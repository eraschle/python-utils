"""
Common Git functionalities for various scripts.

This module contains common classes and functions that can be used by various
Git-related scripts in the python-utility project.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console


@dataclass
class GitOptions:
    """Base class for Git operation options."""

    console: Optional[Console] = None  # Console object for output
    verbose: bool = False  # Show verbose output
    recursive: bool = False  # Search recursively in subdirectories

    # List of field names to ignore during comparison
    def __eq__(self, other):
        if not isinstance(other, GitOptions):
            return False

        # Compare only attributes defined in both classes
        attrs = set(self.__annotations__).intersection(set(other.__annotations__))
        return all(getattr(self, attr) == getattr(other, attr) for attr in attrs)


def is_git_repository(path: Path) -> bool:
    """
    Checks if a directory is a Git repository.

    Args:
        path: Path to the directory to check

    Returns:
        True if the directory is a Git repository, otherwise False
    """
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def get_subdirectories(path: Path) -> List[Path]:
    """
    Returns all subdirectories of the specified path.

    Args:
        path: Path where to search for subdirectories

    Returns:
        List of found subdirectories
    """
    return [item for item in path.iterdir() if item.is_dir()]
