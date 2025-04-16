"""
Tests für git_lineendings.py
"""

import os
import tempfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from git_lineendings import GitOptions, create_gitattributes, main


@pytest.fixture
def temp_dir():
    """Erzeugt ein temporäres Verzeichnis für Tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_dir = os.getcwd()
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(original_dir)


def test_create_gitattributes(temp_dir):
    """Test für die create_gitattributes Funktion."""
    from rich.console import Console

    console = Console(record=True)
    options = GitOptions(extensions=["py", "txt"], line_ending="crlf")

    # Führe die Funktion aus
    result = create_gitattributes(console, options)
    assert result is True

    # Überprüfe, ob die Datei erstellt wurde
    gitattributes_path = temp_dir / ".gitattributes"
    assert gitattributes_path.exists()

    # Überprüfe den Inhalt der Datei
    content = gitattributes_path.read_text(encoding="utf-8")
    assert "*.py text eol=crlf" in content
    assert "*.txt text eol=crlf" in content


def test_create_gitattributes_with_no_extensions(temp_dir):
    """Test für create_gitattributes ohne angegebene Erweiterungen."""
    from rich.console import Console

    console = Console(record=True)
    options = GitOptions(extensions=[], line_ending="lf")

    # Führe die Funktion aus
    result = create_gitattributes(console, options)
    assert result is True

    # Überprüfe, ob die Datei erstellt wurde
    gitattributes_path = temp_dir / ".gitattributes"
    assert gitattributes_path.exists()

    # Überprüfe den Inhalt der Datei
    content = gitattributes_path.read_text(encoding="utf-8")
    assert "* text eol=lf" in content


def test_cli_help():
    """Test für die CLI-Hilfe."""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Passt die Zeilenenden von Dateien" in result.output


@mock.patch("git_lineendings.subprocess.run")
def test_init_git_repo(mock_run, temp_dir):
    """Test für die init_git_repo Funktion mit Mock."""
    from git_lineendings import init_git_repo
    from rich.console import Console

    # Konfiguriere den Mock
    mock_run.return_value.stdout = b"Initialized empty Git repository"
    mock_run.return_value.stderr = b""

    console = Console(record=True)
    options = GitOptions(verbose=True)

    # Führe die Funktion aus
    result = init_git_repo(console, options)

    # Überprüfe das Ergebnis
    assert result is True
    mock_run.assert_called_once()
    assert mock_run.call_args[0][0] == ["git", "init", "."]
