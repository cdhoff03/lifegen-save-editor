"""Run scripts/import_from_game.py against a real LifeGen checkout and verify
the generated assets: category counts, offset map, and that every sprite
family actually renders non-empty crops.

Needs a v0.7.7+ LifeGen checkout; pass its path as argv[1] or set
LIFEGEN_CHECKOUT. Skips (exit 0) when none is available so the suite can run
without a checkout.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.sprites.loader import SpriteLoader

EXPECTED_COUNTS = {
    "pelts": 266, "eyes": 22, "white_patches": 130, "tortie_masks": 43,
    "scars": 53, "skins": 18, "collars": 99,
}
EXPECTED_ACCESSORY_IDS = 380  # 281 standard + 99 collars
SAMPLE_SPRITES = [
    "singleWHITE", "tabbyGOLDEN", "eyesGREEN", "whiteANY", "tortiemaskONE",
    "scarsONE", "skinBLACK", "acc_plantsMAPLE LEAF", "acc_collarsLEATHER_crimson",
    "lines", "lineartdead", "lineartdf", "shaders", "lighting", "heterochromiamask",
]


def main() -> int:
    checkout = (
        Path(sys.argv[1]) if len(sys.argv) > 1
        else Path(os.environ.get("LIFEGEN_CHECKOUT", ""))
    )
    if not checkout or not (checkout / "sprites" / "dicts").is_dir():
        print("SKIP: no LifeGen checkout (pass path or set LIFEGEN_CHECKOUT)")
        return 0

    repo = Path(__file__).resolve().parent.parent
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, str(repo / "scripts" / "import_from_game.py"),
             str(checkout), tmp],
            capture_output=True, text=True,
        )
        print(proc.stdout, end="")
        assert proc.returncode == 0, proc.stdout + proc.stderr

        cfg = Path(tmp) / "assets" / "config"
        index = json.loads((cfg / "spritesIndex.json").read_text())
        offsets = json.loads((cfg / "spritesOffsetMap.json").read_text())
        pelt_info = json.loads((cfg / "peltInfo.json").read_text())

        assert len(offsets) == 26, len(offsets)
        acc_ids = sum(
            len(v) for k, v in pelt_info.items()
            if k.endswith("_accessories") or k == "collars"
        )
        assert acc_ids == EXPECTED_ACCESSORY_IDS, acc_ids
        assert len(pelt_info["scars1"]) == 45 and len(pelt_info["scars2"]) == 8

        # spot-check the printed group counts against expectations
        for group, want in EXPECTED_COUNTS.items():
            assert f"{group}: {want}" in proc.stdout, f"{group} != {want}"

        loader = SpriteLoader(
            sprites_dir=Path(tmp) / "assets" / "sprites", config_dir=cfg
        )
        for name in SAMPLE_SPRITES:
            for pose in (12, 25):
                img = loader.get_sprite(name, pose)
                assert img is not None, name
                opaque = sum(1 for p in img.getdata() if p[3] > 0)
                # some art is legitimately empty at the sick/para poses
                # (e.g. closed eyes on sick_young0) — require content only
                # at the standard adult pose
                if pose == 12:
                    assert opaque > 0, f"{name} pose {pose} rendered empty"
        print(f"OK  {len(index)} index entries, all sample sprites render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
