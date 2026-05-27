"""tufup-based auto-update client.

Replaces the old client.py + swap.py. The Qt UI in ui.py is the only caller.

This module knows three things:
  - where to find the bundled trust anchor (1.root.json),
  - where to point tufup at our gh-pages hosting,
  - how to construct a tufup.client.Client for the current platform.

Everything else (download, verify, extract, swap, relaunch) is tufup's job.
"""
from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Callable, Optional

from platformdirs import user_data_dir
from tufup.client import Client

APP_NAME = "lifegen-save-editor"
GITHUB_OWNER = "cdhoff03"
GITHUB_REPO  = "lifegen-save-editor"
PAGES_BASE = f"https://{GITHUB_OWNER}.github.io/{GITHUB_REPO}"


def _asset_key() -> Optional[str]:
    """Map this Python's OS+arch to the matching tufup tree, or None."""
    system, machine = platform.system(), platform.machine()
    if system == "Windows":
        return "windows-x64"
    if system == "Darwin" and machine == "arm64":
        return "macos-arm64"
    if system == "Darwin" and machine == "x86_64":
        return "macos-x64"
    if system == "Linux" and machine == "x86_64":
        return "linux-x64"
    return None


def _install_dir() -> Path:
    """Directory that should be replaced by the update.

    Windows / Linux: the parent of sys.executable (PyInstaller --onedir).
    macOS: the *.app bundle root.
    """
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for p in [exe, *exe.parents]:
            if p.suffix == ".app":
                return p
        raise RuntimeError(f"could not locate .app bundle from {exe}")
    return exe.parent


def _bundled_root_path(asset_key: str) -> Path:
    """Locate the trust anchor inside the running build (frozen or source)."""
    if getattr(sys, "frozen", False):
        # PyInstaller --onedir puts data files under sys._MEIPASS / assets/.
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        # In dev, walk up from this file: lifegen_editor/updater/tufup_client.py
        # -> repo root.
        base = Path(__file__).resolve().parent.parent.parent
    return base / "assets" / "tufup" / asset_key / "1.root.json"


def _seed_root_if_missing(metadata_dir: Path, asset_key: str) -> None:
    """Copy the bundled root.json into the per-user metadata dir on first run."""
    dst = metadata_dir / "root.json"
    if dst.exists():
        return
    src = _bundled_root_path(asset_key)
    dst.write_bytes(src.read_bytes())


def _make_client() -> Optional[Client]:
    key = _asset_key()
    if key is None:
        return None
    data_dir = Path(user_data_dir(APP_NAME))
    metadata_dir = data_dir / "metadata"
    target_dir   = data_dir / "downloads"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    _seed_root_if_missing(metadata_dir, key)

    from lifegen_editor import __version__

    return Client(
        app_name=APP_NAME,
        app_install_dir=_install_dir(),
        current_version=__version__,
        metadata_dir=metadata_dir,
        metadata_base_url=f"{PAGES_BASE}/{key}/metadata/",
        target_dir=target_dir,
        target_base_url=f"{PAGES_BASE}/{key}/targets/",
        refresh_required=False,
    )


def auto_check_enabled() -> bool:
    """Auto-check runs only in frozen builds, and can be env-disabled."""
    import os
    if os.environ.get("LIFEGEN_DISABLE_UPDATE_CHECK") == "1":
        return False
    return bool(getattr(sys, "frozen", False))


def check_for_update():
    """Returns a tufup TargetMeta if a newer version is available, else None.

    Raises whatever tufup raises on signature / network errors -- the Qt UI
    surfaces these to the user.
    """
    client = _make_client()
    if client is None:
        return None
    return client.check_for_updates()


def perform_update(progress_cb: Callable[[int, int], None]) -> None:
    """Downloads + verifies + applies the update.

    On the happy path this spawns tufup's install script and exits the current
    process; it does NOT return. On failure it raises an exception which the
    caller should surface to the user.
    """
    client = _make_client()
    if client is None:
        raise RuntimeError("Auto-update unavailable on this platform.")
    try:
        client.download_and_apply_update(progress_hook=progress_cb)
    except TypeError:
        client.download_and_apply_update()
