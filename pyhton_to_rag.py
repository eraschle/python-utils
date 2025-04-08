# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "chromadb",
#     "click",
# ]
# ///
import ast
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ContextManager

import click

import chromadb

PATH_TO_RAG = Path("C:/workspace/elyo/ai/config/chromadb")


@dataclass
class Options:
    """Options for the script."""

    directory: Path
    collection: str = "python_code"
    db_path: Path = PATH_TO_RAG

    def ensure_db_exists(self) -> str:
        """Ensure the db_path exists."""
        if not self.db_path.exists():
            self.db_path.mkdir(parents=True, exist_ok=True)
        return str(self.db_path.resolve())


class CodeType(StrEnum):
    """Enum for code types."""

    FUNCTION = "function"
    CLASS = "class"
    ATTRIBUTE = "attribute"


def get_class_name(node: ast.AST) -> str:
    """Get the class name from a node if it is a class definition."""
    try:
        return node.__class__.__name__
    except AttributeError:
        return "Global"


def get_docstring(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str:
    """Get the class name from a node if it is a class definition."""
    docstring = ast.get_docstring(node)
    if docstring is None:
        return ""
    return docstring.strip()


def _analyse_class(node: ast.AST, file_path: Path) -> dict:
    """Analyse a function node and return its details."""
    if not isinstance(node, ast.ClassDef):
        return {}
    return {
        "type": CodeType.CLASS,
        "name": node.name,
        "docstring": get_docstring(node),
        "lineno": node.lineno,
        "file": str(file_path),
    }


def _get_arg_string(node: ast.arg) -> str:
    """Get the argument string from a node."""
    if node.arg.startswith("_"):
        return ""
    parts = [node.arg, node.annotation, node.type_comment]
    parts = [str(part).strip() for part in parts if part is not None]
    return ": ".join([part for part in parts if len(part) > 0])


def _get_function_args(node: ast.arguments) -> str:
    """Get the function arguments from a node."""
    if len(node.args) == 0:
        return ""
    args_string = [_get_arg_string(arg) for arg in node.args]
    args_string = [arg for arg in args_string if len(arg) > 0]
    if len(args_string) == 0:
        return ""
    return ", ".join(args_string)


def _analyse_function(node: ast.AST, file_path: Path) -> dict:
    """Analyse a function node and return its details."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return {}
    return {
        "type": CodeType.FUNCTION,
        "class": get_class_name(node),
        "name": node.name,
        "docstring": get_docstring(node),
        "args": _get_function_args(node.args),
        "returns": ast.dump(node.returns) if node.returns else "None",
        "lineno": node.lineno,
        "file": str(file_path),
    }


def _analyse_attribute(node: ast.AST, file_path: Path) -> dict:
    """Analyse a function node and return its details."""
    if not (
        isinstance(node, ast.Assign)
        and node.targets
        and isinstance(node.targets[0], ast.Name)
        and not node.targets[0].id.startswith("_")
    ):
        return {}
    return {
        "type": CodeType.ATTRIBUTE,
        "class": get_class_name(node),
        "name": node.targets[0].id,
        "data_type": ast.dump(node.value),
        "lineno": node.lineno,
        "file": str(file_path),
    }


ANALYSE_FUNCTIONS = [
    _analyse_function,
    _analyse_class,
    _analyse_attribute,
]


def analyze_code(file_path: Path) -> list[dict]:
    with file_path.open("r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        analyse = {}
        for analyse_cb in ANALYSE_FUNCTIONS:
            analyse.update(analyse_cb(node, file_path))
        if len(analyse) == 0:
            continue
        results.append(analyse)
    return results


def build_doc_id(element: dict) -> str:
    if element["type"] == CodeType.CLASS:
        return f"{element['file']}_{element['name']}"
    return f"{element['file']}_{element['class']}_{element['name']}"


def build_text_content(element: dict) -> str:
    text_content = [f"{element.get('class', None)}", f"{element.get('name', None)}"]
    if element["type"] == CodeType.CLASS:
        text_content.append(f"docstring: {element['docstring']}")
    elif element["type"] == CodeType.FUNCTION:
        text_content.append(
            f"def {element['name']} ({element['args']}) -> {element['returns']}"
            f"docstring: {element['docstring']}"
        )
    elif element["type"] == CodeType.ATTRIBUTE:
        text_content.append(f"{element['name']}: {element['data_type']}")
    else:
        raise ValueError(f"Unknown code type: {element['type']}")
    text_content.append(f"at line {element['lineno']} in {element['file']}")
    text_content = [line.strip() for line in text_content if len(line.strip()) > 0]
    return "\n".join(text_content)


def _progress_bar(values: list, label: str) -> ContextManager:
    """Create a progress bar for an iterable."""
    return click.progressbar(values, length=len(values), label=label)


def index_to_chromadb(elements: list[dict], options: Options) -> None:
    client = chromadb.PersistentClient(path=options.ensure_db_exists())
    collection = client.get_or_create_collection(options.collection)

    with _progress_bar(elements, label="Indexing") as bar_index:
        for data in bar_index:
            try:
                collection.add(
                    ids=[build_doc_id(data)],
                    documents=[build_text_content(data)],
                    metadatas=[data],
                )
            except ValueError as exp:
                click.echo(f"Error: Adding {data} to collection failed: {exp}")
            bar_index.update(1)


@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--collection",
    type=str,
    default="python_code",
    help="Name of the collection.",
)
@click.option(
    "--db-path",
    type=click.Path(exists=True, file_okay=False),
    default=PATH_TO_RAG,
    help="Path to the database.",
)
def main(directory: Path, collection: str, db_path: Path) -> None:
    directory = Path(directory)
    options = Options(
        directory=directory,
        collection=collection,
        db_path=db_path,
    )
    anlaysed = []
    py_files = list(directory.rglob("*.py"))
    with _progress_bar(py_files, label="Analyzing") as files:
        for file in files:
            anlaysed.extend(analyze_code(file))
            files.update(1)
    index_to_chromadb(anlaysed, options)
    click.echo(f"Indexed {len(anlaysed)} elements into Chromadb.")


if __name__ == "__main__":
    main()
