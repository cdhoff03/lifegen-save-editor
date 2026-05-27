"""Cross-platform swap-and-relaunch logic for the auto-updater.

This module is also the ``--finish-update`` entry point: when the running
app downloads a new build, it spawns the new exe with ``--finish-update``
plus install/staging/parent-PID args, then exits. The new exe (running
from a temp location) waits for the parent to exit, swaps the install
directory, and relaunches the freshly-installed exe.

See docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


# -----------------------------------------------------------------------------
# Locating the current install on disk.
# -----------------------------------------------------------------------------

def current_executable() -> Path:
    """Return the path of the running executable (frozen) or sys.executable (dev)."""
    return Path(sys.executable).resolve()


def current_install_dir() -> Path:
    """Return the install directory.

    Windows / Linux: parent of the running exe (PyInstaller --onedir layout).
    macOS: the ``*.app`` bundle root, walking up from sys.executable.
    """
    exe = current_executable()
    if sys.platform == "darwin":
        for p in [exe, *exe.parents]:
            if p.suffix == ".app":
                return p
        raise RuntimeError(f"could not locate .app bundle from {exe}")
    return exe.parent


# -----------------------------------------------------------------------------
# Atomic directory swap with rollback.
# -----------------------------------------------------------------------------


class SwapError(RuntimeError):
    """The swap could not be completed; the install is left untouched."""


def _swap_directories(install_dir: Path, staging_dir: Path) -> Path:
    """Atomically replace ``install_dir`` with ``staging_dir``.

    On success returns the path of the renamed-aside old install, so the
    caller can clean it up.

    On failure raises ``SwapError`` and leaves ``install_dir`` in its
    original state.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    old_path = install_dir.with_name(install_dir.name + f".old.{timestamp}")

    # Step 1: rename current install aside.
    try:
        install_dir.rename(old_path)
    except OSError as e:
        raise SwapError(f"could not rename install dir aside: {e}") from e

    # Step 2: move staging into place.
    try:
        shutil.move(str(staging_dir), str(install_dir))
    except OSError as e:
        # Try to roll back so the user is not left without an install.
        try:
            old_path.rename(install_dir)
        except OSError:
            pass
        raise SwapError(f"could not move staging into place: {e}") from e

    return old_path
