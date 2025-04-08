import ast
from pathlib import Path
import click
import chromadb


def analyze_python_file(file_path: Path) -> list[dict]:
    with file_path.open("r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        # Erfasse öffentliche Funktionen
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                results.append(
                    {
                        "class": node.__class__.__name__,
                        "name": node.name,
                        "docstring": ast.get_docstring(node),
                        "type": "function",
                        "lineno": node.lineno,
                        "file": str(file_path),
                        "args": [arg.arg for arg in node.args.args],
                        "returns": ast.dump(node.returns) if node.returns else None,
                    }
                )
        # Erfasse öffentliche Attribute (einfacher Ansatz: nur für einfache Zuweisungen)
        elif (
            isinstance(node, ast.Assign)
            and node.targets
            and isinstance(node.targets[0], ast.Name)
        ):
            if not node.targets[0].id.startswith("_"):
                results.append(
                    {
                        "class": node.__class__.__name__,
                        "name": node.targets[0].id,
                        "type": "attribute",
                        "data_type": ast.dump(node.value),
                        "docstring": None,
                        "lineno": node.lineno,
                        "file": str(file_path),
                    }
                )
    return results


def build_doc_id(element: dict) -> str:
    return f"{element['file']}_{element['class']}_{element['name']}"


def build_text_content(element: dict) -> str:
    if element["type"] == "function":
        return (
            f"{element['type']} {element['class']}: def {element['name']}({element['args']}) -> {element['returns']}: "
            f"docstring: {element['docstring']} "
            f"at line {element['lineno']} in {element['file']}"
        )
    elif element["type"] == "attribute":
        return (
            f"{element['class']} {element['type']}: "
            f"{element['name']} of data type {element['data_type']} "
            f"at line {element['lineno']} in {element['file']}"
        )
    else:
        raise ValueError("Unbekannter Elementtyp: " + element["type"])


def index_to_chromadb(elements: list[dict], collection_name="public_code_elements"):
    client = chromadb.PersistentClient(path="chromadb", database="chromadb")
    collection = client.get_or_create_collection(collection_name)

    for element in click.progressbar(elements, label="Indexing elements to RAG"):
        doc_id = build_doc_id(element)
        text_content = build_text_content(element)
        collection.add(documents=[text_content], metadatas=[element], ids=[doc_id])


@click.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
def main(directory):
    directory = Path(directory)
    all_elements = []
    py_files = list(directory.rglob("*.py"))
    for py_file in click.progressbar(py_files, label="Analyzing Python files"):
        all_elements.extend(analyze_python_file(py_file))
    index_to_chromadb(all_elements)
    click.echo(f"Indexed {len(all_elements)} elements into Chromadb.")


if __name__ == "__main__":
    main()
