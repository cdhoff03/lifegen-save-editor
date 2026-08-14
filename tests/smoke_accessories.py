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

# one representative id from each imported category (v0.7.7.5 vocabulary)
SAMPLES = {
    "plant": "MAPLE LEAF",
    "wild": "RED FEATHERS",
    "wild2": "LILYPAD",
    "collar": "LEATHER_crimson",       # palette-baked
    "collar_grad": "NYLON_GRADIENT_rainbow",  # widest palette (25 slots)
    "aliveInsect": "BROWN SNAIL",
    "deadInsect": "LUNAR MOTH",
    "plant2": "PUMPKIN",
    "sophisticated": "MOONHAT",
    "fruit": "BLACKBERRY",
    "flowercrown": "PINKFLOWERCROWN",
    "misc": "TIDE",
    "misc2": "ORANGEBUTTERFLY",
    "harness": "REDHARNESS",
    "smallanimals": "GRAY SQUIRREL",
}


def _opaque_pixels(img) -> int:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return sum(1 for px in img.getdata() if px[3] > 0)


def main() -> int:
    loader = SpriteLoader()
    outdir = Path(__file__).resolve().parent / "out"
    outdir.mkdir(exist_ok=True)

    # baseline cat with no accessory to compare against
    base = CatData(pelt_name="SingleColour", colour="WHITE", eye_colour="BLUE")
    base_img = draw_cat(base.to_pelt(), 12, loader)
    base_px = _opaque_pixels(base_img)
    base_bytes = base_img.tobytes()

    failures = 0
    for cat_label, acc in SAMPLES.items():
        cat = CatData(pelt_name="SingleColour", colour="WHITE", eye_colour="BLUE",
                      accessories=[acc])
        try:
            img = draw_cat(cat.to_pelt(), 12, loader)
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {cat_label} ({acc}): render error {e}")
            failures += 1
            continue
        px = _opaque_pixels(img)
        # the accessory must change the rendered image (collars sit entirely
        # inside the cat silhouette, so compare content, not opaque count)
        ok = px > 0 and img.tobytes() != base_bytes
        img.save(outdir / f"acc_{cat_label}.png")
        print(f"{'OK  ' if ok else 'FAIL'} {cat_label:12s} {acc:16s} px={px} (base {base_px})")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
