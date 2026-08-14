"""Render a few sample cats to verify the compositor port works end-to-end.

Run: .venv/bin/python tests/smoke_compositor.py
Produces PNGs in tests/out/.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.sprites import SpriteLoader, draw_cat
from lifegen_editor.sprites.compositor import Pelt

OUT_DIR = Path(__file__).resolve().parent / "out"


def main() -> int:
    OUT_DIR.mkdir(exist_ok=True)
    loader = SpriteLoader()

    cases = [
        ("plain_cream_single", Pelt(name="SingleColour", colour="CREAM", skin="PINK", eye_colour="YELLOW")),
        ("tabby_brown_eyes_amber", Pelt(name="Tabby", colour="BROWN", skin="BLACK", eye_colour="AMBER")),
        ("torbie_calico", Pelt(
            name="Tortie", colour="GINGER", tortie_base="tabby",
            tortie_colour="BLACK", tortie_pattern="tabby", pattern="ONE",
            skin="BLACK", eye_colour="GREEN",
        )),
        ("white_socks", Pelt(
            name="SingleColour", colour="BLACK", skin="BLACK", eye_colour="BLUE",
            white_patches="LITTLE",
        )),
        ("heterochromia_with_collar", Pelt(
            name="Smoke", colour="DARKGREY", skin="BLACK",
            eye_colour="BLUE", eye_colour2="YELLOW",
            accessories=["LEATHER_crimson"],
        )),
        ("stacked_accessories", Pelt(
            name="SingleColour", colour="WHITE", skin="PINK", eye_colour="GREEN",
            accessories=["LEATHER_blue", "MAPLE LEAF"],  # collar with leaf on top
        )),
        ("dead_starclan", Pelt(
            name="Tabby", colour="GOLDEN", skin="PINK", eye_colour="GREEN",
        )),
        ("reversed_with_shading", Pelt(
            name="Bengal", colour="GINGER", skin="PINK", eye_colour="AMBER",
            reverse=True,
        )),
    ]
    pose = 12  # adult_short0

    # Heterochromia (mask-clipped second eye) and baked collars must actually
    # change the render vs their plain counterparts.
    het = cases[4][1]
    plain = Pelt(name=het.name, colour=het.colour, skin=het.skin, eye_colour=het.eye_colour)
    assert draw_cat(het, pose, loader).tobytes() != draw_cat(plain, pose, loader).tobytes(), \
        "heterochromia + collar render identical to plain cat"

    for name, pelt in cases:
        try:
            extra = {}
            if name == "dead_starclan":
                extra["dead"] = True
            if name == "reversed_with_shading":
                extra["shading"] = True
            img = draw_cat(pelt, pose, loader, **extra)
            scaled = img.resize((img.width * 4, img.height * 4), resample=0)  # NEAREST
            out_path = OUT_DIR / f"{name}.png"
            scaled.save(out_path)
            print(f"OK  {name:30s} -> {out_path}")
        except Exception as e:
            print(f"FAIL {name:30s} {type(e).__name__}: {e}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
