#!/usr/bin/env python3
"""Import sprite assets + catalogs from an official LifeGen/ClanGen checkout.

Targets the data-driven sprite layout introduced by ClanGen v0.13 and merged
into LifeGen v0.7.7.0: every sheet is described by ``sprites/dicts/*.json``,
laid out as blocks of 3x9 cells of 50px (26 named poses, cell 27 unused). A
block at data position ``(col, row)`` starts at pixel ``(col*150, row*450)``.

Running this against a LifeGen checkout regenerates the editor's bundled
assets wholesale (LifeGen's dicts are a superset of ClanGen's with identical
shared content, so one import covers both games):

  - assets/config/spritesIndex.json   logical sprite name -> sheet + offsets
  - assets/config/spritesOffsetMap.json  pose index 0..25 -> cell in block
  - assets/config/peltInfo.json       scar + accessory category id lists
  - assets/config/tint.json, white_patches_tint.json  (copied verbatim)
  - assets/config/conversion_dict.json  old-save id conversion maps (verbatim)
  - assets/sprites/*.png              referenced sheets (stale ones removed)

Collars are palette-mapped upstream (style block + palette PNG rows recoloured
at load time). We bake every recolour once at import into a synthetic
``acc_collars_baked.png`` so the editor's loader/compositor stay dumb crops.

Usage:  python scripts/import_from_game.py /path/to/lifegen-checkout [output-root]

``output-root`` defaults to this repo; tests pass a temp dir (expects/creates
``<root>/assets/config`` and ``<root>/assets/sprites``).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from PIL import Image

TILE = 50
SHEET_LAYOUT = [3, 9]
BLOCK_W, BLOCK_H = SHEET_LAYOUT[0] * TILE, SHEET_LAYOUT[1] * TILE  # 150 x 450

# The 26 named poses, in sheet order (row-major within a block). Must match
# POSE_NAMES in lifegen_editor/ui/options.py and the game's pose_sprite_data.
POSES = [
    "newborn0", "newborn1", "newborn2",
    "kitten0", "kitten1", "kitten2",
    "adolescent_short0", "adolescent_short1", "adolescent_short2",
    "adolescent_long0", "adolescent_long1", "adolescent_long2",
    "adult_short0", "adult_short1", "adult_short2",
    "adult_long0", "adult_long1", "adult_long2",
    "senior0", "senior1", "senior2",
    "para_adult_short0", "para_adult_long0", "para_young0",
    "sick_adult0", "sick_young0",
]

# (dict file, peltInfo category key) — every non-collar accessory dict.
# The sprite-name prefix is the dict's own "spritesheet" value.
ACCESSORY_DICTS = [
    ("plant_sprite_data.json", "plant_accessories"),
    ("wild_sprite_data.json", "wild_accessories"),
    ("wild2_sprite_data.json", "wild2_accessories"),
    ("alive_insect_data.json", "aliveInsect_accessories"),
    ("dead_insect_data.json", "deadInsect_accessories"),
    ("plant2_sprite_data.json", "plant2_accessories"),
    ("sophisticated_data.json", "sophisticated_accessories"),
    ("fruit_data.json", "fruit_accessories"),
    ("flowercrowns_data.json", "flowercrown_accessories"),
    ("misc_accs_data.json", "misc_accessories"),
    ("misc2_accs_data.json", "misc2_accessories"),
    ("harness_data.json", "harness_accessories"),
    ("smallanimals_data.json", "smallanimals_accessories"),
]

# All six white-patch family dicts share the editor's single "white" prefix —
# the index carries each name's sheet, so consumers don't care about the split.
WHITE_DICTS = [
    "white_patches_little_sprite_data.json",
    "white_patches_mid_sprite_data.json",
    "white_patches_high_sprite_data.json",
    "white_patches_mostly_sprite_data.json",
    "white_patches_points_sprite_data.json",
    "white_patches_vitiligo_sprite_data.json",
]

# Single-block sheets: upstream sheet file -> editor logical sprite name
# (the editor's compositor keeps its historical names, e.g. "lines").
SINGLE_BLOCKS = {
    "lineart": "lines",
    "lineart_sc": "lineartdead",
    "lineart_df": "lineartdf",
    "shader_mask": "shaders",
    "shader_lighting": "lighting",
    "heterochromiamask": "heterochromiamask",
}
# Upstream swaps the lineart *files* on April Fools; the editor keeps separate
# logical names, pointed at the _aprilfools variants.
APRILFOOLS_BLOCKS = {
    "lineart_aprilfools": "aprilfoolslineart",
    "lineart_sc_aprilfools": "aprilfoolslineartdead",
    "lineart_df_aprilfools": "aprilfoolslineartdf",
}


def _row_names(row) -> list[str]:
    """A sprite_list row is either a list of names or a {name: metadata} dict."""
    return list(row) if isinstance(row, (list, dict)) else []


def main(argv) -> int:
    if len(argv) not in (2, 3):
        print(__doc__)
        return 2
    game = Path(argv[1])
    dicts = game / "sprites" / "dicts"
    game_sprites = game / "sprites"
    if not dicts.is_dir():
        print(f"ERR: {dicts} not found — expected a v0.7.7+/v0.13+ checkout")
        return 1

    root = Path(argv[2]) if len(argv) == 3 else Path(__file__).resolve().parent.parent
    cfg = root / "assets" / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    asset_sprites = root / "assets" / "sprites"
    asset_sprites.mkdir(parents=True, exist_ok=True)

    def load(name: str) -> dict:
        return json.loads((dicts / name).read_text(encoding="utf-8"))

    errors: list[str] = []
    index: dict[str, dict] = {}
    sheets_needed: set[str] = set()
    counts: dict[str, int] = {}

    def emit(name: str, sheet: str, col: int, row: int, group: str) -> None:
        if name in index:
            errors.append(f"duplicate sprite name {name!r}")
        index[name] = {
            "spritesheet": sheet,
            "xOffset": float(col * BLOCK_W),
            "yOffset": float(row * BLOCK_H),
        }
        sheets_needed.add(sheet)
        counts[group] = counts.get(group, 0) + 1

    def emit_sheet(data: dict, prefix: str, group: str, category: list | None = None):
        sheet = data["spritesheet"]
        for row, names in enumerate(data["sprite_list"]):
            for col, sprite in enumerate(_row_names(names)):
                emit(f"{prefix}{sprite}", sheet, col, row, group)
                if category is not None:
                    category.append(sprite)

    # --- poses ---------------------------------------------------------------
    pose_data = load("pose_sprite_data.json")
    if pose_data["sheet_layout"] != SHEET_LAYOUT:
        errors.append(f"sheet_layout {pose_data['sheet_layout']} != {SHEET_LAYOUT}")
    if pose_data["poses"] != POSES:
        errors.append("upstream pose list differs from POSES — update this script "
                      "AND lifegen_editor/ui/options.py POSE_NAMES together")
    offset_map = [{"x": i % 3, "y": i // 3} for i in range(len(POSES))]

    # --- pelt colour sheets --------------------------------------------------
    pelt_data = load("pelt_sprite_data.json")
    for sheet in pelt_data["spritesheet"]:
        prefix = sheet.removeprefix("colours_")
        for row, names in enumerate(pelt_data["sprite_list"]):
            for col, colour in enumerate(_row_names(names)):
                emit(f"{prefix}{colour}", sheet, col, row, "pelts")

    # --- eyes (multi-sheet form, single "eyes" sheet in practice) ------------
    eye_data = load("eye_sprite_data.json")
    for sheet in eye_data["spritesheet"]:
        for row, names in enumerate(eye_data["sprite_list"]):
            for col, colour in enumerate(_row_names(names)):
                emit(f"{sheet}{colour}", sheet, col, row, "eyes")

    # --- white patches / points / vitiligo -----------------------------------
    for fname in WHITE_DICTS:
        emit_sheet(load(fname), "white", "white_patches")

    # --- tortie masks, scars, skins ------------------------------------------
    emit_sheet(load("tortie_patches_sprite_data.json"), "tortiemask", "tortie_masks")
    pelt_info: dict[str, list] = {"scars1": [], "scars2": [], "scars3": []}
    emit_sheet(load("scar_sprite_data.json"), "scars", "scars", pelt_info["scars1"])
    emit_sheet(load("scar_missing_sprite_data.json"), "scars", "scars", pelt_info["scars2"])
    emit_sheet(load("skin_sprite_data.json"), "skin", "skins")

    # --- lineart / shaders / heterochromia mask ------------------------------
    for sheet, logical in SINGLE_BLOCKS.items():
        emit(logical, sheet, 0, 0, "single_blocks")
    for sheet, logical in APRILFOOLS_BLOCKS.items():
        if (game_sprites / f"{sheet}.png").is_file():
            emit(logical, sheet, 0, 0, "single_blocks")

    # --- standard accessories ------------------------------------------------
    for fname, category in ACCESSORY_DICTS:
        pelt_info[category] = []
        data = load(fname)
        emit_sheet(data, data["spritesheet"], "accessories", pelt_info[category])

    # --- palette-mapped collars: bake recolours into one synthetic sheet -----
    collar_data = load("collar_sprite_data.json")
    src_sheet = Image.open(game_sprites / f"{collar_data['spritesheet']}.png").convert("RGBA")
    collar_ids: list[str] = []
    baked_blocks: list[tuple[str, Image.Image]] = []
    for row, styles in enumerate(collar_data["style_data"]):
        for col, (style, palettes) in enumerate(styles.items()):
            block = src_sheet.crop((col * BLOCK_W, row * BLOCK_H,
                                    (col + 1) * BLOCK_W, (row + 1) * BLOCK_H))
            pal_png = game_sprites / "palettes" / f"{collar_data['spritesheet']}{style}_palette.png"
            palette = Image.open(pal_png).convert("RGBA")
            if palette.size[1] != len(palettes) + 1:
                errors.append(f"palette {pal_png.name}: {palette.size[1]} rows "
                              f"!= 1 base + {len(palettes)} palettes")
                continue
            base = [palette.getpixel((x, 0)) for x in range(palette.size[0])]
            block_px = list(block.getdata())
            for k, pal_name in enumerate(palettes, start=1):
                mapping = {
                    base[x]: palette.getpixel((x, k)) for x in range(palette.size[0])
                }
                # ponytail: exact-RGBA match, no tolerance — upstream pygame
                # PixelArray.replace() is exact too.
                recoloured = Image.new("RGBA", block.size)
                recoloured.putdata([mapping.get(p, p) for p in block_px])
                collar_id = f"{style}_{pal_name}"
                collar_ids.append(collar_id)
                baked_blocks.append((collar_id, recoloured))
    per_row = 10
    baked = Image.new(
        "RGBA",
        (per_row * BLOCK_W, ((len(baked_blocks) + per_row - 1) // per_row) * BLOCK_H),
        (0, 0, 0, 0),
    )
    for i, (collar_id, block) in enumerate(baked_blocks):
        col, row = i % per_row, i // per_row
        baked.paste(block, (col * BLOCK_W, row * BLOCK_H))
        emit(f"acc_collars{collar_id}", "acc_collars_baked", col, row, "collars")
    pelt_info["collars"] = collar_ids

    # --- geometry sanity: every block must lie inside its PNG ----------------
    for name, info in index.items():
        sheet = info["spritesheet"]
        if sheet == "acc_collars_baked":
            size = baked.size
        else:
            png = game_sprites / f"{sheet}.png"
            if not png.is_file():
                errors.append(f"{name}: sheet {sheet}.png missing from checkout")
                continue
            size = Image.open(png).size
        if info["xOffset"] + BLOCK_W > size[0] or info["yOffset"] + BLOCK_H > size[1]:
            errors.append(f"{name}: block at ({info['xOffset']}, {info['yOffset']}) "
                          f"outside {sheet}.png {size}")

    dupes = set()
    all_categories = [k for k in pelt_info if k.endswith("_accessories")] + ["collars"]
    seen_ids: set[str] = set()
    for key in all_categories:
        for acc in pelt_info[key]:
            (dupes if acc in seen_ids else seen_ids).add(acc)
    if dupes:
        print(f"WARNING: accessory ids in multiple categories: {sorted(dupes)}")

    if errors:
        for e in errors:
            print(f"ERR: {e}")
        return 1

    # --- write outputs -------------------------------------------------------
    for stale in asset_sprites.glob("*.png"):
        stale.unlink()
    sheets_needed.discard("acc_collars_baked")
    for sheet in sorted(sheets_needed):
        shutil.copy2(game_sprites / f"{sheet}.png", asset_sprites / f"{sheet}.png")
    baked.save(asset_sprites / "acc_collars_baked.png")

    (cfg / "spritesIndex.json").write_text(json.dumps(index, indent=2) + "\n")
    (cfg / "spritesOffsetMap.json").write_text(json.dumps(offset_map, indent=2) + "\n")
    (cfg / "peltInfo.json").write_text(json.dumps(pelt_info, indent=2) + "\n")
    for extra in ("tint.json", "white_patches_tint.json"):
        shutil.copy2(dicts / extra, cfg / extra)
    shutil.copy2(game / "resources" / "dicts" / "conversion_dict.json",
                 cfg / "conversion_dict.json")

    print(f"wrote {len(index)} index entries, {len(POSES)} poses")
    for group in sorted(counts):
        print(f"  {group}: {counts[group]}")
    print(f"copied {len(sheets_needed)} sheets + baked acc_collars_baked.png "
          f"({len(baked_blocks)} collars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
