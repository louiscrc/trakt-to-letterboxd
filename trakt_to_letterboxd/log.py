"""Terminal + in-page browser log panel (single window)."""

from __future__ import annotations

import json
from typing import Any, Literal

from . import console

Kind = Literal["prompt", "ok", "err", "info", "verbose", "heading"]

_verbose = False
_notify_driver: Any | None = None
_browser_lines: list[tuple[Kind, str]] = []
_browser_enabled = False
_bootstrap_installed = False
_MAX_BROWSER_LINES = 40

_KIND_STYLE = {
    "prompt": ("#000000", "#FFEB3B", "#FF5722"),
    "ok": ("#FFFFFF", "#1B5E20", "#69F0AE"),
    "err": ("#FFFFFF", "#B71C1C", "#FF5252"),
    "info": ("#FFFFFF", "#0D47A1", "#40C4FF"),
    "verbose": ("#E0E0E0", "#212121", "#9E9E9E"),
    "heading": ("#FFFFFF", "#4A148C", "#E040FB"),
}

_STORAGE_KEY = "__ttl_logs"


def configure_logging(*, verbose: bool) -> None:
    global _verbose
    _verbose = verbose


def set_browser_notify_driver(driver: Any | None) -> None:
    """Attach/detach the Selenium driver for the on-page log panel."""
    global _notify_driver, _browser_lines, _browser_enabled, _bootstrap_installed
    if driver is None:
        _browser_enabled = False
        _notify_driver = None
        _browser_lines = []
        _bootstrap_installed = False
        return

    _notify_driver = driver
    _browser_enabled = True
    _browser_lines = []
    _install_bootstrap(driver)


def reset_browser_logs() -> None:
    """Clear in-memory + on-page logs (call after landing on letterboxd.com)."""
    global _browser_lines
    _browser_lines = []
    if not _browser_enabled or _notify_driver is None:
        return
    try:
        _notify_driver.execute_script(
            """
            const key = arguments[0];
            try { localStorage.removeItem(key); } catch (e) {}
            if (typeof window.__ttlSaveAndPaint === 'function') {
              window.__ttlSaveAndPaint([]);
            } else if (typeof window.__ttlPaint === 'function') {
              window.__ttlPaint([]);
            }
            """,
            _STORAGE_KEY,
        )
    except Exception:
        pass


def ensure_letterboxd_window() -> None:
    """Re-paint the on-page log panel after navigations."""
    _flush_browser_panel()


def log_nav(msg: str) -> None:
    if _verbose:
        console.print(f"  {msg}", style="dim")
        _browser_log(msg, kind="verbose")


def log_heading(title: str) -> None:
    if _verbose:
        console.print(title, style="bold cyan")
        _browser_log(title, kind="heading")


def log_prompt(msg: str) -> None:
    console.print(f"  {msg}", style="yellow")
    _browser_log(msg, kind="prompt")


def log_ok(msg: str) -> None:
    console.print(f"  {msg}", style="green")
    _browser_log(msg, kind="ok")


def log_err(msg: str) -> None:
    console.print(f"  {msg}", style="red")
    _browser_log(msg, kind="err")


def log_info(msg: str) -> None:
    console.print(f"  {msg}", style="bold magenta")
    _browser_log(msg, kind="info")


def _browser_log(msg: str, *, kind: Kind) -> None:
    _browser_lines.append((kind, msg))
    if len(_browser_lines) > _MAX_BROWSER_LINES:
        del _browser_lines[: len(_browser_lines) - _MAX_BROWSER_LINES]
    _flush_browser_panel()


def _snapshot_lines() -> list[dict[str, str]]:
    return [{"kind": kind, "text": text} for kind, text in _browser_lines]


def _bootstrap_js() -> str:
    styles = json.dumps(
        {k: {"fg": v[0], "bg": v[1], "bd": v[2]} for k, v in _KIND_STYLE.items()}
    )
    return f"""
(function() {{
  if (window.__ttlLogBooted) return;
  window.__ttlLogBooted = true;
  const KEY = {json.dumps(_STORAGE_KEY)};
  const STYLES = {styles};

  function ensurePanel() {{
    let panel = document.getElementById('ttl-log-panel');
    if (panel) return panel;
    const root = document.documentElement || document.body;
    if (!root) return null;
    panel = document.createElement('div');
    panel.id = 'ttl-log-panel';
    panel.style.cssText = [
      'position:fixed',
      'top:12px',
      'right:12px',
      'left:auto',
      'z-index:2147483647',
      'width:min(380px,42vw)',
      'max-height:70vh',
      'overflow:auto',
      'display:flex',
      'flex-direction:column',
      'gap:6px',
      'padding:10px',
      'border-radius:12px',
      'background:rgba(0,0,0,0.88)',
      'box-shadow:0 10px 40px rgba(0,0,0,.55)',
      'pointer-events:none',
      'font:600 13px/1.35 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif',
    ].join(';');
    root.appendChild(panel);
    return panel;
  }}

  function paint(lines) {{
    const panel = ensurePanel();
    if (!panel) return;
    if (!lines) {{
      try {{ lines = JSON.parse(localStorage.getItem(KEY) || '[]'); }}
      catch (e) {{ lines = []; }}
    }}
    panel.innerHTML = '';
    for (const line of lines) {{
      const s = STYLES[line.kind] || STYLES.info;
      const row = document.createElement('div');
      row.textContent = line.text;
      row.style.cssText = [
        'padding:10px 12px',
        'border-radius:8px',
        'border:3px solid ' + s.bd,
        'background:' + s.bg,
        'color:' + s.fg,
        'white-space:pre-wrap',
        'word-break:break-word',
      ].join(';');
      panel.appendChild(row);
    }}
    panel.scrollTop = panel.scrollHeight;
  }}

  window.__ttlPaint = paint;
  window.__ttlSaveAndPaint = function(lines) {{
    try {{ localStorage.setItem(KEY, JSON.stringify(lines)); }} catch (e) {{}}
    paint(lines);
  }};

  // New browser process → empty sessionStorage. Drop leftover logs from the last run
  // before the first paint so they never flash on screen.
  try {{
    if (!sessionStorage.getItem('__ttl_run')) {{
      localStorage.removeItem(KEY);
      sessionStorage.setItem('__ttl_run', '1');
    }}
  }} catch (e) {{}}

  const kick = () => {{ try {{ paint(); }} catch (e) {{}} }};
  kick();
  document.addEventListener('DOMContentLoaded', kick);
  const mo = new MutationObserver(() => {{
    if (!document.getElementById('ttl-log-panel')) kick();
  }});
  try {{
    mo.observe(document.documentElement || document, {{ childList: true, subtree: true }});
  }} catch (e) {{}}
}})();
"""


def _install_bootstrap(driver: Any) -> None:
    global _bootstrap_installed
    if _bootstrap_installed:
        return
    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": _bootstrap_js()},
        )
        _bootstrap_installed = True
    except Exception:
        pass
    try:
        driver.execute_script(_bootstrap_js())
    except Exception:
        pass


def _flush_browser_panel() -> None:
    if not _browser_enabled or _notify_driver is None:
        return
    payload = _snapshot_lines()
    try:
        ok = _notify_driver.execute_script(
            """
            if (typeof window.__ttlSaveAndPaint === 'function') {
              window.__ttlSaveAndPaint(arguments[0]);
              return true;
            }
            return false;
            """,
            payload,
        )
        if ok:
            return
        _notify_driver.execute_script(_bootstrap_js())
        _notify_driver.execute_script(
            "window.__ttlSaveAndPaint(arguments[0]);",
            payload,
        )
    except Exception:
        pass
