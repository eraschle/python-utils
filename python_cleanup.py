# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
# ]
# ///
"""
Python Project Cleanup Tool

Recursively removes all Python/tools generated files and folders.
Uses Click for CLI and Rich for beautiful terminal output.
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
    """Statistics for the cleanup operation."""

    deleted_dirs: int = 0
    deleted_files: int = 0
    total_size: int = 0
    errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class PythonCleaner:
    """Main class for Python cleanup."""

    # Standard patterns for folders to delete
    STANDARD_DIRS = {
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".tox",
        "build",
        "dist",
        ".eggs",
        "node_modules",  # If npm/yarn is used
        ".uv",
    }

    # Patterns for files to delete
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

    # Egg-Info Patterns (special handling)
    EGG_INFO_PATTERNS = {
        "*.egg-info",
        "*.dist-info",
    }

    # Optional patterns
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
        """Calculates the size of a file or folder."""
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
            self.stats.errors.append(f"Size calculation failed for {path}: {e}")
        return 0

    def safe_delete(self, path: Path, item_type: str) -> bool:
        """Safely deletes a file or folder."""
        if not path.exists():
            return False

        # Calculate size before deletion
        size = self.get_size(path)
        self.stats.total_size += size

        if self.dry_run:
            if item_type == "dir":
                self.stats.deleted_dirs += 1
                if self.verbose:
                    console.print(f"[yellow][DRY-RUN][/yellow] Would delete folder: {path}")
            else:
                self.stats.deleted_files += 1
                if self.verbose:
                    console.print(f"[yellow][DRY-RUN][/yellow] Would delete file: {path}")
            return True

        try:
            if item_type == "dir":
                shutil.rmtree(path)
                self.stats.deleted_dirs += 1
                if self.verbose:
                    console.print(f"[green]✓[/green] Folder deleted: {path}")
            else:
                path.unlink()
                self.stats.deleted_files += 1
                if self.verbose:
                    console.print(f"[green]✓[/green] File deleted: {path}")
            return True

        except (OSError, PermissionError) as e:
            error_msg = f"Error deleting {path}: {e}"
            self.stats.errors.append(error_msg)
            console.print(f"[red]✗[/red] {error_msg}")
            return False

    def find_and_delete_dirs(self, patterns: set[str], progress_task: TaskID, progress: Progress) -> None:
        """Finds and deletes folders based on patterns."""
        for pattern in patterns:
            for path in self.target_dir.rglob(pattern):
                if path.is_dir():
                    self.safe_delete(path, "dir")
                    progress.advance(progress_task)

    def find_and_delete_files(self, patterns: set[str], progress_task: TaskID, progress: Progress) -> None:
        """Finds and deletes files based on patterns."""
        for pattern in patterns:
            for path in self.target_dir.rglob(pattern):
                if path.is_file():
                    self.safe_delete(path, "file")
                    progress.advance(progress_task)

    def find_egg_info_dirs(self, progress_task: TaskID, progress: Progress) -> None:
        """Special handling for egg-info directories."""
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
        """Performs the cleanup."""

        # Collect all patterns
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

        # Create progress bar
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            # Estimate number of items (approximate)
            estimated_items = len(dir_patterns) + len(file_patterns) + len(self.EGG_INFO_PATTERNS)
            task = progress.add_task("Cleanup running...", total=estimated_items * 10)

            # Delete folders
            progress.update(task, description="Deleting folders...")
            self.find_and_delete_dirs(dir_patterns, task, progress)

            # Delete egg-info folders
            progress.update(task, description="Deleting egg-info folders...")
            self.find_egg_info_dirs(task, progress)

            # Delete files
            progress.update(task, description="Deleting files...")
            self.find_and_delete_files(file_patterns, task, progress)

            # Cleanup empty __pycache__ folders
            progress.update(task, description="Cleanup empty folders...")
            self.cleanup_empty_pycache_dirs(task, progress)

        return self.stats

    def cleanup_empty_pycache_dirs(self, progress_task: TaskID, progress: Progress) -> None:
        """Removes empty __pycache__ folders."""
        for path in self.target_dir.rglob("__pycache__"):
            if path.is_dir():
                try:
                    # Check if folder is empty
                    if not any(path.iterdir()):
                        self.safe_delete(path, "dir")
                        progress.advance(progress_task)
                except OSError:
                    pass


def format_size(size_bytes: float) -> str:
    """Formats bytes into human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def create_summary_table(stats: CleanupStats, dry_run: bool) -> Table:
    """Creates a summary table."""
    table = Table(title="Cleanup Summary", show_header=True, header_style="bold magenta")
    table.add_column("Category", style="cyan")
    table.add_column("Count", justify="right", style="green")

    prefix = "Would delete" if dry_run else "Deleted"

    table.add_row(f"{prefix} (Folders)", str(stats.deleted_dirs))
    table.add_row(f"{prefix} (Files)", str(stats.deleted_files))
    table.add_row("Freed space", format_size(stats.total_size))

    if stats.errors:
        table.add_row("Errors", str(len(stats.errors)), style="red")

    return table


def show_errors(stats: CleanupStats, max_errors: int):
    """Shows errors if present."""
    if not stats.errors:
        return

    if max_errors < 0:
        max_errors = sys.maxsize

    console.print("\n[red]⚠️  Errors during cleanup:[/red]")
    for error in stats.errors[:max_errors]:
        console.print(f"  [red]•[/red] {error}")

    if len(stats.errors) > max_errors:
        console.print(f"  [red]...[/red] and {len(stats.errors) - max_errors} more errors")


def show_warnings(include_all: bool, include_venv: bool, dry_run: bool, quiet: bool):
    # Display warnings
    warnings = []
    if include_all:
        warnings.append(
            "[red]⚠️  All optional deletion options are enabled![/red]",
        )
    elif include_venv:
        warnings.append(
            "[red]⚠️  Virtual environments will be deleted![/red]",
        )
    if not dry_run:
        warnings.append(
            "[yellow]⚠️  Files will be permanently deleted![/yellow]",
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
    help="Show only what would be deleted (no actual deletion)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output (summary only)")
@click.option(
    "--max-errors-display",
    "-e",
    default=-1,
    type=int,
    help="Maximum number of errors to display (default: -1 for all errors)",
)
@click.option(
    "--include-all",
    is_flag=True,
    help="Include all optional deletion options (venv, logs, coverage)",
)
@click.option(
    "--include-venv",
    is_flag=True,
    help="Also delete virtual environments (caution!)",
)
@click.option(
    "--include-ai",
    is_flag=True,
    help="Also delete AI folders and files",
)
@click.option(
    "--include-logs",
    is_flag=True,
    help="Also delete log files",
)
@click.option(
    "--include-coverage",
    is_flag=True,
    help="Also delete coverage reports",
)
@click.option(
    "--confirm/--no-confirm",
    default=True,
    help="Ask for confirmation before deletion",
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
    Python Project Cleanup Tool

    Recursively removes all Python/tools generated files and folders.

    TARGET_DIRECTORY: Target directory (default: current directory)
    """

    if not quiet:
        # Show header
        console.print(
            Panel.fit(
                "[bold blue]🐍 Python Project Cleanup Tool[/bold blue]\n"
                f"Target directory: [cyan]{target_directory}[/cyan]",
                border_style="blue",
            )
        )

    if include_all:
        include_venv = True
        include_logs = True
        include_coverage = True

    # Display warnings
    show_warnings(include_all, include_venv, dry_run, quiet)

    # Get confirmation (except for dry-run or when disabled)
    if not dry_run and confirm and not quiet:
        if not Confirm.ask("Do you want to continue?"):
            console.print("[yellow]Cancelled.[/yellow]")
            return

    # Create and run cleaner
    if not quiet:
        console.print(
            "[cyan]Starting cleanup...[/cyan]",
            highlight=False,
        )
    cleaner = PythonCleaner(target_directory, dry_run=dry_run, verbose=verbose and not quiet)

    if not quiet:
        if dry_run:
            mode_text = "[yellow]DRY-RUN Mode[/yellow]"
        else:
            mode_text = "[green]Deleting files[/green]"
        console.print(f"\n{mode_text} - Starting cleanup...")

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
                console.print("\n[yellow]💡 This was a DRY-RUN - no files were deleted.[/yellow]")
                console.print("[cyan]Run the tool without --dry-run to delete the files.[/cyan]")
            else:
                console.print(
                    "\n[green]✅ Cleanup successfully completed![/green]",
                )

            show_errors(stats, max_errors_display)
        else:
            # Quiet mode - statistics only
            prefix = "WOULD_DELETE" if dry_run else "DELETED"
            print(f"{prefix}_DIRS={stats.deleted_dirs}")
            print(f"{prefix}_FILES={stats.deleted_files}")
            print(f"SIZE_FREED={stats.total_size}")
            print(f"ERRORS={len(stats.errors)}")

    except KeyboardInterrupt:
        console.print("\n[red]❌ Cleanup was aborted.[/red]")
        raise click.Abort()
    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {e}[/red]")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    main()
