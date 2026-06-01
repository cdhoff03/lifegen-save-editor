"""Status handling across both formats: string status and the newer
CatStatus dict (group_history / standing_history)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.saves import rank_of, standing_of, with_rank, detect_variant, GameVariant
from lifegen_editor.saves.save_io import Clan, SaveCat
from lifegen_editor.io import CatDetails


def main() -> int:
    # rank_of / standing_of on both shapes
    assert rank_of("warrior") == "warrior"
    assert rank_of(None) == ""
    dict_status = {
        "group_history": [
            {"group": "1", "rank": "warrior", "moons_as": 0},
            {"group": "1", "rank": "leader", "moons_as": 0},
        ],
        "standing_history": [{"group": "1", "standing": ["member"], "near": True}],
    }
    assert rank_of(dict_status) == "leader", "current rank = last group_history entry"
    assert standing_of(dict_status) == "member"
    print("OK  rank_of/standing_of handle string and dict status")

    # with_rank preserves dict shape + history, only updates current rank
    updated = with_rank(dict_status, "elder")
    assert updated["group_history"][-1]["rank"] == "elder"
    assert updated["group_history"][0]["rank"] == "warrior", "history kept"
    assert "standing_history" in updated, "standing kept"
    assert dict_status["group_history"][-1]["rank"] == "leader", "original not mutated"
    assert with_rank("warrior", "elder") == "elder", "string form stays a string"
    print("OK  with_rank preserves dict history; string stays string")

    # a newer-ClanGen cat (dict status, no dead/outside/exiled keys) round-trips
    # Mirror the real newer-ClanGen field set (incl. experience + no_* + gender_align)
    # so the "no keys added" guarantee is exercised faithfully.
    cat = {
        "ID": "1", "name_prefix": "Fern", "name_suffix": "pelt",
        "gender": "female", "gender_align": "female",
        "status": dict_status, "moons": 80, "trait": "calm", "facets": "8,8,8,8",
        "skill_dict": {"primary": "SPEAKER,18,False", "secondary": None, "hidden": None},
        "experience": 0, "no_kits": False, "no_mates": False, "no_retire": False,
        "prevent_fading": False, "favourite": False,
    }
    clan = Clan(name="T", path=Path("/tmp/T"), cats=[SaveCat(0, cat)])
    assert detect_variant(clan) is GameVariant.CLANGEN
    assert clan.cats[0].display_name == "Fernpelt (leader)"

    v = GameVariant.CLANGEN
    d = CatDetails.from_save_cat(cat, v)
    assert d.status == "leader"
    d.status = "elder"
    before_keys = set(cat.keys())
    d.apply_to_save_cat(cat, v)
    assert set(cat.keys()) == before_keys, "no keys added/removed on a dict-status cat"
    assert isinstance(cat["status"], dict) and rank_of(cat["status"]) == "elder"
    assert cat["status"]["group_history"][0]["rank"] == "warrior"
    for k in ("dead", "outside", "exiled", "df", "faith", "courage"):
        assert k not in cat, f"must not invent {k} on a newer-ClanGen cat"
    print("OK  newer-ClanGen dict-status cat: rank edits in place, no spurious keys")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
