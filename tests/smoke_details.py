"""Round-trip CatDetails through ClanGen and LifeGen save dicts."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.io import CatDetails, GameVariant


def main() -> int:
    # --- ClanGen cat: must NOT gain LifeGen-only keys -------------------------
    cg = {
        "ID": "001",
        "name_prefix": "Bright",
        "name_suffix": "heart",
        "status": "medicine cat",
        "moons": 42,
        "trait": "loyal",
        "facets": "8,12,4,9",
        "skill_dict": {"primary": "HEALER,15,False", "secondary": None, "hidden": None},
        "dead": False,
        "no_kits": False,
        "favourite": False,
        # appearance / lineage keys that must survive untouched
        "pelt_name": "Tabby",
        "parent1": "999",
    }
    d = CatDetails.from_save_cat(cg, GameVariant.CLANGEN)
    assert d.name_prefix == "Bright" and d.name_suffix == "heart"
    assert d.status == "medicine cat"
    assert (d.facet_lawfulness, d.facet_sociability, d.facet_aggression, d.facet_stability) == (8, 12, 4, 9)
    assert d.skill_primary_path == "HEALER" and d.skill_primary_points == 15
    # edit a few fields
    d.status = "warrior"
    d.moons = 30
    d.trait = "bold"
    d.facet_aggression = 16
    out = d.apply_to_save_cat(dict(cg), GameVariant.CLANGEN)
    assert out["status"] == "warrior" and out["moons"] == 30 and out["trait"] == "bold"
    assert out["facets"] == "8,12,16,9", out["facets"]
    assert out["skill_dict"]["primary"] == "HEALER,15,False"
    # no LifeGen-only keys invented
    for k in ("faith", "no_faith", "lock_faith", "courage", "compassion", "intelligence", "empathy"):
        assert k not in out, f"ClanGen cat must not gain {k}"
    # untouched fields preserved
    assert out["pelt_name"] == "Tabby" and out["parent1"] == "999" and out["ID"] == "001"
    print("OK  ClanGen round-trip; no LifeGen-only keys added; foreign fields preserved")

    # --- LifeGen cat: faith/skills/stats preserved & editable -----------------
    lg = {
        "ID": "002",
        "name_prefix": "Fire",
        "name_suffix": "star",
        "status": "healer",
        "moons": 50,
        "trait": "wise",
        "facets": "10,10,10,10",
        "skill_dict": {"primary": "STAR,29,False", "secondary": "MEDIATOR,5,True", "hidden": "ROGUE"},
        "faith": -2,
        "no_faith": False,
        "lock_faith": "starclan",
        "courage": 7,
        "compassion": 3,
        "intelligence": 9,
        "empathy": 4,
        "favourite": 1,
        "accessories": ["CRIMSONBELL"],
        "dead": True,
        "df": True,
        "dead_moons": 12,
    }
    d2 = CatDetails.from_save_cat(lg, GameVariant.LIFEGEN)
    assert d2.faith == -2 and d2.lock_faith == "starclan" and d2.courage == 7
    assert d2.skill_secondary_path == "MEDIATOR" and d2._skill_secondary_interest == "True"
    assert d2._skill_hidden == "ROGUE"
    assert d2._favourite_int is True
    # resurrect
    d2.clear_death()
    d2.faith = 5
    out2 = d2.apply_to_save_cat(dict(lg), GameVariant.LIFEGEN)
    assert out2["dead"] is False and out2["df"] is False and out2["dead_moons"] == 0
    assert out2["faith"] == 5 and out2["lock_faith"] == "starclan"
    assert out2["courage"] == 7 and out2["empathy"] == 4
    # skill_dict re-emitted in same shape incl interest flag + hidden
    assert out2["skill_dict"]["primary"] == "STAR,29,False"
    assert out2["skill_dict"]["secondary"] == "MEDIATOR,5,True"
    assert out2["skill_dict"]["hidden"] == "ROGUE"
    # favourite kept as int for LifeGen
    assert out2["favourite"] == 1 and isinstance(out2["favourite"], int)
    assert out2["accessories"] == ["CRIMSONBELL"], "appearance keys preserved"
    print("OK  LifeGen round-trip; faith/skills/stats preserved; resurrect clears death")

    # --- present-only: a ClanGen cat WITHOUT facets/skill_dict shouldn't gain them
    bare = {"ID": "003", "status": "warrior", "moons": 10}
    d3 = CatDetails.from_save_cat(bare, GameVariant.CLANGEN)
    d3.trait = "calm"
    out3 = d3.apply_to_save_cat(dict(bare), GameVariant.CLANGEN)
    assert "facets" not in out3 and "skill_dict" not in out3, "present-only keys not invented"
    assert out3["trait"] == "calm"
    print("OK  present-only facets/skill_dict not invented on bare save")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
