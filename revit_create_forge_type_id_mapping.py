# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
# ]
# ///

import json
import os
from pathlib import Path
from typing import Literal
import click
import sys

Language = Literal["de-DE", "en-us"]


def _get_revit_shared_path() -> Path:
    """
    Get the Revit shared path from environment variables.

    Returns
    -------
    Path
        Path to the Autodesk Shared directory

    Raises
    ------
    EnvironmentError
        If ProgramFiles environment variable is not set
    """
    programm_files = os.getenv("ProgramFiles", "")
    if not programm_files:
        raise EnvironmentError("ProgramFiles environment variable is not set.")
    subpaths = ["Common Files", "Autodesk Shared"]
    return Path(programm_files).joinpath(*subpaths)


def _get_revit_versions() -> list[int]:
    """
    Get all available Revit versions from the shared directory.

    Returns
    -------
    list[int]
        Sorted list of available Revit version numbers
    """
    schema_prefix = "Revit Schemas "
    versions = []
    for item in _get_revit_shared_path().iterdir():
        if item.is_file() or not item.name.startswith(schema_prefix):
            continue
        version_str = item.name[len(schema_prefix) :]
        versions.append(int(version_str))
    return sorted(versions)


def _get_location_schmema_path(version: int) -> Path:
    """
    Get the localization schema path for a specific Revit version.

    Parameters
    ----------
    version : int
        Revit version number

    Returns
    -------
    Path
        Path to the localization directory for the specified version

    Raises
    ------
    FileNotFoundError
        If the localization path does not exist
    """
    subpaths = [f"Revit Schemas {version}", "Localization"]
    dir_path = _get_revit_shared_path().joinpath(*subpaths)
    if not dir_path.exists():
        raise FileNotFoundError(f"Localization path does not exist: {dir_path}")
    return dir_path


def _get_type_mapping(json_data: dict) -> dict[str, str]:
    """
    Extract type mapping from JSON data.

    Parameters
    ----------
    json_data : dict
        JSON data containing type information

    Returns
    -------
    dict[str, str]
        Mapping from name to type ID
    """
    type_id = json_data.get("origin", "NO_TYPE_ID")
    constants = json_data.get("constants", [])
    name = "NO_NAME"
    for constant in constants:
        if "id" not in constant or constant["id"] != "name":
            continue
        name = constant.get("value", "NO_NAME")
    return {name: type_id}


def _read_json_file(file_path: Path) -> dict:
    """
    Read and parse a JSON file.

    Parameters
    ----------
    file_path : Path
        Path to the JSON file

    Returns
    -------
    dict
        Parsed JSON data
    """
    with open(file_path, "r", encoding="utf-8") as json_file:
        return json.loads(json_file.read())


def _create_type_mapping(path: Path) -> dict[str, str]:
    """
    Create type mapping from all JSON files in a directory.

    Parameters
    ----------
    path : Path
        Directory path containing JSON files

    Returns
    -------
    dict[str, str]
        Combined type mapping from all JSON files
    """
    type_mapping = {}
    for json_file in path.rglob("*.json"):
        if not json_file.is_file():
            continue
        json_data = _read_json_file(json_file)
        type_mapping.update(_get_type_mapping(json_data))
    return type_mapping


def _get_display_group_mapping(group_path: Path, language: list[Language]) -> dict[str, dict[str, str]]:
    """
    Get display group mapping for specified languages.

    Parameters
    ----------
    group_path : Path
        Path to the group directory
    language : list[Language]
        List of language codes

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping with setting_group as key and language mappings as values
    """
    group_mapping = {}
    for lang in language:
        lang_path = group_path.joinpath(lang)
        group_mapping[lang] = _create_type_mapping(lang_path)
    return {"setting_group": group_mapping}


def _get_parameter_group_mapping(group_path: Path, language: list[Language]) -> dict[str, dict[str, str]]:
    """
    Get parameter group mapping for specified languages.

    Parameters
    ----------
    group_path : Path
        Path to the parameter directory
    language : list[Language]
        List of language codes

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping with parameter_group as key and language mappings as values
    """
    group_mapping = {}
    for lang in language:
        lang_path = group_path.joinpath(lang)
        group_mapping[lang] = _create_type_mapping(lang_path)
    return {"parameter_group": group_mapping}


def _get_data_type_mapping(spec_path: Path, language: list[Language]) -> dict[str, dict[str, str]]:
    """
    Get data type mapping for specified languages.

    Parameters
    ----------
    spec_path : Path
        Path to the spec directory
    language : list[Language]
        List of language codes

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping with data_type as key and language mappings as values
    """
    spec_mapping = {}
    for lang in language:
        lang_path = spec_path.joinpath(lang)
        spec_mapping[lang] = _create_type_mapping(lang_path)
    return {"data_type": spec_mapping}


def _get_unit_mapping(unit_path: Path, language: list[Language]) -> dict[str, dict[str, str]]:
    """
    Get unit mapping for specified languages.

    Parameters
    ----------
    unit_path : Path
        Path to the unit directory
    language : list[Language]
        List of language codes

    Returns
    -------
    dict[str, dict[str, str]]
        Nested mapping with units as key and language mappings as values
    """
    unit_mapping = {}
    for lang in language:
        lang_path = unit_path.joinpath(lang)
        unit_mapping[lang] = _create_type_mapping(lang_path)
    return {"units": unit_mapping}


def _setup_logging(verbose: bool) -> None:
    """
    Setup logging configuration based on verbosity level.

    Parameters
    ----------
    verbose : bool
        If True, enable debug logging; otherwise use info level
    """
    import logging

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")


def _validate_languages(ctx, param, value):
    """
    Validate language codes against supported languages.

    Parameters
    ----------
    ctx : click.Context
        Click context object
    param : click.Parameter
        Click parameter object
    value : tuple
        Language codes to validate

    Returns
    -------
    tuple
        Validated language codes

    Raises
    ------
    click.BadParameter
        If any language code is not supported
    """
    valid_languages = ["de-DE", "en-us"]
    for lang in value:
        if lang not in valid_languages:
            raise click.BadParameter(f"Ungültige Sprache: {lang}. Gültige Optionen: {', '.join(valid_languages)}")
    return value


def _validate_output_directory(ctx, param, value):
    """
    Validate and create output directory if it doesn't exist.

    Parameters
    ----------
    ctx : click.Context
        Click context object
    param : click.Parameter
        Click parameter object
    value : str
        Output directory path

    Returns
    -------
    Path
        Validated output directory path

    Raises
    ------
    click.BadParameter
        If directory cannot be created or path is not a directory
    """
    path = Path(value)
    if not path.exists():
        try:
            path.mkdir(parents=True, exist_ok=True)
            if ctx.obj and ctx.obj.get("verbose"):
                click.echo(f"Ausgabeverzeichnis erstellt: {path}")
        except Exception as e:
            raise click.BadParameter(f"Kann Ausgabeverzeichnis nicht erstellen: {e}")
    elif not path.is_dir():
        raise click.BadParameter(f"Pfad ist kein Verzeichnis: {path}")
    return path


def create_mapping(languages: list[Language], out_directory: Path, verbose: bool = False) -> None:
    """
    Create a mapping of type IDs to names for specified languages.

    Parameters
    ----------
    languages : list[Language]
        List of language codes to process
    out_directory : Path
        Output directory for the mapping file
    verbose : bool, optional
        Enable verbose logging, by default False

    Notes
    -----
    Creates a JSON file named 'revit_mapping.json' in the output directory
    containing mappings for all found Revit versions.
    """
    import logging

    logger = logging.getLogger(__name__)

    if verbose:
        logger.info(f"Starte Mapping-Erstellung für Sprachen: {', '.join(languages)}")
        logger.info(f"Ausgabeverzeichnis: {out_directory}")

    path_for_mapping = {
        "parameter": _get_parameter_group_mapping,
        "revit/group": _get_display_group_mapping,
        "spec": _get_data_type_mapping,
        "unit/unit": _get_unit_mapping,
    }
    mapping = {}

    revit_versions = _get_revit_versions()
    if verbose:
        logger.info(f"Gefundene Revit-Versionen: {revit_versions}")

    for revit_version in revit_versions:
        if verbose:
            logger.info(f"Verarbeite Revit-Version: {revit_version}")

        localization_path = _get_location_schmema_path(version=revit_version)
        version_mapping = {}

        for subpath, callback_func in path_for_mapping.items():
            search_path = localization_path.joinpath(subpath)
            if verbose:
                logger.debug(f"Verarbeite Pfad: {search_path}")
            version_mapping.update(callback_func(search_path, languages))

        if not version_mapping:
            if verbose:
                logger.warning(f"Keine Mappings für Version {revit_version} gefunden")
            return
        mapping[f"{revit_version}"] = version_mapping

    out_file_path = out_directory.joinpath("revit_mapping.json")
    with open(out_file_path, "w", encoding="utf-8") as json_file:
        json.dump(mapping, json_file, indent=2, ensure_ascii=False)

    if verbose:
        logger.info(f"Mapping erfolgreich erstellt: {out_file_path}")


@click.command()
@click.option(
    "--languages",
    "-l",
    multiple=True,
    default=["de-DE", "en-us"],
    callback=_validate_languages,
    help="Sprachen für das Mapping (Standard: de-DE, en-us). Kann mehrfach verwendet werden.",
)
@click.option(
    "--output",
    "-o",
    default=".",
    callback=_validate_output_directory,
    help="Ausgabeverzeichnis für die Mapping-Datei (Standard: aktuelles Verzeichnis)",
)
@click.option("--verbose", "-v", is_flag=True, help="Ausführliche Ausgabe aktivieren")
@click.pass_context
def main_cli(ctx, languages, output, verbose):
    """
    Erstellt ein Revit-Mapping von Typ-IDs zu Namen.

    Diese Anwendung durchsucht die installierten Revit-Versionen und erstellt
    ein JSON-Mapping für Parameter, Gruppen, Datentypen und Einheiten.
    """
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    _setup_logging(verbose)

    output = output.resolve().absolute()
    try:
        if verbose:
            click.echo("Starte Revit-Mapping-Erstellung...")
            click.echo(f"Sprachen: {', '.join(languages)}")
            click.echo(f"Ausgabeverzeichnis: {output}")

        create_mapping(list(languages), output, verbose)

        output_file = output / "revit_mapping.json"
        click.echo(f"[ERFOLG] Mapping erfolgreich erstellt: {output_file}")

    except FileNotFoundError as e:
        click.echo(f"[FEHLER] Datei nicht gefunden: {e}", err=True)
        sys.exit(1)
    except EnvironmentError as e:
        click.echo(f"[FEHLER] Umgebungsfehler: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"[FEHLER] Unerwarteter Fehler: {e}", err=True)
        if verbose:
            import traceback

            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


if __name__ == "__main__":
    main_cli()
