# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "1password", # Note: 1password dependency seems unrelated to the current task, but kept as per original file
#     "click",
# ]
# ///
import os
import json
import click
import sys  # Added for error output
import subprocess
from typing import Any
from collections.abc import Mapping  # Import Mapping from collections.abc

# List of environment variable names to ignore during backup and restore
IGNORED_ENV_VARS = [
    # Examples (add more as needed):
    "PWD",
    "OLDPWD",
    "_",  # Often holds the last command in bash/zsh
    "PROMPT_COMMAND",
    "PS1",
    "PS2",
    "PS3",
    "PS4",  # Shell prompts
    "TMP",  # Windows temporary directories
    "USERPROFILE",  # Windows user home
    "APPDATA",  # Windows application data
    "LOCALAPPDATA",  # Windows local application data
    "PROGRAMDATA",  # Windows program data
    "ALLUSERSPROFILE",  # Windows all users profile
    "HOMEDRIVE",
    "HOMEPATH",  # Windows home location components
    "COMPUTERNAME",
    "HOSTNAME",  # System names
    "SESSIONNAME",  # Windows session name
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",  # System hardware info
    "PATH",
    "Path",  # System execution path (often complex and managed differently)
    "PYTHONPATH",  # Python specific path
    "CONDA_PREFIX",
    "CONDA_DEFAULT_ENV",  # Conda environment specifics
    "VIRTUAL_ENV",  # Python virtual environment indicator
    "LANG",
    "LC_ALL",
    "LC_CTYPE",  # Locale settings
    "TERM",
    "COLORTERM",  # Terminal type
    "DISPLAY",  # X11 display
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_ID",  # Linux session info
    "DBUS_SESSION_BUS_ADDRESS",  # Linux D-Bus info
    "SSH_CLIENT",
    "SSH_CONNECTION",
    "SSH_TTY",  # SSH session info
    "SHELL",  # Default shell
    "HOME",  # User home directory (Linux/macOS)
    "LOGNAME",
    "USER",  # User login name
    "SHLVL",  # Shell level
    "WINDOWID",  # Window ID (graphical environments)
    "_",  # Often last command or script name
]
# Ensure case-insensitivity for comparison later, especially for Windows keys
IGNORED_ENV_VARS_LOWER: set[str] = {var.lower() for var in IGNORED_ENV_VARS}

# Value to replace secrets found in 1Password
REDACTED_VALUE: str = "MEIN-GEHEIMNISS"


def get_1password_values(op_vault: str) -> set[str] | None:
    """Retrieves all values from a 1Password vault. Returns None on error."""
    op_item_values: set[str] = set()

    print(f"Checking environment variable values against 1Password items in vault '{op_vault}'...")
    try:
        # Get all items from the vault
        result = subprocess.run(
            ["op", "item", "list", f"--vault={op_vault}", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        items: list[dict[str, Any]] = json.loads(result.stdout)

        # Extract values from each item
        print(f"Retrieving details for {len(items)} items from vault '{op_vault}'...")
        processed_count = 0
        for item in items:
            # Get item details to access fields
            detail_result = subprocess.run(
                ["op", "item", "get", item["id"], f"--vault={op_vault}", "--format=json"],
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )
            item_details: dict[str, Any] = json.loads(detail_result.stdout)

            # Extract values from fields and notes
            for field in item_details.get("fields", []):
                field_value = field.get("value")
                if field_value is not None:  # Ensure value exists
                    op_item_values.add(str(field_value))  # Add field value as string
            notes_value = item_details.get("notes")
            if notes_value:
                op_item_values.add(str(notes_value))  # Add notes as string

            processed_count += 1
            if processed_count % 50 == 0:  # Print progress for large vaults
                print(f"  Processed {processed_count}/{len(items)} items...")

        print(f"Found {len(op_item_values)} unique values in vault '{op_vault}'.")
        return op_item_values

    except FileNotFoundError:
        print(
            "Error: 'op' command not found. Is the 1Password CLI installed and in your PATH?",
            file=sys.stderr,
        )
        return None
    except subprocess.CalledProcessError as e:
        print(
            "Error executing 'op' command. Is the vault name correct? Are you logged in?",
            file=sys.stderr,
        )
        print(f"Details: {e.stderr}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print("Error: Could not parse JSON output from 'op' command.", file=sys.stderr)
        return None
    except Exception as e:
        print(f"An unexpected error occurred during 1Password check: {e}", file=sys.stderr)
        return None


def get_1password_secret_value(variable_name: str, op_vault: str) -> str | None:
    """Retrieves the secret value for a specific variable name from 1Password."""
    print(f"  Attempting to retrieve secret for '{variable_name}' from vault '{op_vault}'...")
    # Note: op read might fail if the item isn't a Login or doesn't have a 'password' field
    # We'll fall back to 'op item get' if this fails or returns nothing useful.
    try:
        # Try reading the 'password' field directly first (common for Login items)
        try:
            result = subprocess.run(
                ["op", "read", f"op://{op_vault}/{variable_name}/password"],
                capture_output=True,
                text=True,
                check=False,
                encoding="utf-8",  # check=False initially
            )  # try to read password field directly
            if result.returncode == 0 and result.stdout.strip():
                print(f"    Found value for '{variable_name}' using 'op read'.")
                return result.stdout.strip()
            # If op read failed or returned empty, proceed to op item get
        except FileNotFoundError:
            print("Error: 'op' command not found.", file=sys.stderr)
            return None

        # Fallback: Get the full item details and look for a suitable field
        print(
            f"    'op read' failed or yielded no value for '{variable_name}', trying 'op item get'..."
        )
        detail_result = subprocess.run(
            ["op", "item", "get", variable_name, f"--vault={op_vault}", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
            encoding="utf-8",
        )
        item_details: dict[str, Any] = json.loads(detail_result.stdout)

        # Prioritize 'password' field within the details if available
        for field in item_details.get("fields", []):
            if field.get("id") == "password" or field.get("label") == "password":
                value = field.get("value")
                if value:
                    print(f"    Found 'password' field value for '{variable_name}'.")
                    return str(value)

        # If no password field, return the first field value found (simple heuristic)
        for field in item_details.get("fields", []):
            value = field.get("value")
            if value:
                print(f"    Found first field value for '{variable_name}'.")
                return str(value)

        print(
            f"    Warning: No suitable field value found for '{variable_name}' in item details.",
            file=sys.stderr,
        )
        return None  # No suitable value found in details

    except subprocess.CalledProcessError as e:  # catch error if 1password cli returns an error
        # Handle cases where the item might not be found by 'op item get'
        if "isn't an item in vault" in e.stderr or "No item found" in e.stderr:
            print(
                f"    Info: Item '{variable_name}' not found in vault '{op_vault}'.",
                file=sys.stderr,
            )  # info message when item is not found
        else:
            print(
                f"    Error executing 'op item get' for '{variable_name}': {e.stderr}",
                file=sys.stderr,
            )  # error message for other errors
        return None
    except json.JSONDecodeError:  # catch json decode errors
        print(
            f"    Error: Could not parse JSON from 'op item get' for '{variable_name}'.",
            file=sys.stderr,
        )  # json error message
        return None
    except Exception as e:  # catch all other exceptions
        print(
            f"    An unexpected error occurred retrieving secret for '{variable_name}': {e}",
            file=sys.stderr,
        )  # unexpected error message
        return None


def filter_environment_variables(  # function to filter environment variables
    env_vars: Mapping[str, str],
    op_item_values: set[str],
    check_1password: bool,
) -> dict[str, str]:
    """Filters environment variables based on 1Password values and the ignore list."""
    vars_to_store: dict[str, str] = {}
    count_ignored_list: int = 0
    count_ignored_op: int = 0

    print("Filtering environment variables...")
    for key, value in env_vars.items():
        # Check 1: Redact value if it matches a 1Password item value (if check enabled)
        # Ensure value is treated as string for comparison, as op_item_values contains strings
        value_str: str = str(value) if value is not None else ""
        if check_1password and value_str in op_item_values:
            count_ignored_op += 1
            vars_to_store[key] = REDACTED_VALUE  # Store redacted value

        # Check 2: Skip if name is in the ignored list (use elif for mutual exclusion)
        elif key.lower() in IGNORED_ENV_VARS_LOWER:
            count_ignored_list += 1
            continue  # Skip variable from ignore list

        # If not skipped, add to dictionary
        vars_to_store[key] = value  # os.environ provides strings, so value is already str

    print(f"Found {len(vars_to_store)} variables to save.")
    if check_1password:
        # Note: op_vault name is not passed here, so the message is slightly adjusted
        print(f"Ignored {count_ignored_op} variables matching 1Password values.")
    print(f"Ignored {count_ignored_list} variables from the predefined ignore list.")

    return vars_to_store


def save_environment_variables(
    env_vars: dict[str, str], env_file: str
) -> None:  # function to save environment variables to json file
    """Saves environment variables to a JSON file."""
    print(f"Saving variables to {env_file}...")
    try:
        with open(env_file, "w", encoding="utf-8") as f:  # open file for writing
            json.dump(env_vars, f, indent=4, sort_keys=True)
        print(f"Successfully saved environment variables to {env_file}")
    except IOError as e:
        print(
            f"Error: Could not write to file {env_file}. Check permissions or path.",
            file=sys.stderr,
        )
        print(f"Details: {e}", file=sys.stderr)
        sys.exit(1)  # Exit with error code
    except Exception as e:
        print(f"An unexpected error occurred during file writing: {e}", file=sys.stderr)
        sys.exit(1)  # Exit with error code


def load_environment_variables(
    env_file: str,
) -> dict[str, str] | None:  # function to load environment variables from json file
    """Loads environment variables from a JSON file."""
    print(f"Loading variables from {env_file}...")
    try:
        with open(env_file, "r", encoding="utf-8") as f:  # open file for reading
            loaded_vars: dict[str, str] = json.load(f)
        print(f"Successfully loaded {len(loaded_vars)} variables from {env_file}")
        return loaded_vars
    except FileNotFoundError:
        print(f"Error: File not found: {env_file}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from file: {env_file}", file=sys.stderr)
        return None
    except IOError as e:
        print(f"Error: Could not read file {env_file}. Details: {e}", file=sys.stderr)
        return None


@click.group()
def cli():
    """Manages backing up and restoring environment variables, optionally using 1Password."""  # cli group help text
    pass  # Group function doesn't need implementation here


# Backup Command
@cli.command()  # Add backup command to the cli group
@click.option(
    "--check-1password",
    is_flag=True,
    default=False,
    help="Enable checking environment variable values against 1Password item values.",
)
@click.option(
    "--op-vault",
    metavar="VAULT_NAME",
    default=None,
    help="The 1Password vault name to check against. Required if --check-1password is set.",
)
@click.option(
    "--env-file",
    required=True,
    type=click.Path(
        dir_okay=False, writable=True, resolve_path=True
    ),  # Added resolve_path for clarity
    help="Path to the JSON file for storing/reading environment variables.",
)
def backup(env_file: str, check_1password: bool, op_vault: str | None) -> None:
    """BACKUP: Reads current environment variables, optionally filters out those with
    values matching 1Password item values, filters out ignored ones, and saves the rest
    to a specified JSON file."""
    print("Reading environment variables...")

    # os.environ is already a mapping, which matches Mapping[str, str]
    env_vars: Mapping[str, str] = os.environ

    # Initialize as empty set, use built-in set for type hint
    op_item_values: set[str] | None = set()
    if check_1password:
        if not op_vault:  # Check required vault if flag is set
            print(
                "Error: --op-vault is required when --check-1password is enabled.", file=sys.stderr
            )
            sys.exit(1)  # Exit here if vault name is missing but check is requested
        op_item_values = get_1password_values(op_vault)
        if op_item_values is None:
            print("Exiting due to error during 1Password value retrieval.", file=sys.stderr)
            # Note: The sys.exit(1) call here was removed based on the second diff provided.
            sys.exit(1)  # Exit here if vault name is missing but check is requested
    # op_item_values is either a set[str] or an empty set if check_1password is False
    vars_to_store: dict[str, str] = filter_environment_variables(
        env_vars, op_item_values, check_1password
    )

    save_environment_variables(vars_to_store, env_file)


# Restore Command
@cli.command()  # Add restore command to the cli group
@click.option(
    "--env-file",
    required=True,
    type=click.Path(
        exists=True, dir_okay=False, readable=True, resolve_path=True
    ),  # Must exist for reading
    help="Path to the JSON file containing the stored environment variables.",
)
@click.option(
    "--op-vault",
    required=True,  # Required for looking up redacted values
    metavar="VAULT_NAME",
    help="The 1Password vault name to retrieve redacted secrets from.",
)
def restore(env_file: str, op_vault: str) -> None:
    """RESTORE: Reads variables from a file, retrieves redacted values from
    1Password, and outputs 'export' commands to set them."""
    loaded_vars = load_environment_variables(env_file)
    if loaded_vars is None:
        sys.exit(1)  # Exit if loading failed

    print('\nGenerating export commands (run with eval "$(...)"):')
    count_restored = 0
    count_redacted_found = 0
    count_redacted_not_found = 0

    for key, value in loaded_vars.items():
        if value == REDACTED_VALUE:
            # Value was redacted, try to get secret from 1Password
            secret_value = get_1password_secret_value(key, op_vault)
            if secret_value is not None:
                # Escape potential double quotes within the value for safety
                escaped_value = secret_value.replace('"', '\\"')
                print(f'export {key}="{escaped_value}"')
                count_redacted_found += 1
            else:
                # Secret not found in 1Password for this key
                print(  # print warning if secret is not found
                    f"# Warning: Secret for '{key}' marked as redacted, but not found in vault '{op_vault}'. Skipping.",
                    file=sys.stderr,
                )
                count_redacted_not_found += 1
        else:
            # Value is not redacted, use it directly
            # Escape potential double quotes within the value for safety
            escaped_value = value.replace('"', '\\"')
            print(f'export {key}="{escaped_value}"')
            count_restored += 1

    print("\n--- Summary ---", file=sys.stderr)
    print(f"Generated commands for {count_restored} directly restored variables.", file=sys.stderr)
    print(
        f"Retrieved {count_redacted_found} secrets from 1Password for redacted variables.",
        file=sys.stderr,
    )
    if count_redacted_not_found > 0:
        print(
            f"Warning: Could not find secrets for {count_redacted_not_found} redacted variables in vault '{op_vault}'.",
            file=sys.stderr,
        )
    print("\nRun the output commands in your shell, e.g., using 'eval \"$(...)\"'", file=sys.stderr)


# Apply Command
@cli.command()
@click.option(
    "--env-file",
    required=True,
    type=click.Path(
        exists=True, dir_okay=False, readable=True, resolve_path=True
    ),  # Muss für das Lesen existieren
    help="Pfad zur JSON-Datei, die die gespeicherten Umgebungsvariablen enthält.",
)
@click.option(
    "--op-vault",
    required=True,  # Erforderlich, um nach redigierten Werten zu suchen
    metavar="VAULT_NAME",
    help="Der Name des 1Password-Vaults, aus dem redigierte Geheimnisse abgerufen werden sollen.",
)
def apply(env_file: str, op_vault: str) -> None:
    """APPLY: Liest Variablen aus einer Datei, ruft redigierte Werte von
    1Password ab und setzt sie direkt als Umgebungsvariablen im aktuellen Prozess."""
    loaded_vars = load_environment_variables(env_file)
    if loaded_vars is None:
        sys.exit(1)  # Beenden, wenn das Laden fehlschlägt

    print("\nWende Umgebungsvariablen an...")
    count_applied = 0
    count_redacted_found = 0
    count_redacted_not_found = 0
    # Need to define count_restored before using it in the summary print statement
    count_restored = 0  # Initialize count_restored

    for key, value in loaded_vars.items():
        if value == REDACTED_VALUE:
            # Value is redacted, try to get secret from 1Password
            secret_value = get_1password_secret_value(key, op_vault)
            if secret_value is not None:
                os.environ[key] = secret_value  # Setze die Umgebungsvariable direkt
                count_redacted_found += 1
                count_applied += 1
            else:
                # Geheimnis in 1Password für diesen Schlüssel nicht gefunden
                print(  # print warning if secret is not found
                    f"# Warnung: Geheimnis für '{key}' als redigiert markiert, aber nicht im Vault '{op_vault}' gefunden. Überspringe.",
                    file=sys.stderr,
                )
                count_redacted_not_found += 1
        else:
            # Wert ist nicht redigiert, verwende ihn direkt
            os.environ[key] = value  # Setze die Umgebungsvariable direkt
            count_applied += 1
            count_restored += 1  # Increment count_restored for non-redacted variables

    print("\n--- Zusammenfassung ---", file=sys.stderr)
    print(f"{count_applied} Umgebungsvariablen angewendet.", file=sys.stderr)

    # Corrected the summary print statement to use the initialized and incremented count_restored
    print(f"Davon {count_restored} Variablen direkt aus der Datei.", file=sys.stderr)
    print(
        f"Und {count_redacted_found} Geheimnisse erfolgreich von 1Password abgerufen und angewendet.",
        file=sys.stderr,
    )
    if count_redacted_not_found > 0:
        print(
            f"Warnung: Konnte {count_redacted_not_found} redigierte Geheimnisse nicht im Vault '{op_vault}' finden.",
            file=sys.stderr,
        )
    if count_applied > 0:
        print("\nUmgebungsvariablen wurden im aktuellen Prozess gesetzt.", file=sys.stderr)
    else:
        print("\nKeine Umgebungsvariablen wurden gesetzt.", file=sys.stderr)
        if count_redacted_not_found > 0:
            print("Aufgrund fehlender Geheimnisse in 1Password.", file=sys.stderr)
        else:
            print(
                "Datei enthielt keine Umgebungsvariablen oder Fehler beim Lesen.", file=sys.stderr
            )


if __name__ == "__main__":
    cli()
