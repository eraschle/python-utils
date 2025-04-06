# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "click",
#     "rich",
# ]
# ///
import os
import subprocess
import shutil
import platform
from dataclasses import dataclass
from pathlib import Path

import click
from rich.console import Console


@dataclass
class GitOptions:
    """Optionen für Git-Operationen."""

    extensions: list[str] | None = None
    line_ending: str = "crlf"
    cleanup: bool = True
    verbose: bool = False
    force: bool = False
    continue_process: bool = True
    should_overwrite: bool = True

    def __post_init__(self):
        if self.extensions is None:
            self.extensions = []


def run_git_command(
    console: Console, command: list[str], options: GitOptions, error_message: str
) -> tuple[bool, subprocess.CompletedProcess | None]:
    """
    Führt einen Git-Befehl aus und gibt das Ergebnis zurück.

    Args:
        console: Console-Objekt für die Ausgabe
        command: Liste mit dem auszuführenden Befehl und seinen Argumenten
        options: GitOptions mit Konfigurationsoptionen
        error_message: Fehlermeldung, die bei einem Fehler angezeigt werden soll

    Returns:
        Tuple mit einem Boolean (True bei Erfolg, False bei Fehler) und dem CompletedProcess-Objekt (oder None bei Fehler)
    """
    try:
        result = subprocess.run(command, check=True, capture_output=True)

        if options.verbose:
            console.print(f"[dim]Befehl: {' '.join(command)}[/]")
            console.print(
                f"[dim]Ausgabe: {result.stdout.decode() if result.stdout else 'Keine Ausgabe'}[/]"
            )

        return True, result
    except subprocess.CalledProcessError as e:
        console.print(f"[bold red]{error_message}[/] {e}")
        console.print(f"Ausgabe: {e.stdout.decode() if e.stdout else ''}")
        console.print(f"Fehler: {e.stderr.decode() if e.stderr else ''}")
        return False, None


def init_git_repo(console: Console, options: GitOptions) -> bool:
    """
    Git-Repository initialisieren.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    console.print("[bold blue]Initialisiere Git-Repository...[/]")
    success, _ = run_git_command(
        console,
        ["git", "init", "."],
        options,
        "Fehler beim Initialisieren des Git-Repositories:",
    )
    return success


def add_files_to_git(console: Console, options: GitOptions) -> bool:
    """
    Alle Dateien zum Repository hinzufügen.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    console.print("[bold blue]Füge Dateien zum Repository hinzu...[/]")
    success, _ = run_git_command(
        console,
        ["git", "add", "."],
        options,
        "Fehler beim Hinzufügen der Dateien:",
    )
    return success


def create_initial_commit(console: Console, options: GitOptions) -> bool:
    """
    Initialen Commit erstellen, aber nur wenn es Änderungen gibt.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    # Prüfen, ob es Änderungen gibt, die committet werden können
    success, result = run_git_command(
        console,
        ["git", "status", "--porcelain"],
        options,
        "Fehler beim Prüfen des Git-Status:",
    )

    if not success:
        return False

    if result is None:
        console.print(
            "[bold red]Fehler beim Prüfen des Git-Status (Result is NONE).[/]"
        )
        return False

    # Wenn keine Änderungen vorhanden sind, gibt es nichts zu committen
    if not result.stdout.strip():
        console.print("[yellow]Keine Änderungen zum Committen vorhanden.[/]")
        return True

    console.print("[bold blue]Erstelle initialen Commit...[/]")
    success, _ = run_git_command(
        console,
        ["git", "commit", "-m", "initial commit"],
        options,
        "Fehler beim Erstellen des initialen Commits:",
    )
    return success


def create_gitattributes(console: Console, options: GitOptions) -> bool:
    """
    Erstellt die .gitattributes-Datei mit den gewünschten Zeilenenden.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    try:
        console.print(
            f"[bold blue]Erstelle .gitattributes für {options.line_ending} Zeilenenden...[/]"
        )

        with open(".gitattributes", "w") as f:
            # Für jede angegebene Dateiendung eine Regel hinzufügen
            if options.extensions:
                for ext in options.extensions:
                    ext_pattern = f"*.{ext}" if not ext.startswith("*.") else ext
                    f.write(f"{ext_pattern} text eol={options.line_ending}\n")

                    if options.verbose:
                        console.print(
                            f"[dim]Regel hinzugefügt: {ext_pattern} text eol={options.line_ending}[/]"
                        )
            else:
                # Standardregel für alle Textdateien
                f.write(f"* text eol={options.line_ending}\n")

                if options.verbose:
                    console.print(
                        f"[dim]Standardregel hinzugefügt: * text eol={options.line_ending}[/]"
                    )

        return True
    except Exception as e:
        console.print(
            f"[bold red]Fehler beim Erstellen der .gitattributes-Datei:[/] {e}"
        )
        return False


def clear_git_cache(console: Console, options: GitOptions) -> bool:
    """
    Git-Cache leeren.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    console.print("[bold blue]Leere Git-Cache...[/]")
    success, _ = run_git_command(
        console,
        ["git", "rm", "--cached", "-r", "."],
        options,
        "Fehler beim Leeren des Git-Caches:",
    )
    return success


def reset_changes(console: Console, options: GitOptions) -> bool:
    """
    Änderungen zurücksetzen und Zeilenenden anpassen.

    Args:
        console: Console-Objekt für die Ausgabe
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    console.print("[bold blue]Setze Änderungen zurück und passe Zeilenenden an...[/]")
    success, _ = run_git_command(
        console,
        ["git", "reset", "--hard"],
        options,
        "Fehler beim Zurücksetzen der Änderungen:",
    )
    return success


def cleanup_git_files(console: Console, directory: Path, options: GitOptions) -> bool:
    # .gitattributes Datei löschen (erstellt durch create_gitattributes)
    # Weitere Dateien, die durch Git-Operationen in create_temp_git_repo erstellt werden könnten
    git_files = [
        ".gitattributes",
        ".gitignore",  # Könnte durch Git-Operationen erstellt werden
        ".gitmodules",  # Könnte bei Submodulen erstellt werden
        ".gitconfig",  # Könnte durch Git-Konfiguration erstellt werden
    ]

    try:
        for git_file in git_files:
            file_path = directory / git_file
            if not file_path.exists():
                continue
            if options.verbose:
                console.print(f"[dim]Lösche Datei: {file_path}[/]")
            file_path.unlink()
            console.print(f"[bold green]{git_file} wurde gelöscht.[/]")
        return True
    except Exception as e:
        console.print(f"[bold red]Fehler beim Löschen der Git-Dateien:[/] {e}")
        return False


def overwrite_repository(console: Console, directory: Path, options: GitOptions) -> bool:
    """
    Überschreibt ein bestehendes Git-Repository, indem das .git Verzeichnis gelöscht wird.

    Args:
        console: Console-Objekt für die Ausgabe
        directory: Verzeichnis, in dem das Repository überschrieben werden soll
        options: GitOptions mit Konfigurationsoptionen

    Returns:
        True bei Erfolg, False bei Fehler
    """
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        # Kein Repository vorhanden, nichts zu tun
        if options.verbose:
            console.print("[dim]Kein bestehendes Git-Repository zum Überschreiben gefunden.[/]")
        return True

    console.print("[bold blue]Überschreibe bestehendes Git-Repository...[/]")
    return cleanup_git_dir(console, directory, options)


def cleanup_git_dir(console: Console, directory: Path, options: GitOptions) -> bool:
    # .git Verzeichnis löschen (erstellt durch init_git_repo)
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        return True

    try:
        if options.verbose:
            console.print(f"[dim]Lösche Verzeichnis: {git_dir}[/]")

        # Kurz warten, damit alle Dateien geschlossen werden können
        import time

        time.sleep(1)  # 1 Sekunde warten

        # Versuche es mit shutil.rmtree
        shutil.rmtree(git_dir, ignore_errors=True)

        # Prüfe, ob das Verzeichnis noch existiert
        if not git_dir.exists():
            console.print("[bold green].git Verzeichnis wurde gelöscht.[/]")
            return True

        # Wenn das Verzeichnis noch existiert, versuche es mit einem externen Befehl
        console.print(
            "[yellow]Konnte .git Verzeichnis nicht mit Python löschen, versuche externen Befehl...[/]"
        )

        if platform.system() == "Windows":
            # Unter Windows mit rd /s /q
            success, _ = run_git_command(
                console,
                ["cmd", "/c", "rd", "/s", "/q", str(git_dir)],
                options,
                "Fehler beim Löschen des .git Verzeichnisses:",
            )
        else:
            # Unter Unix mit rm -rf
            success, _ = run_git_command(
                console,
                ["rm", "-rf", str(git_dir)],
                options,
                "Fehler beim Löschen des .git Verzeichnisses:",
            )

        if success:
            console.print("[bold green].git Verzeichnis wurde gelöscht.[/]")
            return True

        # Wenn auch das nicht funktioniert, gib eine Anleitung zur manuellen Löschung
        console.print(
            "[bold yellow]Das .git Verzeichnis konnte nicht automatisch gelöscht werden.[/]"
        )
        console.print(f"Bitte löschen Sie das Verzeichnis manuell: {git_dir}")
        return False

    except Exception as e:
        console.print(f"[bold red]Fehler beim Löschen des .git Verzeichnisses:[/] {e}")
        console.print(f"Bitte löschen Sie das Verzeichnis manuell: {git_dir}")
        return False


def cleanup_git_repo(
    console: Console,
    directory: Path,
    options: GitOptions,
    should_delete_git_dir: bool = True,
) -> bool:
    """
    Git-Repository aufräumen.

    Args:
        console: Console-Objekt für die Ausgabe
        directory: Verzeichnis, in dem das Repository aufgeräumt werden soll
        options: GitOptions mit Konfigurationsoptionen
        should_delete_git_dir: Wenn True, wird das .git Verzeichnis gelöscht

    Returns:
        True bei Erfolg, False bei Fehler
    """
    console.print("[bold blue]Räume Git-Repository auf...[/]")

    # Immer die Git-Dateien aufräumen
    cleanup_file = cleanup_git_files(console, directory, options)

    # .git Verzeichnis nur löschen, wenn gewünscht
    cleanup_dir = True
    if should_delete_git_dir:
        cleanup_dir = cleanup_git_dir(console, directory, options)

    return cleanup_dir and cleanup_file


def overwrite_existing_repo(
    console: Console, directory: Path, options: GitOptions
) -> None:
    """
    Überprüft, ob ein Git-Repository existiert und fragt nach Bestätigung zur Anpassung oder Überschreibung.

    Args:
        console: Console-Objekt für die Ausgabe
        directory: Verzeichnis, in dem das Repository überprüft werden soll
        options: GitOptions mit Konfigurationsoptionen

    Die Ergebnisse werden direkt in den options-Parameter geschrieben:
    - options.continue_process: True, wenn der Vorgang fortgesetzt werden soll, False wenn abgebrochen
    - options.should_overwrite: True, wenn das Repository überschrieben werden soll, False wenn nur angepasst
    """
    git_dir = directory / ".git"
    if not git_dir.exists() or not git_dir.is_dir():
        # Kein Repository vorhanden, nichts zu tun
        if options.verbose:
            console.print("[dim]Kein bestehendes Git-Repository gefunden.[/]")
        options.continue_process = True
        options.should_overwrite = True
        return

    if options.force:
        if options.verbose:
            console.print(
                "[dim]Bestehendes Git-Repository wird überschrieben (--force).[/]"
            )
        options.continue_process = True
        options.should_overwrite = True
        return

    console.print(
        "[bold yellow]Warnung:[/] In diesem Verzeichnis existiert bereits ein Git-Repository."
    )

    # Frage nach, ob das Repository überschrieben oder angepasst werden soll
    choices = ["Überschreiben", "Anpassen", "Abbrechen"]
    choice = click.prompt(
        "Möchten Sie das bestehende Repository überschreiben, anpassen oder den Vorgang abbrechen?",
        type=click.Choice(choices),
        default="Anpassen",
    )

    if choice == "Abbrechen":
        console.print("[bold yellow]Vorgang abgebrochen.[/]")
        options.continue_process = False
        options.should_overwrite = False
        return

    if choice == "Überschreiben":
        console.print("[bold blue]Bestehendes Git-Repository wird überschrieben...[/]")
        options.continue_process = True
        options.should_overwrite = True
        return

    # Ansonsten: Anpassen
    console.print(
        "[bold blue]Zeilenenden im bestehenden Repository werden angepasst...[/]"
    )
    options.continue_process = True
    options.should_overwrite = False


def open_file_explorer(directory: Path, console: Console, verbose: bool) -> None:
    """
    Öffnet den Datei-Explorer für das angegebene Verzeichnis.

    Args:
        directory: Das zu öffnende Verzeichnis
        console: Console-Objekt für die Ausgabe
        verbose: Wenn True, werden ausführliche Informationen angezeigt
    """
    try:
        if verbose:
            console.print(f"[dim]Öffne Datei-Explorer für: {directory}[/]")

        system = platform.system()
        if system == "Windows":
            os.startfile(directory)
        elif system == "Darwin":  # macOS
            subprocess.run(["open", directory], check=True)
        else:  # Linux und andere
            subprocess.run(["xdg-open", directory], check=True)

        console.print(f"[bold green]Datei-Explorer für {directory} wurde geöffnet.[/]")
    except Exception as e:
        console.print(f"[bold red]Fehler beim Öffnen des Datei-Explorers:[/] {e}")


def create_git_repo(directory: Path, options: GitOptions) -> None:
    """
    Erstellt ein Git-Repository und passt die Zeilenenden an.

    Args:
        directory: Das Verzeichnis, in dem die Zeilenenden angepasst werden sollen
        options: GitOptions mit Konfigurationsoptionen
        open_explorer: Wenn True, wird der Datei-Explorer nach Abschluss geöffnet
    """
    console = Console()

    # Sicherstellen, dass das Verzeichnis existiert
    if not directory.exists() or not directory.is_dir():
        console.print(
            f"[bold red]Fehler:[/] Das Verzeichnis {directory} existiert nicht."
        )
        return

    # In das Verzeichnis wechseln
    original_dir = os.getcwd()
    os.chdir(directory)
    
    # Wenn das Repository überschrieben werden soll, lösche das bestehende .git Verzeichnis
    if options.should_overwrite:
        if not overwrite_repository(console, directory, options):
            console.print("[bold red]Fehler beim Überschreiben des bestehenden Repositories.[/]")
            os.chdir(original_dir)
            return

    # Liste der auszuführenden Funktionen
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
        # Führe jeden Schritt aus und prüfe auf Erfolg
        for step in steps:
            if step(console, options):
                continue
            success = False
            break

        if success:
            console.print("[bold green]Zeilenenden wurden erfolgreich angepasst![/]")

    finally:
        # Git-Repository aufräumen, wenn gewünscht
        if options.cleanup and success:
            # Das .git Verzeichnis nur löschen, wenn zuvor keines existierte oder das existierende überschrieben wurde
            should_delete_git_dir = options.should_overwrite
            cleanup_git_repo(console, directory, options, should_delete_git_dir)

        # Zurück zum ursprünglichen Verzeichnis wechseln
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
    help="Dateiendungen, die angepasst werden sollen (z.B. 'py,txt,md')",
)
@click.option(
    "--line-ending",
    "-l",
    type=click.Choice(["crlf", "lf"]),
    default="crlf",
    help="Art der Zeilenenden (Standard: crlf)",
)
@click.option("--verbose", "-v", is_flag=True, help="Ausführliche Ausgabe")
@click.option(
    "--keep-git",
    "-k",
    is_flag=True,
    default=False,
    help="Git-Repository nach der Konvertierung behalten",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    default=False,
    help="Bestehendes Git-Repository ohne Nachfrage überschreiben",
)
@click.option(
    "--open-explorer",
    "-o",
    is_flag=True,
    default=False,
    help="Datei-Explorer nach Abschluss öffnen",
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
    Passt die Zeilenenden von Dateien in einem Verzeichnis mittels Git an.

    Parameters:
    -----------
    directory : Path
        Das Verzeichnis, in dem die Zeilenenden angepasst werden sollen.
    extensions : tuple[str, ...]
        Liste der Dateiendungen, die angepasst werden sollen.
    line_ending : str
        Art der Zeilenenden (crlf oder lf).
    verbose : bool
        Wenn gesetzt, wird eine ausführliche Ausgabe angezeigt.
    keep_git : bool
        Wenn gesetzt, wird das Git-Repository nach der Konvertierung nicht gelöscht.
    force : bool
        Wenn gesetzt, wird ein bestehendes Git-Repository ohne Nachfrage überschrieben.
    open_explorer : bool
        Wenn gesetzt, wird der Datei-Explorer nach Abschluss geöffnet.
    """
    console = Console()

    if verbose:
        console.print(f"[bold]Verzeichnis:[/] {directory}")
        console.print(f"[bold]Zeilenenden:[/] {line_ending}")
        if extensions:
            console.print(f"[bold]Dateiendungen:[/] {', '.join(extensions)}")
        else:
            console.print("[bold]Dateiendungen:[/] Alle Textdateien")
        console.print(
            f"[bold]Git-Repository behalten:[/] {'Ja' if keep_git else 'Nein'}"
        )
        console.print(f"[bold]Force-Modus:[/] {'Ja' if force else 'Nein'}")
        console.print(
            f"[bold]Datei-Explorer öffnen:[/] {'Ja' if open_explorer else 'Nein'}"
        )

    # Liste der Dateiendungen erstellen
    ext_list = []
    for ext_group in extensions:
        ext_list.extend([e.strip() for e in ext_group.split(",") if e.strip()])

    # GitOptions erstellen
    options = GitOptions(
        extensions=ext_list,
        line_ending=line_ending,
        cleanup=not keep_git,
        verbose=verbose,
        force=force,
    )

    # Überprüfen und ggf. überschreiben eines bestehenden Repositories
    overwrite_existing_repo(console, directory, options)
    if not options.continue_process:
        return

    create_git_repo(directory, options)

    # Datei-Explorer öffnen, wenn gewünscht
    if open_explorer:
        open_file_explorer(directory, console, options.verbose)


if __name__ == "__main__":
    main()
