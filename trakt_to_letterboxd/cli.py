"""Trakt → Letterboxd sync CLI."""

from __future__ import annotations

import argparse
import getpass
import sys
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path

import yaml

from .config import PrettyDumper
from .main import sync_from_trakt, upload_to_letterboxd_cli
from .paths import config_path, data_dir


def _package_version() -> str:
    try:
        return version("trakt-to-letterboxd")
    except PackageNotFoundError:
        return "0.0.0-dev"


def _prompt(label: str, *, secret: bool = False) -> str:
    while True:
        value = getpass.getpass(f"{label}: ") if secret else input(f"{label}: ")
        value = value.strip()
        if value:
            return value
        print("Value required.", file=sys.stderr)


def init_config(dest: Path, *, non_interactive: bool) -> int:
    """Create config.yml interactively, or write the template when non-interactive."""
    if dest.exists():
        print(f"{dest} already exists — not overwriting.", file=sys.stderr)
        return 1

    dest.parent.mkdir(parents=True, exist_ok=True)

    if non_interactive:
        template = files("trakt_to_letterboxd").joinpath("config.template.yml").read_text(
            encoding="utf-8"
        )
        dest.write_text(template, encoding="utf-8")
        print(f"Wrote template {dest}")
        print(f"Data directory: {data_dir()}")
        print(
            "Fill in letterboxd_username, letterboxd_password, "
            "trakt_client_id, trakt_client_secret."
        )
        return 0

    print(f"Creating config at {dest}")
    print("Get Trakt API credentials at https://trakt.tv/oauth/applications/new")
    print("(redirect URI: urn:ietf:wg:oauth:2.0:oob)\n")

    letterboxd_username = _prompt("Letterboxd username")
    letterboxd_password = _prompt("Letterboxd password", secret=True)
    trakt_client_id = _prompt("Trakt client ID")
    trakt_client_secret = _prompt("Trakt client secret", secret=True)

    data = {
        "letterboxd_username": letterboxd_username,
        "letterboxd_password": letterboxd_password,
        "trakt_client_id": trakt_client_id,
        "trakt_client_secret": trakt_client_secret,
        "internal": {
            "trakt_oauth": {
                "token": None,
                "refresh": None,
                "expires_at": None,
            },
            "last_successful_run": None,
        },
    }
    with dest.open("w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=PrettyDumper, sort_keys=False)

    print(f"\nWrote {dest}")
    print(f"Data directory: {data_dir()}")
    print("Keep this file private — it stores your Letterboxd password in plaintext.")
    return 0


def _add_shared_flags(parser: argparse.ArgumentParser, *, default_config: Path) -> None:
    parser.add_argument(
        "--config",
        default=str(default_config),
        help=f"Config file path (default: {default_config})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Trakt: fetch only, no CSV writes. Letterboxd: stop before Import Films",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress logs",
    )


def main() -> None:
    default_config = config_path()
    app_data = data_dir()
    parser = argparse.ArgumentParser(
        prog="ttl",
        description="Sync Trakt watch history to Letterboxd.",
        epilog=(
            f"Data directory: {app_data}\n"
            f"  config:  {default_config}\n"
            f"  csvs:    {app_data / 'csv'}\n"
            f"  chrome:  {app_data / 'chrome_profile'}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_package_version()}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_p = sub.add_parser("init", help="Create config.yml with interactive prompts")
    init_p.add_argument(
        "--config",
        default=str(default_config),
        help=f"Config file path (default: {default_config})",
    )
    init_p.add_argument(
        "--non-interactive",
        action="store_true",
        help="Write the default template config without prompting",
    )

    trakt_p = sub.add_parser("trakt", help="Pull new watches from Trakt into export.csv")
    _add_shared_flags(trakt_p, default_config=default_config)

    letterboxd_p = sub.add_parser(
        "letterboxd",
        help="Upload export.csv to Letterboxd, then clear it",
    )
    _add_shared_flags(letterboxd_p, default_config=default_config)
    letterboxd_p.add_argument(
        "--no-diary",
        action="store_true",
        help="Skip diary entries on Letterboxd import",
    )
    letterboxd_p.add_argument(
        "--manual-sign-in",
        action="store_true",
        help="Do not auto-click Sign In (fill credentials only)",
    )

    sync_p = sub.add_parser("sync", help="Run trakt then letterboxd")
    _add_shared_flags(sync_p, default_config=default_config)
    sync_p.add_argument(
        "--no-diary",
        action="store_true",
        help="Skip diary entries on Letterboxd import",
    )
    sync_p.add_argument(
        "--manual-sign-in",
        action="store_true",
        help="Do not auto-click Sign In (fill credentials only)",
    )

    try:
        args = parser.parse_args()
    except KeyboardInterrupt:
        sys.exit(130)

    try:
        if args.command == "init":
            sys.exit(init_config(Path(args.config), non_interactive=args.non_interactive))

        ok = True
        if args.command in ("trakt", "sync"):
            ok = sync_from_trakt(
                config_path=args.config,
                dry_run=args.dry_run,
                verbose=args.verbose,
            )
            if not ok and args.command == "sync":
                sys.exit(1)

        if ok and args.command in ("letterboxd", "sync"):
            ok = upload_to_letterboxd_cli(
                config_path=args.config,
                diary=not args.no_diary,
                dry_run=args.dry_run,
                verbose=args.verbose,
                auto_sign_in=not args.manual_sign_in,
            )

        sys.exit(0 if ok else 1)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        sys.exit(130)
