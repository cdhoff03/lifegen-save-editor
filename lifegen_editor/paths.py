"""Locate bundled assets regardless of where the package is run from.

Resolution order:
    1. ``LIFEGEN_EDITOR_ASSETS`` env var (override for testing)
    2. ``sys._MEIPASS / assets`` (PyInstaller frozen bundle)
    3. ``<repo>/assets`` (running from source)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_assets_dir() -> Path:
    override = os.environ.get("LIFEGEN_EDITOR_ASSETS")
    if override:
        return Path(override)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass) / "assets"
    return Path(__file__).resolve().parent.parent / "assets"


ASSETS_DIR = _find_assets_dir()
SPRITES_DIR = ASSETS_DIR / "sprites"
CONFIG_DIR = ASSETS_DIR / "config"
