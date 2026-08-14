"""Convert pre-v0.13/v0.7.7 appearance ids to the current vocabulary.

The games rename ids across versions (collars ``CRIMSON`` -> ``LEATHER_crimson``,
tortie patches, retired accessories, …) and migrate old saves on load. This
module mirrors that load-time conversion — the data-driven part comes from the
vendored ``assets/config/conversion_dict.json`` (kept current by
``scripts/import_from_game.py``), the small inline maps below are frozen game
history copied from ``load_cat.py`` / ``Pelt.check_and_convert``.

Applied when reading a cat (save file or pixel-cat-maker import) so old saves
preview correctly; the converted ids are what gets written back, which migrates
the save the same way opening it in the current game would.
"""
from __future__ import annotations

import json
from functools import lru_cache

from ..paths import CONFIG_DIR
from ..ui.options import POINT_MARKINGS, VITILIGO_MARKINGS

# LifeGen accessory ids retired by the v0.7.7 "abbrev rework" (load_cat.py).
_ACCESSORY_RENAMES = {
    "SMALL COMET": "COMET MOTH",
    "LARGE COMET": "COMET MOTH",
    "RASPBERRY2": "RASPBERRY",
    "SMALL LUNA": "LUNA MOTH",
    "LARGE LUNA": "LUNA MOTH",
    "CHERRY2": "CHERRY",
    "RAINCOAT": "YELLOWRAINCOAT",
    "CHIMES": "CELESTIALCHIMES",
    "LADYBUG": "LADYBUGS",
    "YELLOWCROWN": "DANDELIONCROWN",
    "REDCROWN": "POPPYCROWN",
    "LILYPADCROWN": "LILYPADHAT",
    "ACORN2": "ACORN",
    "HOLLY2": "HOLLYLEAVES",
    "BLEEDING HEARTS2": "BLEEDING HEART BRANCH",
    "MOSS2": "FLOWER MOSS",
    "CLOVER2": "CLOVER",
    "CLOVERS": "CLOVER",
}

_WHITE_PATCH_RENAMES = {
    "POINTMARK": "SEALPOINT",
    "PANTS2": "PANTSTWO",
    "ANY2": "ANYTWO",
    "VITILIGO2": "VITILIGOTWO",
}

_TORTIE_MARKING_RENAMES = {
    "MINIMAL1": "MINIMALONE",
    "MINIMAL2": "MINIMALTWO",
    "MINIMAL3": "MINIMALTHREE",
    "MINIMAL4": "MINIMALFOUR",
}


@lru_cache(maxsize=1)
def _conversion() -> dict:
    try:
        with (CONFIG_DIR / "conversion_dict.json").open(encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def convert_accessories(accessories: list[str]) -> list[str]:
    """Map retired accessory / old collar ids to their current names."""
    collar_map = _conversion().get("collar_map", {})
    out: list[str] = []
    for acc in accessories:
        acc = _ACCESSORY_RENAMES.get(acc, acc)
        acc = collar_map.get(acc, acc)
        if acc and acc not in out:
            out.append(acc)
    return out


def normalize_tortie_pattern(raw: str) -> str:
    """Old saves store overlay patterns as e.g. ``tortietabby``/``tortiesolid``;
    current saves use the plain sheet prefix (``tabby``/``single``)."""
    if "tortie" in raw:
        raw = raw.lower().replace("tortie", "")
        if raw == "solid":
            raw = "single"
    return raw


def convert_cat_data(cat) -> None:
    """Apply every legacy appearance conversion to a ``CatData`` in place.

    Mirrors ``Pelt.check_and_convert``. (The ancient named-tortie pelts that
    ``tortie_map``/``calico_map`` cover predate every save format this editor
    has ever read — not handled.)
    """
    conv = _conversion()

    cat.accessories = convert_accessories(cat.accessories)

    # White patches: renames, creamy re-tints, then split out values that are
    # really points / vitiligo markings.
    wp = cat.white_patches
    if wp:
        wp = _WHITE_PATCH_RENAMES.get(wp, wp)
        creamy = conv.get("old_creamy_patches", {})
        if wp in creamy:
            wp = creamy[wp]
            cat.white_patches_tint = "darkcream"
        if wp in VITILIGO_MARKINGS:
            cat.vitiligo = cat.vitiligo or wp
            wp = None
        elif wp in POINT_MARKINGS:
            cat.points = cat.points or wp
            wp = None
        cat.white_patches = wp
    if cat.vitiligo == "VITILIGO2":
        cat.vitiligo = "VITILIGOTWO"

    # Eyes: renamed / combined heterochromia colours.
    if cat.eye_colour == "BLUE2":
        cat.eye_colour = "COBALT"
    if cat.eye_colour2 == "BLUE2":
        cat.eye_colour2 = "COBALT"
    if cat.eye_colour in ("BLUEYELLOW", "BLUEGREEN"):
        cat.eye_colour2 = "YELLOW" if cat.eye_colour == "BLUEYELLOW" else "GREEN"
        cat.eye_colour = "BLUE"

    # Tortie markings: rename, then the old-patch map (which also un-swaps the
    # base/overlay colours the way the game does).
    if cat.tortie_mask:
        cat.tortie_mask = _TORTIE_MARKING_RENAMES.get(cat.tortie_mask, cat.tortie_mask)
        old_patches = conv.get("old_tortie_patches", {})
        if cat.tortie_mask in old_patches:
            new_colour, new_marking = old_patches[cat.tortie_mask]
            if cat.tortie_colour:
                cat.colour = cat.tortie_colour
            cat.tortie_colour = new_colour
            cat.tortie_mask = new_marking
