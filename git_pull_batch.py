# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "gitpython",
#     "rich",
# ]
# ///
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import click
import git
from rich.console import Console
from rich.panel import Panel
from rich.table import Table


@dataclass
class GitOptions:
    """Options for git operations."""

    console: Console | None = None  # Console for output
    verbose: bool = False  # Whether to show verbose output
    stash_message: str | None = None  # Custom message for stash
    recursive: bool = True  # Whether to recursively search subdirectories


def get_subdirectories(path: Path) -> Iterable[Path]:
    """
    Get all subdirectories in the given path.

    Parameters
    ----------
    path : Path
        The path to search for directories.

    Returns
    -------
    Iterable[Path]
        An iterable of Path objects representing the directories found in the path.
    """
    for item in path.iterdir():
        if item.is_file():
            continue
        yield item


def is_git_repository(current: Path) -> bool:
    """
    Check if the current path is a git repository.

    A path is considered a git repository if it contains a `.git` directory.

    Parameters
    ----------
    current : Path
        The path to check.

    Returns
    -------
    bool
        True if the path is a git repository, False otherwise.
    """
    if current.is_file():
        return False
    return any(".git" == path.name for path in get_subdirectories(current))


def has_no_changes(repo: git.Git) -> bool:
    """
    Check if the repository has no uncommitted changes.

    Parameters
    ----------
    repo : git.Git
        The repository to check.

    Returns
    -------
    bool
          True if the repository has no changes to commit, False otherwise.
    """
    return "nothing to commit" in repo.status()


def stash_changes(repo: git.Git, options: GitOptions | None = None) -> None:
    """
    Stash changes in the repository.

    Parameters
    ----------
    repo : git.Git
        The repository to stash changes in.
    options : GitOptions, optional
        Options for the git operation, by default None
    """
    if options is None:
        options = GitOptions()

    console = options.console
    stash_message = options.stash_message
    verbose = options.verbose

    if has_no_changes(repo):
        return

    stash_args = []
    if stash_message:
        stash_args.extend(["save", stash_message])

    result = repo.stash(*stash_args)

    if console and "No local changes to save" not in result:
        repo_path = Path(repo.rev_parse("--show-toplevel"))
        console.print(
            f"[yellow]⟳[/yellow] Stashed changes in [bold]{repo_path.name}[/bold]"
        )
        if verbose:
            console.print(f"[blue]ℹ[/blue] Stash result: {result}")


def has_stashed_changes(repo: git.Git) -> bool:
    """
    Check if the repository has any stashed changes.

    Parameters
    ----------
    repo : git.Git
        The repository to check.

    Returns
    -------
    bool
        True if any stashes exist, False otherwise.
    """
    return len(repo.stash("list")) > 0


def restore_stashed_changes(repo: git.Git, options: GitOptions | None = None) -> None:
    """
    Restore (pop) stashed changes in the repository.

    Parameters
    ----------
    repo : git.Git
        The repository to restore stashed changes from.
    options : GitOptions, optional
        Options for the git operation, by default None
    """
    if options is None:
        options = GitOptions()

    console = options.console
    verbose = options.verbose

    if not has_stashed_changes(repo):
        return

    result = repo.stash("pop")

    if console is None:
        return

    repo_path = Path(repo.rev_parse("--show-toplevel"))
    console.print(
        f"[yellow]⟲[/yellow] Restored stashed changes in [bold]{repo_path.name}[/bold]"
    )

    if verbose and console:
        console.print(f"[blue]ℹ[/blue] Stash pop result: {result}")


def pull_repo(repo: git.Git, options: GitOptions | None = None) -> str:
    """
    Pull the latest changes from the remote repository.

    Stashes any changes if the repository is not in a clean state.
    Restores the stashed changes after pulling if any stashes exist.

    Parameters
    ----------
    repo : git.Git
        The repository to pull changes from.
    options : GitOptions, optional
        Options for the git operation, by default None

    Returns
    -------
    str
        The output of the git pull command
    """
    if options is None:
        options = GitOptions()

    if not has_no_changes(repo):
        stash_changes(repo, options)

    pull_output = repo.pull()

    if has_stashed_changes(repo):
        restore_stashed_changes(repo, options)

    return pull_output


def process_git_repo(repo_path: Path, options: GitOptions) -> tuple[int, int]:
    """
    Process a single git repository by pulling the latest changes.

    Parameters
    ----------
    repo_path : Path
        The path to the git repository.
    options : GitOptions
        Options for the git operation.

    Returns
    -------
    tuple[int, int]
        A tuple containing (successful_pulls, failed_pulls)
    """
    repo = git.Git(repo_path)
    console = options.console
    verbose = options.verbose

    try:
        if verbose and console:
            console.print(
                f"[blue]ℹ[/blue] Processing repository: [bold]{repo_path}[/bold]"
            )

        # Create a new options object with the stash message for this repo
        pull_options = GitOptions(
            console=console,
            verbose=verbose,
            stash_message=f"Auto-stash before pull in {repo_path.name}",
            recursive=options.recursive,
        )

        pull_output = pull_repo(repo, pull_options)

        if console:
            if verbose:
                console.print(
                    f"[blue]ℹ[/blue] Pull output for [bold]{repo_path.name}[/bold]:"
                )
                console.print(Panel(pull_output, title="Git Pull Output", expand=False))
            else:
                console.print(f"[green]✓[/green] Pulled [bold]{repo_path.name}[/bold]")

        return 1, 0
    except Exception as e:
        if console:
            console.print(
                f"[red]✗[/red] Failed to pull [bold]{repo_path.name}[/bold]: {e}"
            )
            if verbose:
                import traceback

                console.print("[red]Error details:[/red]")
                console.print(
                    Panel(traceback.format_exc(), title="Error Traceback", expand=False)
                )
        return 0, 1


def pull_repositories(current: Path, options: GitOptions) -> tuple[int, int]:
    """
    Pull all git repositories in the current path, optionally recursively.

    Parameters
    ----------
    current : Path
        The path to search for git repositories.
    options : GitOptions
        Options for the git operation.

    Returns
    -------
    tuple[int, int]
        A tuple containing (successful_pulls, failed_pulls)
    """
    successful = 0
    failed = 0

    console = options.console
    verbose = options.verbose
    recursive = options.recursive

    if verbose and console:
        console.print(f"[blue]ℹ[/blue] Checking path: [bold]{current}[/bold]")

    if is_git_repository(current):
        if verbose and console:
            console.print(
                f"[blue]ℹ[/blue] Found git repository at [bold]{current}[/bold]"
            )
        s, f = process_git_repo(current, options)
        successful += s
        failed += f
    else:
        # Check immediate subdirectories
        found_repos = False
        subdirs = list(get_subdirectories(current))

        if verbose and console:
            console.print(
                f"[blue]ℹ[/blue] Found {len(subdirs)} subdirectories in [bold]{current}[/bold]"
            )

        for path in subdirs:
            if is_git_repository(path):
                if verbose and console:
                    console.print(
                        f"[blue]ℹ[/blue] Found git repository at [bold]{path}[/bold]"
                    )
                s, f = process_git_repo(path, options)
                successful += s
                failed += f
                found_repos = True
            elif recursive:
                # Only go deeper if recursive is True
                s, f = pull_repositories(path, options)
                successful += s
                failed += f
                found_repos = found_repos or (s > 0 or f > 0)

        if not found_repos and not recursive and console:
            console.print(
                f"[yellow]![/yellow] No git repositories found in [bold]{current}[/bold]."
            )

    return successful, failed


def print_summary(successful: int, failed: int, console: Console) -> None:
    """
    Print a summary table of the pull operations.

    Parameters
    ----------
    successful : int
        Number of successful pull operations.
    failed : int
        Number of failed pull operations.
    console : Console
        Rich console for formatted output.
    """
    table = Table(title="Summary")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")

    table.add_row("Successful", f"[green]{successful}[/green]")
    table.add_row("Failed", f"[red]{failed}[/red]")
    table.add_row("Total", f"{successful + failed}")

    console.print(table)


@click.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=Path.cwd(),
    required=False,
)
@click.option(
    "--recursive/--no-recursive",
    "-r/-n",
    default=True,
    help="Recursively search for git repositories in subdirectories",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
def main(directory: Path, recursive: bool, verbose: bool):
    """
    Pull the latest changes from all git repositories in the specified directory.

    If no directory is specified, the current working directory is used.
    """
    console = Console()

    console.print(
        Panel.fit(
            "[bold blue]Git Pull Batch[/bold blue]",
            subtitle=f"Directory: [cyan]{directory}[/cyan]",
        )
    )

    options = GitOptions(console=console, verbose=verbose, recursive=recursive)

    if verbose:
        console.print(f"[blue]ℹ[/blue] Verbose mode: [green]{verbose}[/green]")
        console.print(f"[blue]ℹ[/blue] Recursive mode: [green]{recursive}[/green]")

    successful, failed = pull_repositories(directory, options)

    print_summary(successful, failed, console)


if __name__ == "__main__":
    main()
