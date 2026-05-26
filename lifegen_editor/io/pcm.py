"""Pixel-Cat-Maker import / export.

Two formats are supported:
    1. JSON (`{pelt_name, pelt_color, eye_colour, ...}`) — exported via the tool's
       Save/Load button.
    2. Share URL (`https://cgen-tools.github.io/pixel-cat-maker/?peltName=...`) —
       the tool encodes the full editable state in URL query parameters.

The JSON format is appearance-only. Its ``accessory`` field is ``string |
string[] | null`` — we accept either shape on import and produce a list on
export (the pixel-cat-maker importer collapses to the first element, while
ClanGen and ManiiaKop-LifeGen treat lists natively).
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse

from ..sprites.compositor import NAME_TO_SPRITESNAME
from .cat_data import CatData, SPRITESNAME_TO_NAME

PCM_SHARE_BASE = "https://cgen-tools.github.io/pixel-cat-maker/"


def _coerce_accessory_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [a for a in value if a]
    if isinstance(value, str) and value:
        return [value]
    return []


def parse_pcm_json(text_or_obj: str | dict) -> CatData:
    """Parse the JSON shape exported by pixel-cat-maker's Save button."""
    data: dict[str, Any]
    if isinstance(text_or_obj, str):
        data = json.loads(text_or_obj)
    else:
        data = text_or_obj

    pelt_name = data.get("pelt_name") or "SingleColour"
    is_tortie = pelt_name in ("Tortie", "Calico")
    if is_tortie:
        base = data.get("tortie_base") or "single"
        actual_pelt = SPRITESNAME_TO_NAME.get(base, "TwoColour")
    else:
        actual_pelt = pelt_name

    tortie_pattern_raw = data.get("tortie_pattern")
    tortie_pattern = (
        SPRITESNAME_TO_NAME.get(tortie_pattern_raw) if tortie_pattern_raw else None
    )

    accessories = _coerce_accessory_list(data.get("accessory"))

    scars_raw = data.get("scars")
    if scars_raw is None:
        scars: list[str] = []
    elif isinstance(scars_raw, list):
        scars = list(scars_raw)
    else:
        scars = [scars_raw]

    return CatData(
        pelt_name=actual_pelt,
        colour=data.get("pelt_color") or "CREAM",
        skin=data.get("skin") or "BLACK",
        eye_colour=data.get("eye_colour") or "YELLOW",
        eye_colour2=data.get("eye_colour2"),
        tint=data.get("tint") or "none",
        white_patches_tint=data.get("white_patches_tint") or "none",
        white_patches=data.get("white_patches"),
        points=data.get("points"),
        vitiligo=data.get("vitiligo"),
        accessories=accessories,
        scars=scars,
        is_tortie=is_tortie,
        tortie_mask=data.get("pattern") if is_tortie else None,
        tortie_pattern=tortie_pattern,
        tortie_colour=data.get("tortie_color"),
        reverse=bool(data.get("reverse", False)),
    )


def to_pcm_json(cat: CatData, *, indent: int = 4) -> str:
    """Serialize to pixel-cat-maker JSON shape. Writes ``accessory`` as a list;
    the live tool's importer accepts both shapes."""
    data = {
        "pelt_name": cat.name,
        "pelt_color": cat.colour,
        "eye_colour": cat.eye_colour,
        "eye_colour2": cat.eye_colour2,
        "reverse": cat.reverse,
        "white_patches": cat.white_patches,
        "vitiligo": cat.vitiligo,
        "points": cat.points,
        "white_patches_tint": cat.white_patches_tint,
        "pattern": cat.tortie_mask if cat.is_tortie else None,
        "tortie_base": (
            NAME_TO_SPRITESNAME.get(cat.pelt_name, "single") if cat.is_tortie else None
        ),
        "tortie_pattern": (
            NAME_TO_SPRITESNAME.get(cat.tortie_pattern, "")
            if cat.is_tortie and cat.tortie_pattern
            else None
        ),
        "tortie_color": cat.tortie_colour if cat.is_tortie else None,
        "skin": cat.skin,
        "tint": cat.tint,
        "scars": cat.scars[0] if cat.scars else None,
        # Either format works for the official importer; lists let other tools
        # round-trip multi-accessory cats without information loss.
        "accessory": list(cat.accessories) if cat.accessories else None,
    }
    return json.dumps(data, indent=indent)


def parse_pcm_url(url: str) -> CatData:
    """Parse the shareable URL the tool generates from the Copy URL button.

    The URL format only encodes a single ``accessory`` value (the live tool's
    UI is single-select). Multi-accessory state is only preserved through JSON
    or save-file paths."""
    parts = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    cat = CatData()

    if params.get("version") != "v1":
        return cat

    def _opt(key: str) -> str | None:
        v = params.get(key)
        return v if v else None

    cat.is_tortie = params.get("isTortie") == "true"
    cat.shading = params.get("shading") == "true"
    cat.reverse = params.get("reverse") == "true"
    if v := _opt("backgroundColour"):
        cat.background_colour = v
    if v := _opt("peltName"):
        cat.pelt_name = v
    if v := _opt("colour"):
        cat.colour = v
    if v := _opt("tint"):
        cat.tint = v
    if v := _opt("skinColour"):
        cat.skin = v
    if v := _opt("eyeColour"):
        cat.eye_colour = v
    cat.eye_colour2 = _opt("eyeColour2")
    cat.white_patches = _opt("whitePatches")
    cat.points = _opt("points")
    if v := _opt("whitePatchesTint"):
        cat.white_patches_tint = v
    cat.vitiligo = _opt("vitiligo")
    if v := _opt("accessory"):
        cat.accessories = [v]
    if v := _opt("scar"):
        cat.scars = [v]
    cat.tortie_mask = _opt("tortieMask")
    cat.tortie_colour = _opt("tortieColour")
    cat.tortie_pattern = _opt("tortiePattern")
    if v := params.get("spriteNumber"):
        try:
            cat.sprite_number = int(v)
        except ValueError:
            pass
    return cat


def to_pcm_url(cat: CatData, base: str = PCM_SHARE_BASE) -> str:
    """Build a shareable URL identical in shape to the pixel-cat-maker output.

    Only the first accessory survives the round-trip — the URL schema has a
    single slot."""
    params = {
        "shading": str(cat.shading).lower(),
        "reverse": str(cat.reverse).lower(),
        "isTortie": str(cat.is_tortie).lower(),
        "backgroundColour": cat.background_colour,
        "tortieMask": cat.tortie_mask or "",
        "tortieColour": cat.tortie_colour or "",
        "tortiePattern": cat.tortie_pattern or "",
        "peltName": cat.pelt_name,
        "spriteNumber": str(cat.sprite_number),
        "colour": cat.colour,
        "tint": cat.tint,
        "skinColour": cat.skin,
        "eyeColour": cat.eye_colour,
        "eyeColour2": cat.eye_colour2 or "",
        "whitePatches": cat.white_patches or "",
        "points": cat.points or "",
        "whitePatchesTint": cat.white_patches_tint if cat.white_patches else "",
        "vitiligo": cat.vitiligo or "",
        "accessory": cat.accessories[0] if cat.accessories else "",
        "scar": cat.scars[0] if cat.scars else "",
        "version": "v1",
    }
    return f"{base.rstrip('?')}?{urlencode(params)}"
