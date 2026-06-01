"""Verify ClanGen vs LifeGen variant detection from loaded cats."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.saves import GameVariant, detect_variant
from lifegen_editor.saves.save_io import Clan, SaveCat


def _clan(cat_dicts: list[dict]) -> Clan:
    cats = [SaveCat(index=i, raw=raw) for i, raw in enumerate(cat_dicts)]
    return Clan(name="Test", path=Path("/tmp/Test"), cats=cats)


def main() -> int:
    # ClanGen: medicine cat, no LifeGen-only keys.
    cg = _clan([
        {"ID": "1", "status": "medicine cat", "moons": 30, "accessory": None},
        {"ID": "2", "status": "warrior", "moons": 40},
    ])
    assert detect_variant(cg) is GameVariant.CLANGEN, "plain ClanGen save"
    print("OK  ClanGen save -> CLANGEN")

    # LifeGen by status vocabulary alone (the queen career track).
    lg_status = _clan([{"ID": "1", "status": "queen's apprentice", "moons": 30}])
    assert detect_variant(lg_status) is GameVariant.LIFEGEN, "queen's apprentice status"
    print("OK  'queen's apprentice' status -> LIFEGEN")

    # LifeGen by a single LifeGen-only key, even with generic statuses.
    lg_key = _clan([{"ID": "1", "status": "warrior", "moons": 40, "faith": 0}])
    assert detect_variant(lg_key) is GameVariant.LIFEGEN, "faith key"
    print("OK  'faith' key -> LIFEGEN")

    lg_acc = _clan([{"ID": "1", "status": "warrior", "accessories": [], "inventory": []}])
    assert detect_variant(lg_acc) is GameVariant.LIFEGEN, "accessories/inventory"
    print("OK  accessories/inventory -> LIFEGEN")

    lg_queen = _clan([{"ID": "1", "status": "queen", "moons": 40}])
    assert detect_variant(lg_queen) is GameVariant.LIFEGEN, "queen status"
    print("OK  'queen' status -> LIFEGEN")

    # Empty clan defaults to ClanGen.
    assert detect_variant(_clan([])) is GameVariant.CLANGEN, "empty -> CLANGEN"
    print("OK  empty clan -> CLANGEN")

    # Malformed cats are tolerated.
    assert detect_variant(_clan([{"ID": "1"}, {"junk": True}])) is GameVariant.CLANGEN
    print("OK  malformed/minimal cats tolerated")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
