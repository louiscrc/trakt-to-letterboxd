from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, PrivateAttr

from . import console
from .paths import config_path

_PLACEHOLDER_VALUES = frozenset(
    {
        "your_letterboxd_username",
        "your_letterboxd_password",
        "your_trakt_client_id",
        "your_trakt_client_secret",
    }
)


class PrettyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


class TraktOAuth(BaseModel):
    token: str | None = None
    refresh: str | None = None
    expires_at: int | None = None


class Internal(BaseModel):
    trakt_oauth: TraktOAuth = TraktOAuth()
    last_successful_run: datetime | None = None


def _is_unset(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    return not stripped or stripped.lower() in _PLACEHOLDER_VALUES


class Config(BaseModel):
    letterboxd_username: str = ""
    letterboxd_password: str | None = None
    trakt_client_id: str = ""
    trakt_client_secret: str = ""
    internal: Internal = Internal()

    _path: Path | None = PrivateAttr(default=None)

    def dump(self):
        return self.model_dump()

    def save(self, path: Path | None = None):
        dest = Path(path) if path else (self._path or config_path())
        dest.parent.mkdir(parents=True, exist_ok=True)
        self._path = dest
        with dest.open("w", encoding="utf-8") as f:
            yaml.dump(self.dump(), f, Dumper=PrettyDumper, sort_keys=False)

    def has_trakt_credentials(self) -> bool:
        return not _is_unset(self.trakt_client_id) and not _is_unset(self.trakt_client_secret)

    def has_letterboxd_credentials(self) -> bool:
        return not _is_unset(self.letterboxd_username) and not _is_unset(self.letterboxd_password)

    @staticmethod
    def load(path: Path | None = None) -> "Config | None":
        dest = Path(path) if path else config_path()
        if not dest.exists():
            console.print(
                f"Config not found at {dest}. Run: ttl init",
                style="red",
            )
            return None

        with dest.open("r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)

        if not isinstance(yaml_data, dict):
            console.print("Failed to load config: invalid config schema", style="red")
            return None

        config = Config(**yaml_data)
        config._path = dest
        return config


def load_config(path: Path | str | None = None) -> Config | None:
    cfg_path = Path(path) if path else config_path()
    try:
        return Config.load(cfg_path)
    except Exception as e:
        console.print(f"Failed to load config: {e}", style="red")
        return None
