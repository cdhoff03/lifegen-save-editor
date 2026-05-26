"""Enumerations for dropdown / multi-select UI controls.

Values extracted from the bundled asset configs at runtime, with a few
fixed sub-lists (points / vitiligo) that the underlying games hard-code.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..paths import CONFIG_DIR
from ..sprites.compositor import NAME_TO_SPRITESNAME

# Patterns toggled separately via is_tortie — exclude from the main pelt dropdown.
PELT_NAMES: list[str] = [n for n in NAME_TO_SPRITESNAME if n not in ("Tortie", "Calico")]

POINT_MARKINGS: list[str] = ["COLOURPOINT", "RAGDOLL", "SEPIAPOINT", "MINKPOINT", "SEALPOINT"]
VITILIGO_MARKINGS: list[str] = [
    "VITILIGO", "VITILIGOTWO", "MOON", "PHANTOM", "KARPATI",
    "POWDER", "BLEACHED", "SMOKEY",
]
LINEART_STYLES: list[tuple[str, dict]] = [
    ("Normal", {"dead": False, "dark_forest": False, "april_fools": False}),
    ("Dead (StarClan)", {"dead": True, "dark_forest": False, "april_fools": False}),
    ("Dark Forest", {"dead": True, "dark_forest": True, "april_fools": False}),
    ("April Fools", {"dead": False, "dark_forest": False, "april_fools": True}),
]

# How many poses the offset map defines.
POSE_COUNT = 21


@lru_cache(maxsize=1)
def _index() -> dict:
    with (CONFIG_DIR / "spritesIndex.json").open() as f:
        return json.load(f)


def _extract(prefix: str) -> list[str]:
    pat = re.compile(rf"^{re.escape(prefix)}([A-Z0-9_-]+)$")
    out: set[str] = set()
    for key in _index():
        m = pat.match(key)
        if m:
            out.add(m.group(1))
    return sorted(out)


def colours() -> list[str]:
    return _extract("single")


def eye_colours() -> list[str]:
    # "eyes" prefix matches both eyes2 and the primary list; strip the "2*" entries.
    return sorted({c for c in _extract("eyes") if not c.startswith("2")})


def secondary_eye_colours() -> list[str]:
    # eye2 sprites use names like "eyes2YELLOW".
    return _extract("eyes2")


def skin_colours() -> list[str]:
    return _extract("skin")


def all_white_patches() -> list[str]:
    """Every white-patch / point / vitiligo sprite. Used as the dropdown values
    for `white_patches` since the underlying game treats markings as one big set."""
    return _extract("white")


def white_patches_only() -> list[str]:
    """All white sprites minus the ones reserved as points / vitiligo."""
    reserved = set(POINT_MARKINGS) | set(VITILIGO_MARKINGS)
    return [w for w in all_white_patches() if w not in reserved]


def tortie_masks() -> list[str]:
    return _extract("tortiemask")


def tortie_pattern_names() -> list[str]:
    # Single-colour mask works as a tortie overlay too; "Single" is special-cased
    # by the compositor.
    return [n for n in PELT_NAMES if n not in ("Tortie", "Calico")]


@lru_cache(maxsize=1)
def _pelt_info() -> dict:
    with (CONFIG_DIR / "peltInfo.json").open() as f:
        return json.load(f)


def plant_accessories() -> list[str]:
    return sorted(set(_pelt_info()["plant_accessories"]))


def wild_accessories() -> list[str]:
    return sorted(set(_pelt_info()["wild_accessories"]))


def collars() -> list[str]:
    return list(_pelt_info()["collars"])  # preserve original order


def all_accessories() -> list[tuple[str, str]]:
    """Return (label, value) pairs grouped by category."""
    out: list[tuple[str, str]] = []
    for acc in plant_accessories():
        out.append((f"Plant — {acc.title()}", acc))
    for acc in wild_accessories():
        out.append((f"Wild — {acc.title()}", acc))
    for acc in collars():
        out.append((f"Collar — {acc.title()}", acc))
    return out


def all_scars() -> list[str]:
    info = _pelt_info()
    return sorted(set(info["scars1"]) | set(info["scars2"]) | set(info["scars3"]))


@lru_cache(maxsize=1)
def tints() -> dict:
    with (CONFIG_DIR / "tint.json").open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def white_tints() -> dict:
    with (CONFIG_DIR / "white_patches_tint.json").open() as f:
        return json.load(f)


def tint_names() -> list[str]:
    t = tints()
    names = ["none"]
    names += sorted(t.get("tint_colours", {}).keys())
    names += sorted(t.get("dilute_tint_colours", {}).keys())
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def white_tint_names() -> list[str]:
    t = white_tints()
    names = ["none"]
    names += sorted(t.get("tint_colours", {}).keys())
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
