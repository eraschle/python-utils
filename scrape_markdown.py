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
    """Creates a valid filename from a URL."""
    parsed_url = urlparse(url)
    # Take the path and replace invalid characters
    filename = parsed_url.path.strip("/")
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Add .md if it's missing
    if not filename.endswith(".md"):
        filename += ".md"
    # Handle empty filenames (e.g., for root URL)
    if not filename or filename == ".md":
        filename = f"{parsed_url.netloc}.md"
        filename = re.sub(r'[<>:"/\\|?*]', "_", filename)  # Clean again
    return filename


def show_current_url(item):
    """Returns a shortened version of the URL for the progress bar."""
    if not item:
        return ""

    # Define maximum lengths
    max_visible_segments = 2  # Number of path segments at the end that remain visible
    max_total_len = 70  # Maximum total length of the display URL
    try:
        url_str = str(item)
        parsed = urlparse(url_str)
        path = parsed.path

        # Handle simple cases (no path or only root)
        if not path or path == "/":
            # Shorten the base URL if it's already too long
            if len(url_str) > max_total_len:
                return url_str[: max_total_len - 3] + "..."
            return url_str

        # Split the path into segments (ignore empty parts due to leading/trailing '/')
        segments = [s for s in path.split("/") if s]

        shortened_url = url_str  # Default is the original URL

        if len(segments) > max_visible_segments:
            # Keep the last 'max_visible_segments'
            visible_part = "/".join(segments[-max_visible_segments:])
            # Construct the shortened path
            # Add leading slash if the original path started with it
            shortened_path = ("/" if path.startswith("/") else "") + ".../" + visible_part
            # Add trailing slash if the original path ended with it AND it wasn't just the root slash
            if path.endswith("/") and len(segments) > 0:
                shortened_path += "/"

            # Reconstruct the URL
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

        # Final length check and shortening if necessary
        if len(shortened_url) > max_total_len:
            # Shorten from the beginning of the path to keep the end visible
            # Find the start of the path in the shortened URL
            path_start_index = len(parsed.scheme) + 3 + len(parsed.netloc)  # '://' = 3
            if path_start_index < len(shortened_url):
                # Calculate how much of the beginning (scheme + host + path beginning) can be shown
                keep_len = (
                    max_total_len - (len(shortened_url) - path_start_index) - 3
                )  # -3 für "..."
                if keep_len < path_start_index + 5:  # Show at least host + a bit of path
                    # If too short, just shorten from the front
                    return shortened_url[: max_total_len - 3] + "..."
                else:
                    # Shorten intelligently, keep beginning and end
                    return (
                        shortened_url[:path_start_index]
                        + "..."
                        + shortened_url[-(max_total_len - path_start_index - 3) :]
                    )

            else:  # Shouldn't happen, but as fallback
                return shortened_url[: max_total_len - 3] + "..."

        else:
            return shortened_url

    except Exception:
        # Fallback for unexpected errors (e.g., invalid URL)
        url_str = str(item)
        if len(url_str) > max_total_len:
            return url_str[: max_total_len - 3] + "..."
        return url_str


def search_urls(app: FirecrawlApp, url: str, search: str) -> list[str]:
    """
    Searches a start URL for a term using Firecrawl.

    Args:
        app: The initialized FirecrawlApp instance.
        url: The start URL to search.
        search: The search term.

    Returns:
        A list of found URLs or an empty list on errors or no results.
    """
    click.echo(f"Searching '{url}' for '{search}'...")
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
            click.echo("No matching URLs found (map_result is empty).")
            return []

        if not map_result.success:
            click.echo(
                "Error with API request. Check the URL and API key.",
                err=True,
            )
            return []

        found_urls = map_result.links
        if not found_urls:
            click.echo("No URLs found in map_result.")
            return []

        click.echo(f"{len(found_urls)} URLs found.")
        return found_urls

    except Exception as e:
        click.echo(f"Error with map_url: {e}", err=True)
        return []


def sanitize_title_to_filename(title: Optional[str], fallback_url: str) -> str:
    """
    Creates a valid filename from a page title.
    Uses sanitize_filename(fallback_url) as fallback if no title is present.
    """
    # Fallback if title is None, empty, or only whitespace
    if not title or title.isspace():
        click.echo(
            f"\nWarning: No title found for URL {fallback_url}. Using URL for filename.",
            err=True,
        )
        return sanitize_filename(fallback_url)  # Use the existing URL sanitizer function

    # Replace invalid characters in title
    # Allow spaces and replace them later with underscores
    filename = re.sub(r'[<>:"/\\|?*]', "_", title)
    # Replace multiple spaces/underscores with a single underscore
    filename = re.sub(r"[\s_]+", "_", filename).strip("_")

    # Optional: Limit length (e.g., to 100 characters)
    max_len = 100
    if len(filename) > max_len:
        filename = filename[:max_len].strip("_")

    # Add .md
    filename += ".md"

    # Handle very short or empty names after cleaning
    if filename == ".md" or len(filename) < 4:  # ".md" is 3 characters long
        click.echo(
            f"\nWarning: Could not generate valid title-based name for URL {fallback_url}. Using URL.",
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
    Scrapes a list of URLs, extracts the Markdown content, and saves it to files.

    Args:
        app: The initialized FirecrawlApp instance.
        urls: A list of URLs to scrape.
        output_path: The path to the directory where Markdown files should be saved.
    """
    # Ensure the output directory exists
    output_path.mkdir(parents=True, exist_ok=True)
    click.echo(f"Saving {len(urls)} Markdown files to: {output_path.resolve()}")

    # Use click.progressbar with URL display
    with progressbar(urls, label="Scraping URLs", item_show_func=show_current_url) as bar:
        for found_url in bar:
            scrape_response = None  # Initialize in case of early error
            try:
                scrape_response = app.scrape_url(
                    url=found_url,
                    formats=["markdown"],
                    only_main_content=True,
                )
            except Exception as e:
                click.echo(f"\nError scraping {found_url}: {e}", err=True)
                continue

            if scrape_response is None or scrape_response.markdown is None:
                click.echo(f"\nNo Markdown content found for {found_url}.", err=True)
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
                    f"\nError writing file {filepath.name} for URL {found_url}: {e}",
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
    help="Firecrawl API Key. If not provided, the FIRECRAWL_API_KEY environment variable will be used.",
)
def main(url: str, search: str, output_path: Path, api_key: Optional[str]):
    """
    Searches a start URL for a term using Firecrawl, downloads the
    found pages as Markdown and saves them to OUTPUT_PATH.
    """
    resolved_api_key = api_key or os.environ.get("FIRECRAWL_API_KEY")

    if not resolved_api_key:
        click.echo(
            "Error: API key not found. Please provide via --api-key or the FIRECRAWL_API_KEY environment variable.",
            err=True,
        )
        return

    app = FirecrawlApp(api_key=resolved_api_key)

    # Step 1: Search for URLs
    found_urls = search_urls(app, url, search)

    # Step 2: Scrape Markdown and save if URLs were found
    if found_urls:
        scrape_and_save_markdown(app, found_urls, output_path)
    else:
        click.echo("No URLs found to scrape.")

    click.echo("Process completed.")


if __name__ == "__main__":
    main()
