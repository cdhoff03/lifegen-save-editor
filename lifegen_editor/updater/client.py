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
import urllib.request
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
