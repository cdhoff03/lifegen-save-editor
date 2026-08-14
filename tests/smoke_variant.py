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

    # New-schema (v0.13/v0.7.7+) saves: status is a CatStatus dict.
    dict_status = {"group_history": [{"group": "1", "rank": "warrior", "moons_as": 0}],
                   "standing_history": [{"group": "1", "standing": ["member"], "near": True}]}
    lg_new = _clan([{
        "ID": "1", "status": dict_status, "moons": 40, "tortie_marking": None,
        "sprite_newborn": "newborn0", "faith": 0, "inventory": [], "revives": 0,
        "courage": 5, "df_mentor": None, "connected_dialogue": {},
    }])
    assert detect_variant(lg_new) is GameVariant.LIFEGEN, "LifeGen 0.7.7 key-set"
    print("OK  LifeGen v0.7.7 new-schema cat -> LIFEGEN")

    cg_new = _clan([{
        "ID": "1", "status": dict_status, "moons": 40, "tortie_marking": None,
        "sprite_newborn": "newborn0", "dark_forest_affinity": None,
        "starclan_affinity": None, "pronouns": {"en": []},
    }])
    assert detect_variant(cg_new) is GameVariant.CLANGEN, "ClanGen 0.13 key-set"
    print("OK  ClanGen v0.13 new-schema cat -> CLANGEN")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
