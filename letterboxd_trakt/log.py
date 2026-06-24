from . import console

_verbose = False


def configure_logging(*, verbose: bool) -> None:
    global _verbose
    _verbose = verbose


def log_nav(msg: str) -> None:
    if _verbose:
        console.print(f"  {msg}", style="dim")


def log_heading(title: str) -> None:
    if _verbose:
        console.print(title, style="bold cyan")
