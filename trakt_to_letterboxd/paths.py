"""Platform data directory for config, CSVs, and Chrome profile."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIR_NAME = "trakt-to-letterboxd"


def data_dir() -> Path:
    """Return the app data directory, creating it if needed.

    - macOS: ~/Library/Application Support/trakt-to-letterboxd
    - Windows: %LOCALAPPDATA%/trakt-to-letterboxd
    - Linux/other: $XDG_DATA_HOME/trakt-to-letterboxd or ~/.local/share/trakt-to-letterboxd
    """
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    path = base / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.yml"


def csv_dir() -> Path:
    path = data_dir() / "csv"
    path.mkdir(parents=True, exist_ok=True)
    return path


def csv_path(filename: str) -> Path:
    return csv_dir() / filename


def chrome_profile_dir() -> Path:
    """Chrome user-data dir; migrates legacy cwd locations if present."""
    import shutil

    profile = data_dir() / "chrome_profile"
    for legacy in (Path("./chrome_profile"), Path("./csv/chrome_profile")):
        if not profile.exists() and legacy.exists():
            shutil.move(str(legacy), str(profile))
            break
    profile.mkdir(parents=True, exist_ok=True)
    return profile
