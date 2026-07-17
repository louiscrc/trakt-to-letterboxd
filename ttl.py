#!/usr/bin/env python3
"""Trakt → Letterboxd sync (manual runs only)."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from letterboxd_trakt.main import sync_from_trakt, upload_to_letterboxd_cli


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="ttl",
        description="Sync Trakt watch history to Letterboxd.",
    )
    parser.add_argument(
        "-t",
        "--trakt",
        action="store_true",
        help="Pull new watches from Trakt into csv/export.csv (accumulates)",
    )
    parser.add_argument(
        "-l",
        "--letterboxd",
        action="store_true",
        help="Upload csv/export.csv to Letterboxd, then clear it",
    )
    parser.add_argument(
        "--config",
        default="config.yml",
        help="Config file path (default: config.yml)",
    )
    parser.add_argument(
        "--no-diary",
        action="store_true",
        help="Skip diary entries on Letterboxd import (only with -l/--letterboxd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Trakt: fetch only, no CSV writes. Letterboxd: stop before Import Films (Ctrl-C to exit)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed progress logs",
    )

    args = parser.parse_args()
    if args.no_diary and not args.letterboxd:
        parser.error("--no-diary requires -l/--letterboxd")
    if args.dry_run and not args.trakt and not args.letterboxd:
        parser.error("--dry-run requires -t/--trakt and/or -l/--letterboxd")
    if not args.trakt and not args.letterboxd:
        parser.print_help()
        sys.exit(1)

    if args.trakt:
        sync_from_trakt(config_path=args.config, dry_run=args.dry_run, verbose=args.verbose)
    if args.letterboxd:
        upload_to_letterboxd_cli(
            config_path=args.config,
            diary=not args.no_diary,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
