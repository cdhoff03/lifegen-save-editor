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
