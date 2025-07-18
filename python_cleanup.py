# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
# ]
# ///
"""
Python Projekt Cleanup Tool

Entfernt rekursiv alle von Python/Tools generierten Dateien und Ordner.
Verwendet Click für CLI und Rich für schöne Terminal-Ausgabe.
"""

import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn
from rich.prompt import Confirm
from rich.table import Table

console = Console()


@dataclass
class CleanupStats:
    """Statistiken für den Cleanup-Vorgang."""

    deleted_dirs: int = 0
    deleted_files: int = 0
    total_size: int = 0
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class PythonCleaner:
    """Hauptklasse für den Python-Cleanup."""

    # Standard-Patterns für zu löschende Ordner
    STANDARD_DIRS = {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "build",
        "dist",
        ".eggs",
        "node_modules",  # Falls npm/yarn verwendet wird
        ".uv",
    }

    # Patterns für zu löschende Dateien
    STANDARD_FILES = {
        "*.pyc",
        "*.pyo",
        "*.pyd",
        ".coverage",
        "coverage.xml",
        "*.cover",
        ".cache",
        "nosetests.xml",
        "pytest.xml",
        ".DS_Store",
        "Thumbs.db",
        "*.tmp",
        "*.temp",
    }

    # Egg-Info Patterns (spezielle Behandlung)
    EGG_INFO_PATTERNS = {
        "*.egg-info",
        "*.dist-info",
    }

    # Optionale Patterns
    VENV_DIRS = {
        "venv",
        ".venv",
        "env",
        ".env",
        "virtualenv",
    }

    LOG_FILES = {
        "*.log",
    }

    COVERAGE_DIRS = {
        "htmlcov",
        "coverage_html_report",
        ".coverage.*",
    }

    AI_FILES = {
        ".aider*",
        "claude.md",
    }

    AI_DIRS = {
        ".aider*",
        ".claude",
    }

    def __init__(self, target_dir: Path, dry_run: bool = False, verbose: bool = False):
        self.target_dir = target_dir.resolve()
        self.dry_run = dry_run
        self.verbose = verbose
        self.stats = CleanupStats()

    def get_size(self, path: Path) -> int:
        """Berechnet die Größe einer Datei oder eines Ordners."""
        try:
            if path.is_file():
                return path.stat().st_size
            elif path.is_dir():
                total = 0
                for item in path.rglob("*"):
                    if item.is_file():
                        try:
                            total += item.stat().st_size
                        except (OSError, PermissionError):
                            pass
                return total
        except (OSError, PermissionError) as e:
            self.stats.errors.append(f"Größenberechnung fehlgeschlagen für {path}: {e}")
        return 0

    def safe_delete(self, path: Path, item_type: str) -> bool:
        """Löscht eine Datei oder einen Ordner sicher."""
        if not path.exists():
            return False

        # Größe vor Löschung berechnen
        size = self.get_size(path)
        self.stats.total_size += size

        if self.dry_run:
            if item_type == "dir":
                self.stats.deleted_dirs += 1
                if self.verbose:
                    console.print(f"[yellow][DRY-RUN][/yellow] Würde Ordner löschen: {path}")
            else:
                self.stats.deleted_files += 1
                if self.verbose:
                    console.print(f"[yellow][DRY-RUN][/yellow] Würde Datei löschen: {path}")
            return True

        try:
            if item_type == "dir":
                shutil.rmtree(path)
                self.stats.deleted_dirs += 1
                if self.verbose:
                    console.print(f"[green]✓[/green] Ordner gelöscht: {path}")
            else:
                path.unlink()
                self.stats.deleted_files += 1
                if self.verbose:
                    console.print(f"[green]✓[/green] Datei gelöscht: {path}")
            return True

        except (OSError, PermissionError) as e:
            error_msg = f"Fehler beim Löschen von {path}: {e}"
            self.stats.errors.append(error_msg)
            console.print(f"[red]✗[/red] {error_msg}")
            return False

    def find_and_delete_dirs(self, patterns: set[str], progress_task: TaskID, progress: Progress) -> None:
        """Findet und löscht Ordner basierend auf Patterns."""
        for pattern in patterns:
            for path in self.target_dir.rglob(pattern):
                if path.is_dir():
                    self.safe_delete(path, "dir")
                    progress.advance(progress_task)

    def find_and_delete_files(self, patterns: set[str], progress_task: TaskID, progress: Progress) -> None:
        """Findet und löscht Dateien basierend auf Patterns."""
        for pattern in patterns:
            for path in self.target_dir.rglob(pattern):
                if path.is_file():
                    self.safe_delete(path, "file")
                    progress.advance(progress_task)

    def find_egg_info_dirs(self, progress_task: TaskID, progress: Progress) -> None:
        """Spezielle Behandlung für egg-info Verzeichnisse."""
        for pattern in self.EGG_INFO_PATTERNS:
            for path in self.target_dir.rglob(pattern):
                if path.is_dir():
                    self.safe_delete(path, "dir")
                    progress.advance(progress_task)

    def cleanup(
        self,
        include_venv: bool = False,
        include_logs: bool = False,
        include_coverage: bool = False,
        include_ai: bool = False,
    ) -> CleanupStats:
        """Führt den Cleanup durch."""

        # Sammle alle Patterns
        dir_patterns = self.STANDARD_DIRS.copy()
        file_patterns = self.STANDARD_FILES.copy()

        if include_venv:
            dir_patterns.update(self.VENV_DIRS)

        if include_logs:
            file_patterns.update(self.LOG_FILES)

        if include_coverage:
            dir_patterns.update(self.COVERAGE_DIRS)

        if include_ai:
            dir_patterns.update(self.AI_DIRS)
            file_patterns.update(self.AI_FILES)

        # Erstelle Progress Bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            # Schätze Anzahl der Items (ungefähr)
            estimated_items = len(dir_patterns) + len(file_patterns) + len(self.EGG_INFO_PATTERNS)
            task = progress.add_task("Cleanup läuft...", total=estimated_items * 10)

            # Lösche Ordner
            progress.update(task, description="Lösche Ordner...")
            self.find_and_delete_dirs(dir_patterns, task, progress)

            # Lösche egg-info Ordner
            progress.update(task, description="Lösche egg-info Ordner...")
            self.find_egg_info_dirs(task, progress)

            # Lösche Dateien
            progress.update(task, description="Lösche Dateien...")
            self.find_and_delete_files(file_patterns, task, progress)

            # Cleanup leerer __pycache__ Ordner
            progress.update(task, description="Cleanup leerer Ordner...")
            self.cleanup_empty_pycache_dirs(task, progress)

        return self.stats

    def cleanup_empty_pycache_dirs(self, progress_task: TaskID, progress: Progress) -> None:
        """Entfernt leere __pycache__ Ordner."""
        for path in self.target_dir.rglob("__pycache__"):
            if path.is_dir():
                try:
                    # Prüfe ob Ordner leer ist
                    if not any(path.iterdir()):
                        self.safe_delete(path, "dir")
                        progress.advance(progress_task)
                except OSError:
                    pass


def format_size(size_bytes: float) -> str:
    """Formatiert Bytes in menschenlesebar Größe."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def create_summary_table(stats: CleanupStats, dry_run: bool) -> Table:
    """Erstellt eine Zusammenfassungstabelle."""
    table = Table(title="Cleanup Zusammenfassung", show_header=True, header_style="bold magenta")
    table.add_column("Kategorie", style="cyan")
    table.add_column("Anzahl", justify="right", style="green")

    prefix = "Würde löschen" if dry_run else "Gelöscht"

    table.add_row(f"{prefix} (Ordner)", str(stats.deleted_dirs))
    table.add_row(f"{prefix} (Dateien)", str(stats.deleted_files))
    table.add_row("Freigegebener Speicher", format_size(stats.total_size))

    if stats.errors:
        table.add_row("Fehler", str(len(stats.errors)), style="red")

    return table


def show_errors(stats: CleanupStats, max_errors: int):
    """Zeigt Fehler an, falls vorhanden."""
    if not stats.errors:
        return

    if max_errors < 0:
        max_errors = sys.maxsize

    console.print("\n[red]⚠️  Fehler während des Cleanup:[/red]")
    for error in stats.errors[:max_errors]:
        console.print(f"  [red]•[/red] {error}")

    if len(stats.errors) > max_errors:
        console.print(f"  [red]...[/red] und {len(stats.errors) - max_errors} weitere Fehler")


def show_warnings(include_all: bool, include_venv: bool, dry_run: bool, quiet: bool):
    # Warnungen anzeigen
    warnings = []
    if include_all:
        warnings.append(
            "[red]⚠️  Alle optionalen Löschoptionen sind aktiviert![/red]",
        )
    elif include_venv:
        warnings.append(
            "[red]⚠️  Virtuelle Umgebungen werden gelöscht![/red]",
        )
    if not dry_run:
        warnings.append(
            "[yellow]⚠️  Dateien werden permanent gelöscht![/yellow]",
        )

    if warnings and not quiet:
        for warning in warnings:
            console.print(warning)
        console.print()


@click.command()
@click.argument(
    "target_directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd(),
)
@click.option(
    "--dry-run",
    "-d",
    is_flag=True,
    help="Zeige nur was gelöscht würde (kein echter Löschvorgang)",
)
@click.option("--verbose", "-v", is_flag=True, help="Ausführliche Ausgabe")
@click.option("--quiet", "-q", is_flag=True, help="Minimale Ausgabe (nur Zusammenfassung)")
@click.option(
    "--max-errors-display",
    "-e",
    default=-1,
    type=int,
    help="Maximale Anzahl an Fehlern, die ausgegeben werden sollen (Standard: -1 für alle Fehler)",
)
@click.option(
    "--include-all",
    is_flag=True,
    help="Inkludiere alle optionalen Löschoptionen (venv, logs, coverage)",
)
@click.option(
    "--include-venv",
    is_flag=True,
    help="Lösche auch virtuelle Umgebungen (Vorsicht!)",
)
@click.option(
    "--include-ai",
    is_flag=True,
    help="Lösche auch AI-Order und Dateien",
)
@click.option(
    "--include-logs",
    is_flag=True,
    help="Lösche auch Log-Dateien",
)
@click.option(
    "--include-coverage",
    is_flag=True,
    help="Lösche auch Coverage-Reports",
)
@click.option(
    "--confirm/--no-confirm",
    default=True,
    help="Frage vor dem Löschen nach Bestätigung",
)
def main(
    target_directory: Path,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
    max_errors_display: int,
    include_all: bool,
    include_venv: bool,
    include_ai: bool,
    include_logs: bool,
    include_coverage: bool,
    confirm: bool,
):
    """
    Python Projekt Cleanup Tool

    Entfernt rekursiv alle von Python/Tools generierten Dateien und Ordner.

    TARGET_DIRECTORY: Zielverzeichnis (Standard: aktuelles Verzeichnis)
    """

    if not quiet:
        # Zeige Header
        console.print(
            Panel.fit(
                "[bold blue]🐍 Python Projekt Cleanup Tool[/bold blue]\n"
                f"Zielverzeichnis: [cyan]{target_directory}[/cyan]",
                border_style="blue",
            )
        )

    if include_all:
        include_venv = True
        include_logs = True
        include_coverage = True

    # Warnungen anzeigen
    show_warnings(include_all, include_venv, dry_run, quiet)

    # Bestätigung einholen (außer bei dry-run oder wenn deaktiviert)
    if not dry_run and confirm and not quiet:
        if not Confirm.ask("Möchten Sie fortfahren?"):
            console.print("[yellow]Abgebrochen.[/yellow]")
            return

    # Cleaner erstellen und ausführen
    if not quiet:
        console.print(
            "[cyan]Starte Cleanup...[/cyan]",
            highlight=False,
        )
    cleaner = PythonCleaner(target_directory, dry_run=dry_run, verbose=verbose and not quiet)

    if not quiet:
        if dry_run:
            mode_text = "[yellow]DRY-RUN Modus[/yellow]"
        else:
            mode_text = "[green]Lösche Dateien[/green]"
        console.print(f"\n{mode_text} - Starte Cleanup...")

    try:
        stats = cleaner.cleanup(
            include_venv=include_venv,
            include_logs=include_logs,
            include_coverage=include_coverage,
            include_ai=include_ai,
        )

        if not quiet:
            console.print()
            console.print(create_summary_table(stats, dry_run))

            if dry_run:
                console.print("\n[yellow]💡 Dies war ein DRY-RUN - keine Dateien wurden gelöscht.[/yellow]")
                console.print("[cyan]Führen Sie das Tool ohne --dry-run aus um die Dateien zu löschen.[/cyan]")
            else:
                console.print(
                    "\n[green]✅ Cleanup erfolgreich abgeschlossen![/green]",
                )

            show_errors(stats, max_errors_display)
        else:
            # Quiet mode - nur Statistiken
            prefix = "WOULD_DELETE" if dry_run else "DELETED"
            print(f"{prefix}_DIRS={stats.deleted_dirs}")
            print(f"{prefix}_FILES={stats.deleted_files}")
            print(f"SIZE_FREED={stats.total_size}")
            print(f"ERRORS={len(stats.errors)}")

    except KeyboardInterrupt:
        console.print("\n[red]❌ Cleanup wurde abgebrochen.[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[red]❌ Unerwarteter Fehler: {e}[/red]")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
