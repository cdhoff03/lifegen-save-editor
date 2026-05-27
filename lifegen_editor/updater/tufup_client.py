"""tufup-based auto-update client.

Replaces the old client.py + swap.py. The Qt UI in ui.py is the only caller.

This module knows three things:
  - where to find the bundled trust anchor (1.root.json),
  - where to point tufup at our gh-pages metadata + GitHub Release targets,
  - how to construct a tufup.client.Client for the current platform.

Everything else (download, verify, extract, swap, relaunch) is tufup's job.

URL strategy:
  - Metadata (small, signed JSON) lives on GitHub Pages:
      https://<owner>.github.io/<repo>/<asset_key>/metadata/
  - Targets (multi-megabyte .tar.gz / .patch bundles) live as GitHub Release
    assets on the tag for each version. Since GitHub Release URLs include
    the tag, we override download_target to construct URLs of the form:
      https://github.com/<owner>/<repo>/releases/download/v<ver>/<filename>-<asset_key>.<ext>
    where <ver> is parsed out of the tufup target filename
    (`lifegen-save-editor-1.2.3.tar.gz` for archives,
     `lifegen-save-editor-1.2.0-to-1.2.3.patch` for patches), and the
    asset_key suffix prevents the four per-OS bundles from colliding on
    a single Release.
"""
from __future__ import annotations

import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Callable, Optional

from platformdirs import user_data_dir
from tufup.client import Client

APP_NAME = "lifegen-save-editor"
GITHUB_OWNER = "cdhoff03"
GITHUB_REPO  = "lifegen-save-editor"
PAGES_BASE = f"https://{GITHUB_OWNER}.github.io/{GITHUB_REPO}"
RELEASES_BASE = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}/releases/download"


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
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "assets" / "tufup" / asset_key / "1.root.json"


def _seed_root_if_missing(metadata_dir: Path, asset_key: str) -> None:
    """Copy the bundled root.json into the per-user metadata dir on first run."""
    dst = metadata_dir / "root.json"
    if dst.exists():
        return
    src = _bundled_root_path(asset_key)
    dst.write_bytes(src.read_bytes())


# -----------------------------------------------------------------------------
# URL building helpers (also reused by sign_release.py via its own copy of
# the rename logic). Pure functions, easy to test.
# -----------------------------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+\.\d+\.\d+)")


def extract_target_version(filename: str) -> str:
    """Return the *target* (new) version from a tufup target filename.

    For full archives ``<app>-<ver>.tar.gz`` returns ``<ver>``.
    For patches ``<app>-<from>-to-<to>.patch`` returns ``<to>``.
    """
    matches = _VERSION_RE.findall(filename)
    if not matches:
        raise ValueError(f"cannot parse version from {filename!r}")
    return matches[-1]


def suffix_filename_with_asset_key(filename: str, asset_key: str) -> str:
    """``foo-1.2.3.tar.gz`` + ``windows-x64`` -> ``foo-1.2.3-windows-x64.tar.gz``.

    Handles both ``.tar.gz`` and ``.patch`` extensions.
    """
    if filename.endswith(".tar.gz"):
        stem = filename[: -len(".tar.gz")]
        return f"{stem}-{asset_key}.tar.gz"
    stem, _, ext = filename.rpartition(".")
    return f"{stem}-{asset_key}.{ext}"


def release_asset_url(target_filename: str, asset_key: str) -> str:
    """Compose the GitHub Release asset URL for a tufup target."""
    version = extract_target_version(target_filename)
    asset_name = suffix_filename_with_asset_key(target_filename, asset_key)
    return f"{RELEASES_BASE}/v{version}/{asset_name}"


# -----------------------------------------------------------------------------
# Custom Client. Overrides download_target so the URL points at the
# GitHub Release asset (with asset_key suffix), not the gh-pages targets dir.
# -----------------------------------------------------------------------------

class _GHReleaseClient(Client):
    def __init__(self, *, asset_key: str, **kwargs):
        super().__init__(**kwargs)
        self._asset_key = asset_key

    def download_target(self, targetinfo, filepath=None, target_base_url=None):
        """Re-implement download_target with our URL scheme.

        The parent's implementation builds ``target_base_url + targetinfo.path``.
        We ignore both and construct the GitHub Release URL ourselves.
        """
        if filepath is None:
            filepath = self._generate_target_file_path(targetinfo)
        full_url = release_asset_url(targetinfo.path, self._asset_key)
        with self._fetcher.download_file(full_url, targetinfo.length) as src:
            targetinfo.verify_length_and_hashes(src)
            src.seek(0)
            with open(filepath, "wb") as dst:
                shutil.copyfileobj(src, dst)
        return filepath


# -----------------------------------------------------------------------------
# Construction + public API.
# -----------------------------------------------------------------------------

def _make_client() -> Optional[_GHReleaseClient]:
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

    return _GHReleaseClient(
        asset_key=key,
        app_name=APP_NAME,
        app_install_dir=_install_dir(),
        current_version=__version__,
        metadata_dir=metadata_dir,
        metadata_base_url=f"{PAGES_BASE}/{key}/metadata/",
        # target_base_url is required by the parent but never used because we
        # override download_target. Pass a clearly-unused placeholder.
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
