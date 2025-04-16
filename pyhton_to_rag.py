# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "chromadb",
#     "click",
#     "rich",
# ]
# ///
import sys
import ast
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import ContextManager
from rich.console import Console
from rich.table import Table

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
    qualified_name = f"{file_path.stem}.{node.name}"
    # Suche im Klassenkörper nach einem Konstruktor (__init__)
    constructor = {}
    for item in node.body:
        if isinstance(item, ast.FunctionDef) and item.name == "__init__":
            # Hier rufen wir _analyse_function auf und passen den qualified_name an
            constructor = _analyse_function(item, file_path)
            constructor["qualified_name"] = f"{qualified_name}.__init__"
            break
    result = {
        "type": CodeType.CLASS,
        "name": node.name,
        "qualified_name": qualified_name,
        "docstring": get_docstring(node),
        "lineno": node.lineno,
        "file": str(file_path),
    }
    if constructor:
        result["constructor"] = constructor
    return result


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
    # Prüfe, ob der Knoten einen Elternteil hat, der eine Klasse ist
    parent_class = getattr(node, "parent", None)
    if parent_class and isinstance(parent_class, ast.ClassDef):
        qualified_name = f"{file_path.stem}.{parent_class.name}.{node.name}"
    else:
        qualified_name = f"{file_path.stem}.{node.name}"
    return {
        "type": CodeType.FUNCTION,
        "class": get_class_name(node),
        "name": node.name,
        "qualified_name": qualified_name,
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


def _print_error(node: ast.AST, file_path: Path, exp: Exception) -> str:
    lineno = getattr(node, "lineno", None)
    if lineno is None:
        return f"[bold red]Error[/]: {file_path}:\nNode: {node}\nException: {exp}"
    return f"[bold red]Error[/]: {file_path}:\nNode: {node} at line {lineno}\nException: {exp}"


def analyze_code(file_path: Path) -> tuple[list[dict], list[str]]:
    errors = []
    with file_path.open("r", encoding="utf-8") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=str(file_path.name))
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                setattr(child, "parent", node)
    except SyntaxError as exp:
        errors.append(f"[bold red]SyntaxError[/]: {file_path}:\n{exp}")
        return [], errors
    results = []
    for node in ast.walk(tree):
        analyse = {}
        for analyse_cb in ANALYSE_FUNCTIONS:
            try:
                analyse.update(analyse_cb(node, file_path))
            except Exception as exp:
                errors.append(_print_error(node, file_path, exp))
                continue
        # der Code ist hier proziert zu viel ausgabe,
        if len(analyse) == 0:
            # node_type = node.__class__.__name__
            # errors.append(f"Unknown node type: {node_type} in {file_path}")
            continue
        results.append(analyse)
    return results, errors


def build_doc_id(element: dict) -> str:
    if "type" not in element:
        raise ValueError(f"Element {element} has no tyoe informatuin.")
    if element["type"] == CodeType.CLASS:
        return f"{element['file']}_{element['name']}"
    return f"{element['file']}_{element['class']}_{element['name']}"


def build_text_content(element: dict) -> str:
    if "type" not in element:
        raise ValueError(f"Element {element} has no tyoe informatuin.")
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
    console = Console()  # Neu: konsistente Ausgabe innerhalb von index_to_chromadb
    client = chromadb.PersistentClient(path=options.ensure_db_exists())
    collection = client.get_or_create_collection(options.collection)

    with _progress_bar(elements, label="Indexing") as bar_index:
        for data_dict in bar_index:
            data_type = data_dict.get("type", None)
            if not isinstance(data_type, (int, float, str)):
                data_dict["type"] = str(data_type)
            try:
                collection.add(
                    ids=[build_doc_id(data_dict)],
                    documents=[build_text_content(data_dict)],
                    metadatas=[data_dict],
                )
            except ValueError as exp:
                console.print(
                    f"[bold red]Error:[/] Adding {data_dict} to collection failed: {exp}"
                )
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
    if isinstance(directory, str):
        directory = Path(directory)
    if isinstance(db_path, str):
        db_path = Path(db_path)
    console = Console()  # Neu: Instance global innerhalb von main
    directory = Path(directory)
    options = Options(
        directory=directory,
        collection=collection,
        db_path=db_path,
    )
    anlaysed_data = []
    analyse_error = []
    py_files = list(directory.rglob("*.py"))
    with _progress_bar(py_files, label="Analyzing") as files:
        for file in files:
            analyse, error = analyze_code(file)
            if len(analyse) > 0:
                anlaysed_data.extend(analyse)
            if len(error) > 0:
                analyse_error.extend(error)
            files.update(1)
        print("No errors during analysis.")
    if analyse_error:
        print("Errors during analysis:")
        table = Table(title="Fehlerübersicht während der Analyse")
        table.add_column("Index", justify="right", style="cyan", no_wrap=True)
        table.add_column("Fehlermeldung", style="magenta")
        for idx, msg in enumerate(analyse_error, start=1):
            table.add_row(str(idx), msg)
        console.print("\n\n")
        console.print(table)
    print("Start indexing to Chromadb...")
    index_to_chromadb(anlaysed_data, options)
    console.print(
        f"[bold green]Erfolg:[/] Indexed {len(anlaysed_data)} elements into Chromadb."
    )


if __name__ == "__main__":
    if len(sys.argv) == 2:
        sys.argv.append("directory")
        sys.argv.append("python_code")

    main()
