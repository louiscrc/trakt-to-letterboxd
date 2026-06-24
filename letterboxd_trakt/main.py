from datetime import datetime
from pathlib import Path

from trakt.errors import TraktUnavailable

from . import console
from .config import load_config
from .export import export_all_trakt_data
from .import_letterboxd import upload_to_letterboxd
from .log import configure_logging
from .trakt import trakt_init


def sync_from_trakt(
    *,
    config_path: str | Path = "config.yml",
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Pull new watches from Trakt into export.csv."""
    configure_logging(verbose=verbose)
    title = "Trakt download (dry run)" if dry_run else "Trakt download"
    console.print(title, style="bold magenta")
    path = Path(config_path)
    config = load_config(path)
    if not config:
        console.print("Config failed to load", style="red")
        return

    if not config.trakt_client_id or not config.letterboxd_username:
        console.print("Config not properly configured", style="red")
        return

    if not trakt_init(config):
        console.print("Failed to log in to Trakt", style="red")
        return

    try:
        export_all_trakt_data(dry_run=dry_run)
        if not dry_run:
            config.internal.last_successful_run = datetime.now()
            config.save(path)
    except TraktUnavailable:
        console.print("Trakt unavailable", style="red")
    except Exception:
        console.print("Trakt download failed", style="red")
        console.print_exception()


def upload_to_letterboxd_cli(
    *,
    config_path: str | Path = "config.yml",
    diary: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    path = Path(config_path)
    config = load_config(path)
    if not config:
        console.print("Config failed to load", style="red")
        return
    upload_to_letterboxd(config, diary=diary, dry_run=dry_run, verbose=verbose)
