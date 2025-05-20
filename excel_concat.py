# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
#     "openpyxl",
#     "pandas",
#     "rich",
# ]
# ///
from dataclasses import dataclass, field
from pathlib import Path

import click
import pandas as pd
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)
from rich.panel import Panel
from rich.table import Table


@dataclass
class Options:
    """Configuration options for Excel file filtering.

    Attributes:
        include: Tuple of strings that must be in filenames to include
        exclude: Tuple of strings that, if in filenames, will exclude the file
        extensions: List of file extensions to include (defaults to .xls and .xlsx)
    """

    include: tuple[str, ...]
    exclude: tuple[str, ...]
    extensions: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Initialize default extensions if none provided."""
        if len(self.extensions) == 0:
            self.extensions = [".xls", ".xlsx"]

    def is_allowed(self, path: Path) -> bool:
        """Check if a file path meets all filtering criteria.

        Parameters
        ----------
            path: Path object to check against filters

        Returns
        -------
            True if file should be included, False otherwise
        """
        if not self.is_extension(path):
            return False
        if len(self.include) > 0 and not any(incl in path.name for incl in self.include):
            return False
        if len(self.exclude) > 0 and any(excl in path.name for excl in self.exclude):
            return False
        return True

    def is_extension(self, path: Path) -> bool:
        """Check if a file has one of the allowed extensions.

        Parameters
        ----------
            path: Path object to check extension

        Returns
        -------
            True if extension matches allowed list, False otherwise
        """
        return any(path.suffix.lower() == ext for ext in self.extensions)


def find_excel_files(directory: Path, options: Options) -> list[Path]:
    """Recursively find all Excel files in a directory matching filter options.

    Parameters
    ----------
        directory: Base directory to search in
        options: Filter options to apply

    Returns
    -------
        List of Path objects to Excel files that match criteria
    """
    result = []
    for path in directory.rglob("*"):
        if not path.is_file() or not options.is_allowed(path):
            continue
        result.append(path)
    return result


def read_excel_file(file_path: Path, console: Console) -> dict[str, pd.DataFrame]:
    """Read an Excel file into a pandas DataFrame with error handling.

    Parameters
    ----------
        file_path: Path to the Excel file
        console: Rich console for displaying errors

    Returns
    -------
        DataFrame if file was read successfully, None if there was an error
    """
    try:
        return pd.read_excel(file_path, engine="openpyxl", sheet_name=None)
    except Exception as e:
        console.print(f"[bold red]Error reading {file_path}: {str(e)}[/]")
        return {}


def create_progress_bar(console: Console) -> Progress:
    """Create a standardized Rich progress bar.

    Parameters
    ----------
        console: Rich console instance

    Returns
    -------
        Configured Progress object for displaying progress
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def read_excel_files(excel_files: list[Path], console: Console) -> list[pd.DataFrame]:
    """Read multiple Excel files with progress tracking.

    Parameters
    ----------
        excel_files: List of Excel file paths to read
        console: Rich console for display

    Returns
    -------
        List of successfully read DataFrames
    """
    dataframes = []

    with create_progress_bar(console) as progress:
        task = progress.add_task("[cyan]Reading Excel files...", total=len(excel_files))

        for excel_file in excel_files:
            progress.update(task, advance=1, description=f"[cyan]Reading {excel_file.name}...")
            sheets = read_excel_file(excel_file, console)
            if sheets is None:
                continue
            dataframes.append(sheets)

    return dataframes


def concat_dataframes(dataframes: list[pd.DataFrame], console: Console) -> pd.DataFrame:
    """Concatenate multiple DataFrames into one.

    Parameters
    ----------
        dataframes: List of DataFrames to concatenate
        console: Rich console for error display

    Returns
    -------
        Single concatenated DataFrame

    Raises
    ------
        click.Abort: If no valid DataFrames are available
    """
    if not dataframes:
        console.print("[bold red]No valid Excel files found![/]")
        raise click.Abort()

    return pd.concat(dataframes, ignore_index=True)


def display_file_table(files: list[Path], console: Console) -> None:
    """Display a formatted table of found Excel files.

    Parameters
    ----------
        files: List of file paths to display
        console: Rich console for display
    """
    table = Table(title="Found Excel Files")
    table.add_column("No.", style="cyan", justify="right")
    table.add_column("Filename", style="green")
    table.add_column("Size", style="magenta", justify="right")

    for i, file in enumerate(files, 1):
        size_kb = file.stat().st_size / 1024
        table.add_row(str(i), file.name, f"{size_kb:.1f} KB")

    console.print(table)


def save_dataframe(df: pd.DataFrame, output_path: Path, console: Console) -> None:
    """Save a DataFrame to an Excel file with progress indication.

    Parameters
    ----------
        df: DataFrame to save
        output_path: Path where to save the Excel file
        console: Rich console for display
    """
    with create_progress_bar(console) as progress:
        task = progress.add_task("[cyan]Saving output file...", total=1)
        df.to_excel(output_path, index=False)
        progress.update(task, advance=1, completed=True)


def print_header(console: Console) -> None:
    """Display the application header.

    Parameters
    ----------
        console: Rich console for display
    """
    console.print(Panel.fit("[bold cyan]Excel Files Merger[/]", border_style="cyan"))


def print_result_summary(df: pd.DataFrame, output_path: Path, console: Console) -> None:
    """Display a summary of the operation results.

    Parameters
    ----------
        df: The concatenated DataFrame
        output_path: Path where the file was saved
        console: Rich console for display
    """
    console.print(f"[bold green]✓ Done! [/]Merged data has been saved to: {output_path}")
    console.print(f"[dim]Number of rows: {len(df)}[/]")


@click.command()
@click.option(
    "--dir",
    "-d",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    required=True,
    help="Directory containing Excel files",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Path to output Excel file",
)
@click.option(
    "--include",
    "-i",
    multiple=True,
    help="Include only files containing this string (can be used multiple times)",
)
@click.option(
    "--exclude",
    "-e",
    multiple=True,
    help="Exclude files containing this string (can be used multiple times)",
)
def main(dir: Path, output: Path, include: tuple, exclude: tuple):
    """Tool for merging multiple Excel files into a single file.

    This utility recursively searches through directories to find Excel files,
    applies filtering based on filename patterns, and concatenates all matching
    files into a single output Excel file. The tool provides a user-friendly
    interface with progress indicators and clear output summaries.

    Usage examples:

    Merge all Excel files in a directory:
    $ python main.py --dir /data --output result.xlsx

    Only include files with '2023' in the name:
    $ python main.py --dir /data --output result.xlsx --include 2023

    Include files with 'sales' but exclude those with 'test':
    $ python main.py --dir /data --output result.xlsx --include sales --exclude test
    """
    console = Console()

    print_header(console)

    options = Options(include=include, exclude=exclude)

    console.print(f"[yellow]Searching for Excel files in:[/] {dir}")
    excel_files = find_excel_files(dir, options)

    if not excel_files:
        console.print("[bold red]No Excel files found![/]")
        raise click.Abort()

    console.print(f"[green]{len(excel_files)} Excel files found.[/]")
    display_file_table(excel_files, console)

    console.print("\n[yellow]Beginning to merge files...[/]")
    dataframes = read_excel_files(excel_files, console)
    combined_df = concat_dataframes(dataframes, console)

    console.print(f"\n[yellow]Saving merged data to:[/] {output}")
    save_dataframe(combined_df, output, console)

    print_result_summary(combined_df, output, console)


if __name__ == "__main__":
    main()
