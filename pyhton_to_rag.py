import ast
from pathlib import Path
import click
import chromadb


def analyze_python_file(file_path: Path) -> list[dict]:
    with file_path.open('r', encoding='utf-8') as f:
        source = f.read()
    tree = ast.parse(source)
    results = []
    for node in ast.walk(tree):
        # Erfasse öffentliche Funktionen
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith('_'):
                results.append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "type": "function",
                    "lineno": node.lineno,
                    "file": str(file_path),
                    "args": [arg.arg for arg in node.args.args],
                    "returns": ast.dump(node.returns) if node.returns else None

                })
        # Erfasse öffentliche Attribute (einfacher Ansatz: nur für einfache Zuweisungen)
        elif isinstance(node, ast.Assign) and node.targets and isinstance(node.targets[0], ast.Name):
            if not node.targets[0].id.startswith('_'):
                results.append({
                    "name": node.targets[0].id,
                    "type": "attribute",
                    "data_type": ast.dump(node.value),
                    "docstring": None,
                    "lineno": node.lineno,
                    "file": str(file_path)
                })
    return results


def index_to_chromadb(elements: list[dict], collection_name="public_code_elements"):
    client = chromadb.
    try:
        collection = client.get_collection(collection_name)
    except Exception:
        collection = client.create_collection(collection_name)

    # Erzeuge aus jedem Element einen eindeutigen ID-String und ein Textdokument
    for element in elements:
        doc_id = f"{element['file']}_{element['name']}_{element['lineno']}"
        text_content = (f"{element['type']}: {element['name']} in {element['file']} "
                       f"at line {element['lineno']}")
        collection.add(
            documents=[text_content],
            metadatas=[element],
            ids=[doc_id]
        )


@click.command()
@click.argument('directory', type=click.Path(exists=True, file_okay=False))
def main(directory):
    directory = Path(directory)
    all_elements = []
    for py_file in directory.rglob("*.py"):
        all_elements.extend(analyze_python_file(py_file))
    index_to_chromadb(all_elements)
    click.echo(f"Indexed {len(all_elements)} elements into Chromadb.")


if __name__ == "__main__":
    main()
