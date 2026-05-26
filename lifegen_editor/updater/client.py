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
