from datetime import datetime
from pathlib import Path

from trakt.errors import TraktUnavailable

from . import console
from .config import load_config
from .export import export_all_trakt_data
from .import_letterboxd import upload_to_letterboxd
from .log import configure_logging
from .paths import config_path as default_config_file
from .trakt import trakt_init


def sync_from_trakt(
    *,
    config_path: str | Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Pull new watches from Trakt into export.csv. Returns True on success."""
    configure_logging(verbose=verbose)
    title = "Trakt download (dry run)" if dry_run else "Trakt download"
    console.print(title, style="bold magenta")
    path = Path(config_path) if config_path is not None else default_config_file()
    config = load_config(path)
    if not config:
        return False

    if not config.has_trakt_credentials():
        console.print(
            "Trakt credentials missing or still placeholders. Run: ttl init",
            style="red",
        )
        return False

    if not trakt_init(config):
        console.print("Failed to log in to Trakt", style="red")
        return False

    try:
        export_all_trakt_data(dry_run=dry_run)
        if not dry_run:
            config.internal.last_successful_run = datetime.now()
            config.save()
        return True
    except TraktUnavailable:
        console.print("Trakt unavailable", style="red")
        return False
    except Exception as e:
        console.print(f"Trakt download failed: {e}", style="red")
        if verbose:
            console.print_exception()
        return False


def upload_to_letterboxd_cli(
    *,
    config_path: str | Path | None = None,
    diary: bool = True,
    dry_run: bool = False,
    verbose: bool = False,
    auto_sign_in: bool = True,
) -> bool:
    """Upload export.csv to Letterboxd. Returns True on success."""
    path = Path(config_path) if config_path is not None else default_config_file()
    config = load_config(path)
    if not config:
        return False

    if not config.has_letterboxd_credentials():
        console.print(
            "Letterboxd credentials missing or still placeholders. Run: ttl init",
            style="red",
        )
        return False

    return upload_to_letterboxd(
        config,
        diary=diary,
        dry_run=dry_run,
        verbose=verbose,
        auto_sign_in=auto_sign_in,
    )
