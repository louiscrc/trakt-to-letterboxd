"""Trakt OAuth authentication module."""

from trakt import core
from trakt.api import TokenAuth
from trakt.auth import config_factory, device_auth

from . import console

core.AUTH_METHOD = core.DEVICE_AUTH


def create_trakt_config(config, with_tokens: bool = True):
    trakt_cfg = config_factory()
    trakt_cfg.CLIENT_ID = config.trakt_client_id
    trakt_cfg.CLIENT_SECRET = config.trakt_client_secret

    if with_tokens:
        trakt_cfg.OAUTH_TOKEN = config.internal.trakt_oauth.token
        trakt_cfg.OAUTH_REFRESH = config.internal.trakt_oauth.refresh
        trakt_cfg.OAUTH_EXPIRES_AT = config.internal.trakt_oauth.expires_at
    else:
        trakt_cfg.OAUTH_TOKEN = None
        trakt_cfg.OAUTH_REFRESH = None
        trakt_cfg.OAUTH_EXPIRES_AT = None

    return trakt_cfg


def clear_invalid_tokens(config):
    config.internal.trakt_oauth.token = None
    config.internal.trakt_oauth.refresh = None
    config.internal.trakt_oauth.expires_at = None
    config.save()


def save_tokens(config, trakt_cfg):
    config.internal.trakt_oauth.token = trakt_cfg.OAUTH_TOKEN
    config.internal.trakt_oauth.refresh = trakt_cfg.OAUTH_REFRESH
    config.internal.trakt_oauth.expires_at = trakt_cfg.OAUTH_EXPIRES_AT
    config.save()


def validate_existing_tokens(config, trakt_cfg) -> bool:
    try:
        client = core.api()
        auth: TokenAuth = client.auth
        auth.config = trakt_cfg
        _, token = auth.get_token()

        if not token:
            return False

        save_tokens(config, trakt_cfg)
        if client.get("users/me"):
            return True
        return False

    except Exception:
        return False


def run_device_auth(config) -> bool:
    trakt_cfg = create_trakt_config(config, with_tokens=False)

    console.print(
        "\n[bold cyan]Trakt device auth[/bold cyan] — enter the code at "
        "[link=https://trakt.tv/activate]trakt.tv/activate[/link]\n",
        style="cyan",
    )

    try:
        device_auth(config=trakt_cfg)
        save_tokens(config, trakt_cfg)
        console.print("Signed in to Trakt.", style="green")
        return True
    except Exception as e:
        console.print(f"Trakt auth failed: {e}", style="red")
        return False


def trakt_init(config) -> bool:
    has_existing_tokens = config.internal.trakt_oauth.token is not None

    if has_existing_tokens:
        trakt_cfg = create_trakt_config(config, with_tokens=True)
        if validate_existing_tokens(config, trakt_cfg):
            return True
        clear_invalid_tokens(config)

    return run_device_auth(config)
