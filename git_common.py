"""
Gemeinsame Git-Funktionalitäten für verschiedene Skripte.

Dieses Modul enthält gemeinsame Klassen und Funktionen, die von verschiedenen
Git-bezogenen Skripten im python-utils Projekt verwendet werden können.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console


@dataclass
class GitOptions:
    """Basisklasse für Git-Operationsoptionen."""

    console: Optional[Console] = None  # Console-Objekt für die Ausgabe
    verbose: bool = False  # Ausführliche Ausgabe anzeigen
    recursive: bool = False  # Rekursiv in Unterverzeichnissen suchen

    # Liste mit Feldnamen, die beim Vergleich ignoriert werden sollen
    def __eq__(self, other):
        if not isinstance(other, GitOptions):
            return False

        # Vergleiche nur die Attribute, die in beiden Klassen definiert sind
        attrs = set(self.__annotations__).intersection(set(other.__annotations__))
        return all(getattr(self, attr) == getattr(other, attr) for attr in attrs)


def is_git_repository(path: Path) -> bool:
    """
    Prüft, ob ein Verzeichnis ein Git-Repository ist.

    Args:
        path: Pfad zum zu prüfenden Verzeichnis

    Returns:
        True, wenn das Verzeichnis ein Git-Repository ist, sonst False
    """
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def get_subdirectories(path: Path) -> List[Path]:
    """
    Gibt alle Unterverzeichnisse des angegebenen Pfads zurück.

    Args:
        path: Pfad, in dem nach Unterverzeichnissen gesucht werden soll

    Returns:
        Liste der gefundenen Unterverzeichnisse
    """
    return [item for item in path.iterdir() if item.is_dir()]
