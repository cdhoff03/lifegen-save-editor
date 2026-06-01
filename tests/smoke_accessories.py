"""Render cats wearing newly-imported LifeGen accessory categories.

Verifies the import produced valid index entries + sheets: each accessory must
crop a non-empty (has some opaque pixels) sprite for a normal adult pose.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.io import CatData
from lifegen_editor.sprites import SpriteLoader, draw_cat

# one representative id from each newly-imported category
SAMPLES = {
    "flower": "DAISIES",
    "smallAnimal": "WHITE RABBIT",
    "crafted": "WILLOWBARK BAG",
    "snake": "KINGSNAKE",
    "fruit": "CHERRY",
    "aliveInsect": "BEE",
    "deadInsect": "MONARCH",
    "plant2": "PUMPKIN",
    "tail2": "SEAWEED",
}


def _opaque_pixels(img) -> int:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return sum(1 for px in img.getdata() if px[3] > 0)


def main() -> int:
    loader = SpriteLoader()
    outdir = Path(__file__).resolve().parent / "out"
    outdir.mkdir(exist_ok=True)

    # baseline cat with no accessory, to compare opaque-pixel counts
    base = CatData(pelt_name="SingleColour", colour="WHITE", eye_colour="BLUE")
    base_px = _opaque_pixels(draw_cat(base.to_pelt(), 3, loader))

    failures = 0
    for cat_label, acc in SAMPLES.items():
        cat = CatData(pelt_name="SingleColour", colour="WHITE", eye_colour="BLUE",
                      accessories=[acc])
        try:
            img = draw_cat(cat.to_pelt(), 3, loader)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {cat_label} ({acc}): render error {e}")
            failures += 1
            continue
        px = _opaque_pixels(img)
        # the accessory should add (or at least change) opaque pixels vs baseline
        ok = px != base_px and px > 0
        img.save(outdir / f"acc_{cat_label}.png")
        print(f"{'OK  ' if ok else 'FAIL'} {cat_label:12s} {acc:16s} px={px} (base {base_px})")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
