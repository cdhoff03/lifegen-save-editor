"""Dict-status (ClanGen v0.13 / LifeGen v0.7.7+) life & death editing.

Covers the pure catstatus transforms and the CatDetails read/apply round-trip:
kill/revive, StarClan<->Dark Forest, dead-moons, exile on/off, outside on/off,
nested ["shunned", moon] tolerance, and that only CatRank-valid ranks are ever
written (invalid ranks crash the games' loaders).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.saves import catstatus as cs
from lifegen_editor.saves.variant import GameVariant
from lifegen_editor.io.cat_details import CatDetails

VALID_RANKS = {
    "newborn", "kitten", "apprentice", "medicine cat apprentice",
    "mediator apprentice", "queen's apprentice", "warrior", "queen",
    "medicine cat", "mediator", "deputy", "leader", "elder",
    "loner", "rogue", "kittypet",
}


def alive_status() -> dict:
    return {
        "group_history": [{"group": "1", "rank": "warrior", "moons_as": 5}],
        "standing_history": [{"group": "1", "standing": ["member"], "near": True}],
    }


def check_ranks(status: dict) -> None:
    for entry in status["group_history"]:
        assert entry["rank"] in VALID_RANKS, f"invalid rank {entry['rank']!r}"


def main() -> int:
    # --- pure transforms ---------------------------------------------------
    alive = alive_status()
    assert not cs.is_dead(alive) and not cs.is_outside(alive) and not cs.is_exiled(alive)

    dead = cs.kill(alive)
    assert cs.is_dead(dead) and not cs.is_df(dead) and cs.current_group(dead) == "2"
    assert cs.rank_of(dead) == "warrior" and cs.dead_moons_of(dead) == 0
    check_ranks(dead)

    dfd = cs.kill(dead, df=True)
    assert cs.is_df(dfd) and cs.dead_moons_of(dfd) == 0
    back = cs.revive(dfd)
    assert not cs.is_dead(back) and cs.current_group(back) == "1"
    assert cs.rank_of(back) == "warrior"
    check_ranks(back)

    assert cs.dead_moons_of(cs.with_dead_moons(dead, 12)) == 12

    ex = cs.set_exiled(alive, True)
    assert cs.is_exiled(ex) and cs.is_outside(ex) and cs.rank_of(ex) == "loner"
    check_ranks(ex)
    unex = cs.set_exiled(ex, False)
    assert not cs.is_exiled(unex) and not cs.is_outside(unex)

    out_lg = cs.set_outside(alive, True, lifegen=True)
    assert cs.is_outside(out_lg) and cs.current_group(out_lg) == "6"
    out_cg = cs.set_outside(alive, True, lifegen=False)
    assert cs.is_outside(out_cg) and cs.current_group(out_cg) is None
    check_ranks(out_cg)

    shunned = alive_status()
    shunned["standing_history"][0]["standing"].append(["shunned", 12])
    assert cs.standing_of(shunned) == "shunned" and not cs.is_exiled(shunned)

    # originals never mutated (all writers deep-copy)
    assert len(alive["group_history"]) == 1

    # --- CatDetails round-trip on a new-schema cat -------------------------
    cat = {
        "ID": "1", "name_prefix": "Bright", "name_suffix": "heart",
        "gender": "female", "gender_align": "female", "moons": 40,
        "status": alive_status(), "trait": "calm",
        "skill_dict": {"primary": "HUNTER,9,False", "secondary": None, "hidden": None},
        "facets": "8,8,8,8", "experience": 100, "favourite": 0,
        "no_kits": False, "no_mates": False, "no_retire": False,
        "faith": 3, "inventory": [],
    }
    d = CatDetails.from_save_cat(cat, GameVariant.LIFEGEN)
    assert not d.dead and not d.outside and not d.exiled and d.dead_moons == 0

    d.dead, d.df, d.dead_moons = True, True, 7
    out = dict(cat)
    d.apply_to_save_cat(out, GameVariant.LIFEGEN)
    st = out["status"]
    assert cs.is_dead(st) and cs.is_df(st) and cs.dead_moons_of(st) == 7
    assert "dead" not in out and "df" not in out and "dead_moons" not in out
    check_ranks(st)

    # resurrect: re-read the killed cat, clear death, apply
    d2 = CatDetails.from_save_cat(out, GameVariant.LIFEGEN)
    assert d2.dead and d2.df and d2.dead_moons == 7
    d2.clear_death()
    out2 = dict(out)
    d2.apply_to_save_cat(out2, GameVariant.LIFEGEN)
    assert not cs.is_dead(out2["status"]) and cs.current_group(out2["status"]) == "1"
    check_ranks(out2["status"])

    # legacy string-status path unchanged
    legacy = {"ID": "2", "status": "warrior", "moons": 10, "dead": False}
    dl = CatDetails.from_save_cat(legacy, GameVariant.CLANGEN)
    dl.dead = True
    outl = dict(legacy)
    dl.apply_to_save_cat(outl, GameVariant.CLANGEN)
    assert outl["status"] == "warrior" and outl["dead"] is True

    print("OK  status-dict death/exile/outside transforms + CatDetails round-trip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
