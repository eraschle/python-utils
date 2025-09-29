# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
# ]
# ///
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console

from git_common import GitOptions as BaseGitOptions


@dataclass
class GitOptions(BaseGitOptions):
    """Options for Git operations for line ending adjustment."""

    extensions: list[str] | None = None
    line_ending: str = "crlf"
    cleanup: bool = True
    force: bool = False
    continue_process: bool = True
    should_overwrite: bool = True

    def __post_init__(self):
        if self.extensions is None:
            self.extensions = []


def run_git_command(
    console: Console, command: list[str], options: GitOptions, error_message: str
) -> tuple[bool, subprocess.CompletedProcess[bytes] | None]:
    """
    Executes a Git command and returns the result.

    Args:
        console: Console object for output
        command: List with the command to execute and its arguments
        options: GitOptions with configuration options
        error_message: Error message to display on error

    Returns:
        Tuple with a Boolean (True on success, False on error) and the CompletedProcess object (or None on error)
    """
    try:
        result = subprocess.run(command, check=True, capture_output=True)

        if options.verbose:
            console.print(f"[dim]Command: {' '.join(command)}[/]")
            console.print(f"[dim]Output: {result.stdout.decode() if result.stdout else 'No output'}[/]")

        return True, result
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{error_message}[/] {e}")
        console.print(f"Output: {e.stdout.decode() if e.stdout else ''}")
        console.print(f"Error: {e.stderr.decode() if e.stderr else ''}")
        return False, None


def init_git_repo(console: Console, options: GitOptions) -> bool:
    """
    Initialize Git repository.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    console.print("[bold blue]Initializing Git repository...[/]")
    success, _ = run_git_command(
        console,
        ["git", "init", "."],
        options,
        "Error initializing Git repository:",
    )
    return success


def add_files_to_git(console: Console, options: GitOptions) -> bool:
    """
    Add all files to the repository.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    console.print("[bold blue]Adding files to repository...[/]")
    success, _ = run_git_command(
        console,
        ["git", "add", "."],
        options,
        "Error adding files:",
    )
    return success


def create_initial_commit(console: Console, options: GitOptions) -> bool:
    """
    Create initial commit, but only if there are changes.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    # Check if there are changes that can be committed
    success, result = run_git_command(
        console,
        ["git", "status", "--porcelain"],
        options,
        "Error checking Git status:",
    )

    if not success:
        return False

    if result is None:
        console.print("[bold red]Error checking Git status (Result is NONE).[/]")
        return False

    # If no changes exist, there's nothing to commit
    if not result.stdout.strip():
        console.print("[yellow]No changes to commit.[/]")
        return True

    console.print("[bold blue]Creating initial commit...[/]")
    success, _ = run_git_command(
        console,
        ["git", "commit", "-m", "initial commit"],
        options,
        "Error creating initial commit:",
    )
    return success


def create_gitattributes(console: Console, options: GitOptions) -> bool:
    """
    Creates the .gitattributes file with the desired line endings.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    try:
        console.print(f"[bold blue]Creating .gitattributes for {options.line_ending} line endings...[/]")

        with open(".gitattributes", "w", encoding="utf-8") as f:
            # Add a rule for each specified file extension
            if options.extensions:
                for ext in options.extensions:
                    ext_pattern = f"*.{ext}" if not ext.startswith("*.") else ext
                    f.write(f"{ext_pattern} text eol={options.line_ending}\n")

                    if options.verbose:
                        console.print(f"[dim]Rule added: {ext_pattern} text eol={options.line_ending}[/]")
            else:
                # Default rule for all text files
                f.write(f"* text eol={options.line_ending}\n")

                if options.verbose:
                    console.print(f"[dim]Default rule added: * text eol={options.line_ending}[/]")

        return True
    except Exception as e:
        console.print(f"[bold red]Error creating .gitattributes file:[/] {e}")
        return False


def clear_git_cache(console: Console, options: GitOptions) -> bool:
    """
    Clear Git cache.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    console.print("[bold blue]Clearing Git cache...[/]")
    success, _ = run_git_command(
        console,
        ["git", "rm", "--cached", "-r", "."],
        options,
        "Error clearing Git cache:",
    )
    return success


def reset_changes(console: Console, options: GitOptions) -> bool:
    """
    Reset changes and adjust line endings.

    Args:
        console: Console object for output
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    console.print("[bold blue]Resetting changes and adjusting line endings...[/]")
    success, _ = run_git_command(
        console,
        ["git", "reset", "--hard"],
        options,
        "Error resetting changes:",
    )
    return success


def cleanup_git_files(console: Console, directory: Path, options: GitOptions) -> bool:
    """
    Deletes Git-specific files.

    Args:
        console: Console object for output
        directory: Directory where files should be deleted
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    # Delete .gitattributes file (created by create_gitattributes)
    # Additional files that could be created by Git operations in create_temp_git_repo
    git_files = [
        ".gitattributes",
        ".gitignore",  # Could be created by Git operations
        ".gitmodules",  # Could be created for submodules
        ".gitconfig",  # Could be created by Git configuration
    ]

    try:
        for git_file in git_files:
            file_path = directory / git_file
            if not file_path.exists():
                continue
            if options.verbose:
                console.print(f"[dim]Deleting file: {file_path}[/]")
            file_path.unlink()
            console.print(f"[bold green]{git_file} has been deleted.[/]")
        return True
    except Exception as e:
        console.print(f"[bold red]Error deleting Git files:[/] {e}")
        return False


def overwrite_repository(console: Console, directory: Path, options: GitOptions) -> bool:
    """
    Overwrites an existing Git repository by deleting the .git directory.

    Args:
        console: Console object for output
        directory: Directory where the repository should be overwritten
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        # No repository present, nothing to do
        if options.verbose:
            console.print("[dim]No existing Git repository found to overwrite.[/]")
        return True

    console.print("[bold blue]Overwriting existing Git repository...[/]")
    return cleanup_git_dir(console, directory, options)


def cleanup_git_dir(console: Console, directory: Path, options: GitOptions) -> bool:
    """
    Deletes the .git directory.

    Args:
        console: Console object for output
        directory: Directory where the .git directory should be deleted
        options: GitOptions with configuration options

    Returns:
        True on success, False on error
    """
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return True

    try:
        if options.verbose:
            console.print(f"[dim]Deleting directory: {git_dir}[/]")

        # Wait briefly so all files can be closed
        import time

        time.sleep(1)  # Wait 1 second

        # Try with shutil.rmtree
        shutil.rmtree(git_dir, ignore_errors=True)

        # Check if the directory still exists
        if not git_dir.exists():
            console.print("[bold green].git directory has been deleted.[/]")
            return True

        # If the directory still exists, try with an external command
        console.print("[yellow]Could not delete .git directory with Python, trying external command...[/]")

        if platform.system() == "Windows":
            # On Windows with rd /s /q
            success, _ = run_git_command(
                console,
                ["cmd", "/c", "rd", "/s", "/q", str(git_dir)],
                options,
                "Error deleting .git directory:",
            )
        else:
            # On Unix with rm -rf
            success, _ = run_git_command(
                console,
                ["rm", "-rf", str(git_dir)],
                options,
                "Error deleting .git directory:",
            )

        if success:
            console.print("[bold green].git directory has been deleted.[/]")
            return True

        # If that doesn't work either, give instructions for manual deletion
        console.print("[bold yellow]The .git directory could not be deleted automatically.[/]")
        console.print(f"Please delete the directory manually: {git_dir}")
        return False

    except Exception as e:
        console.print(f"[bold red]Error deleting .git directory:[/] {e}")
        console.print(f"Please delete the directory manually: {git_dir}")
        return False


def cleanup_git_repo(
    console: Console,
    directory: Path,
    options: GitOptions,
    should_delete_git_dir: bool = True,
) -> bool:
    """
    Clean up Git repository.

    Args:
        console: Console object for output
        directory: Directory where the repository should be cleaned up
        options: GitOptions with configuration options
        should_delete_git_dir: If True, the .git directory will be deleted

    Returns:
        True on success, False on error
    """
    console.print("[bold blue]Cleaning up Git repository...[/]")

    # Always clean up Git files
    cleanup_file = cleanup_git_files(console, directory, options)

    # Only delete .git directory if desired
    cleanup_dir = True
    if should_delete_git_dir:
        cleanup_dir = cleanup_git_dir(console, directory, options)

    return cleanup_dir and cleanup_file


def overwrite_existing_repo(console: Console, directory: Path, options: GitOptions) -> None:
    """
    Checks if a Git repository exists and asks for confirmation to adjust or overwrite.

    Args:
        console: Console object for output
        directory: Directory where the repository should be checked
        options: GitOptions with configuration options

    Results are written directly to the options parameter:
    - options.continue_process: True if the process should continue, False if aborted
    - options.should_overwrite: True if the repository should be overwritten, False if only adjusted
    """
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        # No repository present, nothing to do
        if options.verbose:
            console.print("[dim]No existing Git repository found.[/]")
        options.continue_process = True
        options.should_overwrite = True
        return

    if options.force:
        if options.verbose:
            console.print("[dim]Existing Git repository will be overwritten (--force).[/]")
        options.continue_process = True
        options.should_overwrite = True
        return

    console.print("[bold yellow]Warning:[/] A Git repository already exists in this directory.")

    # Ask whether the repository should be overwritten or adjusted
    choices = ["Overwrite", "Adjust", "Cancel"]
    choice = click.prompt(
        "Would you like to overwrite, adjust the existing repository, or cancel the operation?",
        type=click.Choice(choices),
        default="Adjust",
    )

    if choice == "Cancel":
        console.print("[bold yellow]Operation cancelled.[/]")
        options.continue_process = False
        options.should_overwrite = False
        return

    if choice == "Overwrite":
        console.print("[bold blue]Overwriting existing Git repository...[/]")
        options.continue_process = True
        options.should_overwrite = True
        return

    # Otherwise: Adjust
    console.print("[bold blue]Adjusting line endings in existing repository...[/]")
    options.continue_process = True
    options.should_overwrite = False


def open_file_explorer(directory: Path, console: Console, verbose: bool) -> None:
    """
    Opens the file explorer for the specified directory.

    Args:
        directory: The directory to open
        console: Console object for output
        verbose: If True, detailed information will be displayed
    """
    try:
        if verbose:
            console.print(f"[dim]Opening file explorer for: {directory}[/]")

        system = platform.system()
        if system == "Windows":
            os.startfile(directory)
        elif system == "Darwin":  
            subprocess.run(["open", directory], check=True)
        else:  # Linux und andere
            subprocess.run(["xdg-open", directory], check=True)

        console.print(f"[bold green]File explorer for {directory} has been opened.[/]")
    except Exception as e:
        console.print(f"[bold red]Error opening file explorer:[/] {e}")


def create_git_repo(directory: Path, options: GitOptions) -> None:
    """
    Creates a Git repository and adjusts line endings.

    Args:
        directory: The directory where line endings should be adjusted
        options: GitOptions with configuration options
        open_explorer: If True, the file explorer will be opened after completion
    """
    console = Console()

    # Ensure the directory exists
    if not directory.exists() or not directory.is_dir():
        console.print(f"[bold red]Error:[/] The directory {directory} does not exist.")
        return

    # Change to the directory
    original_dir = os.getcwd()
    os.chdir(directory)

    # If the repository should be overwritten, delete the existing .git directory
    if options.should_overwrite:
        if not overwrite_repository(console, directory, options):
            console.print("[bold red]Error overwriting existing repository.[/]")
            os.chdir(original_dir)
            return

    # List of functions to execute
    steps = [
        init_git_repo,
        create_gitattributes,
        add_files_to_git,
        create_initial_commit,
        clear_git_cache,
        reset_changes,
    ]

    success = True
    try:
        # Execute each step and check for success
        for step in steps:
            if step(console, options):
                continue
            success = False
            break

        if success:
            console.print("[bold green]Line endings have been successfully adjusted![/]")

    finally:
        # Clean up Git repository if desired
        if options.cleanup and success:
            # Only delete the .git directory if none existed before or the existing one was overwritten
            should_delete_git_dir = options.should_overwrite
            cleanup_git_repo(console, directory, options, should_delete_git_dir)

        # Change back to the original directory
        os.chdir(original_dir)


@click.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd(),
)
@click.option(
    "--extensions",
    "-e",
    multiple=True,
    help="File extensions to adjust (e.g. 'py,txt,md')",
)
@click.option(
    "--line-ending",
    "-l",
    type=click.Choice(["crlf", "lf"]),
    default="crlf",
    help="Type of line endings (default: crlf)",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
@click.option(
    "--keep-git",
    "-k",
    is_flag=True,
    default=False,
    help="Keep Git repository after conversion",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing Git repository without confirmation",
)
@click.option(
    "--open-explorer",
    "-o",
    is_flag=True,
    default=False,
    help="Open file explorer after completion",
)
def main(
    directory: Path,
    extensions: tuple[str, ...],
    line_ending: str,
    verbose: bool,
    keep_git: bool,
    force: bool,
    open_explorer: bool,
):
    """
    Adjusts line endings of files in a directory using Git.

    Parameters:
    -----------
    directory : Path
        The directory where line endings should be adjusted.
    extensions : tuple[str, ...]
        List of file extensions to adjust.
    line_ending : str
        Type of line endings (crlf or lf).
    verbose : bool
        If set, verbose output will be displayed.
    keep_git : bool
        If set, the Git repository will not be deleted after conversion.
    force : bool
        If set, an existing Git repository will be overwritten without confirmation.
    open_explorer : bool
        If set, the file explorer will be opened after completion.
    """
    console = Console()

    if verbose:
        console.print(f"[bold]Directory:[/] {directory}")
        console.print(f"[bold]Line endings:[/] {line_ending}")
        if extensions:
            console.print(f"[bold]File extensions:[/] {', '.join(extensions)}")
        else:
            console.print("[bold]File extensions:[/] All text files")
        console.print(f"[bold]Keep Git repository:[/] {'Yes' if keep_git else 'No'}")
        console.print(f"[bold]Force mode:[/] {'Yes' if force else 'No'}")
        console.print(f"[bold]Open file explorer:[/] {'Yes' if open_explorer else 'No'}")

    # Create list of file extensions
    ext_list = []
    for ext_group in extensions:
        ext_list.extend([e.strip() for e in ext_group.split(",") if e.strip()])

    # Create GitOptions
    options = GitOptions(
        extensions=ext_list,
        line_ending=line_ending,
        cleanup=not keep_git,
        verbose=verbose,
        force=force,
    )

    # Check and optionally overwrite an existing repository
    overwrite_existing_repo(console, directory, options)
    if not options.continue_process:
        return

    create_git_repo(directory, options)

    # Open file explorer if desired
    if open_explorer:
        open_file_explorer(directory, console, options.verbose)


if __name__ == "__main__":
    main()
