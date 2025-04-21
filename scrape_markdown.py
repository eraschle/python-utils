# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "firecrawl",
#     "click",
# ]
# ///
from enum import member
import os
import re
from pathlib import Path
from typing import Optional
import click
from click import progressbar
from urllib.parse import urlparse, urlunparse

# Install with pip install firecrawl-py
from firecrawl import FirecrawlApp
from firecrawl.firecrawl import MapParams, ScrapeResponse


def sanitize_filename(url: str) -> str:
    """Erstellt einen gültigen Dateinamen aus einer URL."""
    parsed_url = urlparse(url)
    # Nimm den Pfad und ersetze ungültige Zeichen
    filename = parsed_url.path.strip("/")
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Füge .md hinzu, wenn es fehlt
    if not filename.endswith(".md"):
        filename += ".md"
    # Handle leere Dateinamen (z.B. für Root-URL)
    if not filename or filename == ".md":
        filename = f"{parsed_url.netloc}.md"
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)  # Erneut säubern
    return filename


def show_current_url(item):
    """Gibt eine gekürzte Version der URL für die Progressbar zurück."""
    if not item:
        return ""

    # Definiere maximale Längen
    max_visible_segments = 2  # Anzahl der Pfadsegmente am Ende, die sichtbar bleiben
    max_total_len = 70  # Maximale Gesamtlänge der Anzeige-URL
    try:
        url_str = str(item)
        parsed = urlparse(url_str)
        path = parsed.path

        # Handle einfache Fälle (kein Pfad oder nur Root)
        if not path or path == "/":
            # Kürze ggf. die Basis-URL, falls sie allein schon zu lang ist
            if len(url_str) > max_total_len:
                return url_str[: max_total_len - 3] + "..."
            return url_str

        # Zerlege den Pfad in Segmente (ignoriere leere Teile durch führende/folgende '/')
        segments = [s for s in path.split("/") if s]

        shortened_url = url_str  # Standard ist die Original-URL

        if len(segments) > max_visible_segments:
            # Behalte die letzten 'max_visible_segments'
            visible_part = "/".join(segments[-max_visible_segments:])
            # Konstruiere den gekürzten Pfad
            # Füge führenden Slash hinzu, wenn der Originalpfad damit begann
            shortened_path = ("/" if path.startswith("/") else "") + ".../" + visible_part
            # Füge abschließenden Slash hinzu, wenn der Originalpfad damit endete UND es nicht nur der Root-Slash war
            if path.endswith("/") and len(segments) > 0:
                shortened_path += "/"

            # Baue die URL wieder zusammen
            shortened_url = urlunparse(
                (
                    parsed.scheme,
                    parsed.netloc,
                    shortened_path,
                    parsed.params,
                    parsed.query,
                    parsed.fragment,
                )
            )

        # Finale Längenprüfung und Kürzung, falls nötig
        if len(shortened_url) > max_total_len:
            # Kürze vom Anfang des Pfades her, um das Ende sichtbar zu halten
            # Finde den Start des Pfades in der gekürzten URL
            path_start_index = len(parsed.scheme) + 3 + len(parsed.netloc)  # '://' = 3
            if path_start_index < len(shortened_url):
                # Berechne, wie viel vom Anfang (Schema + Host + Pfad-Anfang) gezeigt werden kann
                keep_len = (
                    max_total_len - (len(shortened_url) - path_start_index) - 3
                )  # -3 für "..."
                if keep_len < path_start_index + 5:  # Mindestens Host + ein bisschen Pfad zeigen
                    # Wenn zu kurz, einfach von vorne kürzen
                    return shortened_url[: max_total_len - 3] + "..."
                else:
                    # Kürze intelligent, behalte Anfang und Ende
                    return (
                        shortened_url[:path_start_index]
                        + "..."
                        + shortened_url[-(max_total_len - path_start_index - 3) :]
                    )

            else:  # Sollte nicht passieren, aber als Fallback
                return shortened_url[: max_total_len - 3] + "..."

        else:
            return shortened_url

    except Exception:
        # Fallback bei unerwarteten Fehlern (z.B. ungültige URL)
        url_str = str(item)
        if len(url_str) > max_total_len:
            return url_str[: max_total_len - 3] + "..."
        return url_str


def search_urls(app: FirecrawlApp, url: str, search: str) -> list[str]:
    """
    Durchsucht eine Start-URL nach einem Begriff mit Firecrawl.

    Args:
        app: Die initialisierte FirecrawlApp Instanz.
        url: Die zu durchsuchende Start-URL.
        search: Der Suchbegriff.

    Returns:
        Eine Liste der gefundenen URLs oder eine leere Liste bei Fehlern oder keinen Ergebnissen.
    """
    click.echo(f"Durchsuche '{url}' nach '{search}'...")
    try:
        map_result = app.map_url(
            url,
            params=MapParams(
                includeSubdomains=True,
                ignoreSitemap=True,
                search=search,
                limit=100,
            ),
        )
        if not map_result:
            click.echo("Keine passenden URLs gefunden (map_result ist leer).")
            return []

        if not map_result.success:
            click.echo(
                "Fehler bei der API-Anfrage. Überprüfen Sie die URL und den API-Schlüssel.",
                err=True,
            )
            return []

        found_urls = map_result.links
        if not found_urls:
            click.echo("Keine URLs im map_result gefunden.")
            return []

        click.echo(f"{len(found_urls)} URLs gefunden.")
        return found_urls

    except Exception as e:
        click.echo(f"Fehler bei map_url: {e}", err=True)
        return []


def sanitize_title_to_filename(title: Optional[str], fallback_url: str) -> str:
    """
    Erstellt einen gültigen Dateinamen aus einem Seitentitel.
    Verwendet sanitize_filename(fallback_url) als Fallback, wenn kein Titel vorhanden ist.
    """
    # Fallback, wenn Titel None, leer oder nur Leerzeichen ist
    if not title or title.isspace():
        click.echo(
            f"\nWarnung: Kein Titel für URL {fallback_url} gefunden. Verwende URL für Dateinamen.",
            err=True,
        )
        return sanitize_filename(fallback_url)  # Verwende die bestehende URL-Sanitizer-Funktion

    # Ersetze ungültige Zeichen im Titel
    # Erlaube Leerzeichen und ersetze sie später durch Unterstriche
    filename = re.sub(r'[<>:"/\\|?*]', "_", title)
    # Ersetze mehrere Leerzeichen/Unterstriche durch einen einzigen Unterstrich
    filename = re.sub(r"[\s_]+", "_", filename).strip("_")

    # Optional: Länge begrenzen (z.B. auf 100 Zeichen)
    max_len = 100
    if len(filename) > max_len:
        filename = filename[:max_len].strip("_")

    # Füge .md hinzu
    filename += ".md"

    # Handle sehr kurze oder leere Namen nach der Bereinigung
    if filename == ".md" or len(filename) < 4:  # ".md" ist 3 Zeichen lang
        click.echo(
            f"\nWarnung: Konnte keinen gültigen Titel-basierten Namen für URL {fallback_url} generieren. Verwende URL.",
            err=True,
        )
        return sanitize_filename(fallback_url)

    return filename


def _get_page_title(scrape_response: ScrapeResponse) -> str | None:
    if scrape_response.title is not None:
        return scrape_response.title
    if scrape_response.metadata is not None:
        return scrape_response.metadata.get("title")
    return None


def scrape_and_save_markdown(app: FirecrawlApp, urls: list[str], output_path: Path) -> None:
    """
    Scrapt eine Liste von URLs, extrahiert den Markdown-Inhalt und speichert ihn in Dateien.

    Args:
        app: Die initialisierte FirecrawlApp Instanz.
        urls: Eine Liste von URLs, die gescraped werden sollen.
        output_path: Der Pfad zum Verzeichnis, in dem die Markdown-Dateien gespeichert werden sollen.
    """
    # Stelle sicher, dass das Output-Verzeichnis existiert
    output_path.mkdir(parents=True, exist_ok=True)
    click.echo(f"Speichere {len(urls)} Markdown-Dateien in: {output_path.resolve()}")

    # Verwende click.progressbar mit Anzeige der URL
    with progressbar(urls, label="Scraping URLs", item_show_func=show_current_url) as bar:
        for found_url in bar:
            scrape_response = None  # Initialisieren für den Fall eines frühen Fehlers
            try:
                scrape_response = app.scrape_url(
                    url=found_url,
                    formats=["markdown"],
                    only_main_content=True,
                )
            except Exception as e:
                click.echo(f"\nFehler beim Scrapen von {found_url}: {e}", err=True)
                continue

            if scrape_response is None or scrape_response.markdown is None:
                click.echo(f"\nKein Markdown-Inhalt für {found_url} gefunden.", err=True)
                continue

            markdown_content = scrape_response.markdown
            page_title = _get_page_title(scrape_response)
            filename = sanitize_title_to_filename(page_title, found_url)
            filepath = output_path / filename
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(markdown_content)
            except OSError as e:
                click.echo(
                    f"\nFehler beim Schreiben der Datei {filepath.name} für URL {found_url}: {e}",
                    err=True,
                )


@click.command()
@click.argument("url", type=str)
@click.argument("search", type=str)
@click.argument("output_path", type=click.Path(file_okay=False, path_type=Path))
@click.option(
    "--api-key",
    type=str,
    default=None,
    help="Firecrawl API Key. Falls nicht angegeben, wird die Umgebungsvariable FIRECRAWL_API_KEY verwendet.",
)
def main(url: str, search: str, output_path: Path, api_key: Optional[str]):
    """
    Durchsucht eine Start-URL nach einem Begriff mit Firecrawl, lädt die
    gefundenen Seiten als Markdown herunter und speichert sie im OUTPUT_PATH.
    """
    resolved_api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")

    if not resolved_api_key:
        click.echo(
            "Fehler: API-Schlüssel nicht gefunden. Bitte über --api-key oder die Umgebungsvariable FIRECRAWL_API_KEY angeben.",
            err=True,
        )
        return

    app = FirecrawlApp(api_key=resolved_api_key)

    # Schritt 1: URLs suchen
    found_urls = search_urls(app, url, search)

    # Schritt 2: Markdown scrapen und speichern, wenn URLs gefunden wurden
    if found_urls:
        scrape_and_save_markdown(app, found_urls, output_path)
    else:
        click.echo("Keine URLs zum Scrapen gefunden.")

    click.echo("Vorgang abgeschlossen.")


if __name__ == "__main__":
    main()
