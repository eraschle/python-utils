# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "click",
# ]
# ///
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import click

GLOBAL_IGNORE_URL = "https://raw.githubusercontent.com/eraschle/python-utils/refs/heads/master/env_backup_global_ignore.txt"


def get_global_ignore_list(fetch_url: str) -> tuple:
    """Fetches the global ignore list from a URL.

    Params:
    fetch_url (str): URL to fetch the global ignore list from.

    Returns:
    set: A set of environment variable names to ignore (case-insensitive).
    """
    try:
        response = subprocess.run(
            ["curl", "-s", fetch_url], capture_output=True, text=True, check=True
        )
        return tuple(set(response.stdout.splitlines()))
    except subprocess.CalledProcessError as e:
        print(f"Error fetching global ignore list: {e}", file=sys.stderr)
        return tuple()


def save_environment_variables(env_vars: dict[str, str], env_file: str) -> None:
    """Save environment variables to a JSON file

    Params:
    env_vars (dict): Environment variables to save.
    env_file (str): Path to the JSON file for storing environment variables.
    """
    try:
        with open(env_file, "w", encoding="utf-8") as f:  # open file for writing
            json.dump(env_vars, f, indent=2, sort_keys=True)
    except IOError as e:
        print(
            f"Error: Could not write to file {env_file}. Check permissions or path.",
            file=sys.stderr,
        )
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during file writing: {e}", file=sys.stderr)
        sys.exit(1)


def load_environment_variables(env_file: Path) -> dict[str, str] | None:
    """Load environment variables from a JSON file

    Params:
    env_file (str): Path to the JSON file containing the stored environment variables.

    Returns:
    dict: Loaded environment variables.
    """
    try:
        with open(env_file, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"Error: File not found: {env_file}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {env_file}", file=sys.stderr)
        return None
    except IOError as e:
        print(f"Error: Could not read file {env_file}. Details: {e}", file=sys.stderr)
        return None


def _backup_env_vars(env_to_ignore: tuple) -> dict[str, str]:
    """Filters environment variables based on 1Password values and the ignore list."""
    vars_to_store: dict[str, str] = {}
    ignored_names = []

    to_ignore = {str(var).lower() for var in env_to_ignore}
    for key, value in os.environ.items():
        if key.lower() in to_ignore:
            ignored_names.append(key)
            continue

        vars_to_store[key] = value
    return vars_to_store


@click.group()
def cli():
    """Manages backing up and restoring environment variables, optionally using 1Password."""
    pass


@cli.command()
@click.argument(
    "env_file",
    required=True,
    type=click.Path(dir_okay=False, writable=True, resolve_path=True),
)
@click.option(
    "--ignore",
    "-i",
    multiple=True,
    metavar="VAR_NAME",
    help="Environment variable names to ignore (case-insensitive). Can be used multiple times.",
)
@click.option(
    "--url",
    default=GLOBAL_IGNORE_URL,
    help="Url to fetch the global ignore list. (default: URL of global ignore list from GitHub)",
)
@click.option(
    "--no-global-ignore",
    flag_value=True,
    default=False,
    help="Disable the global ignore list. (default: False)",
)
def backup(env_file: str, ignore: tuple, url: str, no_global_ignore: bool) -> None:
    """BACKUP: Saves environment variables to a JSON file, excluding specified variables.

    params:
    env_file (str): Path to the JSON file for storing environment variables.
    to_ignore (set): [Optional] Environment variable names to ignore (case-insensitive). Can be used multiple times.
    url (str): [Optional] URL to fetch the global ignore list. (default: URL of global ignore list from GitHub)
    no_global_ignore (bool): [Optional] Disable the global ignore list (default: False).
    """
    if not no_global_ignore:
        global_ignore = get_global_ignore_list(url)
        ignore = ignore + tuple(global_ignore)
    print(f"Backup environment variables to {env_file}")
    vars_to_store = _backup_env_vars(env_to_ignore=ignore)
    count_env_vars = len(os.environ)
    count_ignored = count_env_vars - len(vars_to_store)
    print(f"- Total:   {count_env_vars}")
    print(f"- Ignored: {count_ignored}")
    print(f"- Saved:   {len(vars_to_store)}")
    save_environment_variables(vars_to_store, env_file)


def set_envvar_linux(env_name: str, value: Any) -> int:
    os.environ[env_name] = value
    return 0


def set_envvar_windows(env_name: str, value: Any) -> int:
    command = f'setx {env_name} "{value}"'
    process = subprocess.Popen(
        command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    return process.wait()


def set_environment_variable(env_name: str, value: Any) -> None:
    """ "Set an environment variable in the current session and system-wide.

    Params:
    env_name (str): Name of the environment variable.
    value (Any): Value of the environment variable.
    """
    try:
        if env_name in os.environ:
            print(
                f"Updating existing variable {env_name} from {os.environ[env_name]} to {value}"
            )
        else:
            print(f"Creating new variable {env_name} with value {value}")
        if sys.platform == "win32":
            set_envvar_windows(env_name, value)
        elif sys.platform == "linux":
            return set_envvar_linux(env_name, value)
        else:
            print(f"Unsupported platform: {sys.platform}", file=sys.stderr)
            sys.exit(1)
    except Exception as e:
        print(f"Error setting variable {env_name}: {e}", file=sys.stderr)
        sys.exit(1)


@cli.command()
@click.argument(
    "env_file",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    "--overwrite",
    flag_value=True,
    help="Overwrite existing environment variables. Default is False.",
)
def restore(env_file: Path, overwrite: bool) -> None:
    """RESTORE: Restores environment variables from a JSON file.
    Overrides existing variables if override is set to True.

    Params:
    env_file (str): Path to the JSON file containing the stored environment variables.
    overwrite (bool): Whether to overwrite existing environment variables.
    """
    loaded_vars = load_environment_variables(env_file)
    if loaded_vars is None:
        sys.exit(1)

    count_restored = 0
    count_overwritten = 0

    for key, value in loaded_vars.items():
        if not overwrite and key in os.environ:
            print(f"Skipping existing variable: {key} with value {value}")
            continue
        count_restored += 1
        if overwrite and key in os.environ:
            count_overwritten += 1
        set_environment_variable(key, value)

    print("Zusammenfassung der Wiederherstellung:")
    print(f"Restored {count_restored} environment variables.")
    if count_overwritten > 0:
        print(f"Overwritten {count_overwritten} existing environment variables.")


if __name__ == "__main__":
    cli()
