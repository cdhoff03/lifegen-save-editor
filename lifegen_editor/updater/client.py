"""Auto-update client. Pure logic, no Qt dependencies.

See docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md.
"""
from __future__ import annotations

from typing import Iterable


def _parse(version: str) -> tuple[int, int, int, int]:
    """Parse a version string into a 4-tuple suitable for ordering.

    Returns ``(major, minor, patch, dev_flag)`` where ``dev_flag`` is 0 for
    a normal release and -1 for a ``-dev`` sentinel (so it sorts before
    any released version with the same major.minor.patch).
    """
    v = version.lstrip("v")
    dev_flag = 0
    if v.endswith("-dev"):
        v = v[: -len("-dev")]
        dev_flag = -1
    parts: list[str] = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    major, minor, patch = (int(p) for p in parts[:3])
    return (major, minor, patch, dev_flag)


def is_newer(current: str, remote: str) -> bool:
    """Return True if ``remote`` is strictly newer than ``current``."""
    return _parse(remote) > _parse(current)


# OS+arch (as returned by platform.system() / platform.machine()) → manifest key.
_ASSET_TABLE: dict[tuple[str, str], str] = {
    ("Windows", "AMD64"):  "windows-x64",
    ("Windows", "x86_64"): "windows-x64",
    ("Darwin",  "arm64"):  "macos-arm64",
    ("Darwin",  "x86_64"): "macos-x64",
    ("Linux",   "x86_64"): "linux-x64",
}


def pick_asset(manifest: dict, system: str, machine: str) -> dict | None:
    """Return the manifest asset entry for this OS+arch, or None."""
    key = _ASSET_TABLE.get((system, machine))
    if key is None:
        return None
    return manifest.get("assets", {}).get(key)


import hashlib
import json
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable


class UpdateError(Exception):
    """Base class for all updater errors."""


class UpdateCheckError(UpdateError):
    """Failed to fetch or parse the release manifest."""


class ChecksumMismatch(UpdateError):
    """Downloaded asset did not match the expected SHA-256."""


def download(
    asset: dict,
    dest: Path,
    progress_cb: Callable[[int, int | None], None] | None = None,
    chunk_size: int = 64 * 1024,
) -> Path:
    """Stream ``asset['url']`` to ``dest``, verifying ``asset['sha256']``.

    ``progress_cb(bytes_so_far, total_or_None)`` is called after each chunk.
    Raises ``ChecksumMismatch`` if the SHA-256 doesn't match (and deletes
    the partial file).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = asset["sha256"].lower()
    hasher = hashlib.sha256()
    bytes_so_far = 0

    req = urllib.request.Request(asset["url"], headers={"User-Agent": "lifegen-save-editor-updater/1"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
        total_header = resp.headers.get("Content-Length")
        total = int(total_header) if total_header else None
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            hasher.update(chunk)
            bytes_so_far += len(chunk)
            if progress_cb:
                progress_cb(bytes_so_far, total)

    if hasher.hexdigest().lower() != expected:
        dest.unlink(missing_ok=True)
        raise ChecksumMismatch(
            f"sha256 mismatch: expected {expected}, got {hasher.hexdigest()}"
        )
    return dest


def fetch_manifest(url: str, timeout: float = 10.0) -> dict:
    """GET ``url`` and parse the response as JSON. Raises UpdateCheckError."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lifegen-save-editor-updater/1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise UpdateCheckError(f"failed to fetch manifest: {e}") from e


def extract(archive: Path, dest_parent: Path) -> Path:
    """Extract ``archive`` into ``dest_parent`` and return the staging dir.

    Always extracts into a fresh subdirectory ``dest_parent / 'staging'`` so
    callers know exactly where to find the unpacked tree.
    """
    staging = dest_parent / "staging"
    if staging.exists():
        import shutil
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    suffix = "".join(archive.suffixes[-2:]) if archive.name.endswith(".tar.gz") else archive.suffix
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(staging)
    elif suffix == ".tar.gz":
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(staging)
    else:
        raise UpdateError(f"unsupported archive type: {archive.name}")
    return staging


import os
import platform
import sys


# TODO(user): set this to your GitHub <owner>/<repo> before first release.
UPDATE_REPO = "<owner>/lifegen-save-editor"


def manifest_url() -> str:
    return f"https://github.com/{UPDATE_REPO}/releases/latest/download/latest.json"


def auto_check_enabled() -> bool:
    """Auto-check runs only for frozen builds, and can be disabled by env var."""
    if os.environ.get("LIFEGEN_DISABLE_UPDATE_CHECK") == "1":
        return False
    return bool(getattr(sys, "frozen", False))


def check_for_update() -> tuple[dict, dict] | None:
    """Single-call helper: fetch manifest, compare versions, pick asset.

    Returns ``(manifest, asset)`` if an update is available for this platform,
    or ``None`` if up to date / platform unsupported. Raises ``UpdateCheckError``
    on network or parse failure.
    """
    from lifegen_editor import __version__ as current

    manifest = fetch_manifest(manifest_url())
    remote = manifest.get("version", "0.0.0")
    if not is_newer(current, remote):
        return None
    asset = pick_asset(manifest, platform.system(), platform.machine())
    if asset is None:
        return None
    return manifest, asset
