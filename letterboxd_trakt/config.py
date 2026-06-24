from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from . import console

CFG_PATH = Path("config.yml")
CFG_PATH.parent.mkdir(parents=True, exist_ok=True)


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


class Config(BaseModel):
    letterboxd_username: str = ""
    letterboxd_password: str | None = None
    trakt_client_id: str = ""
    trakt_client_secret: str = ""
    internal: Internal = Internal()

    def dump(self):
        return self.model_dump()

    def save(self, path: Path = CFG_PATH):
        with path.open("w") as f:
            yaml.dump(self.dump(), f, Dumper=PrettyDumper, sort_keys=False)

    @staticmethod
    def load(path: Path = CFG_PATH):
        if not path.exists():
            template_config = Config(
                letterboxd_username="your_letterboxd_username",
                letterboxd_password="your_letterboxd_password",
                trakt_client_id="your_trakt_client_id",
                trakt_client_secret="your_trakt_client_secret",
            )
            template_config.save()

            console.print("Config not found, created template", style="orange4")
            return None

        with path.open("r") as f:
            yaml_data = yaml.safe_load(f)

            if not isinstance(yaml_data, dict):
                console.print(
                    "Failed to load config: invalid config schema", style="red"
                )
                return None

            return Config(**yaml_data)


def load_config(path: Path | str | None = None) -> Config | None:
    cfg_path = Path(path) if path else CFG_PATH
    try:
        config = Config.load(cfg_path)
        if not config:
            return None
        return config
    except Exception:
        console.print_exception()

    return None
