"""Verify sidecar file I/O: conditions, relationships, clan.json, resurrect."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.saves import (
    load_clan,
    list_clans,
    load_conditions,
    write_conditions,
    load_relationships,
    write_relationships,
    load_clan_json,
    write_clan_json,
    clan_json_path,
    remove_from_afterlife,
)


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "saves"
        clandir = root / "ThunderClan"
        clandir.mkdir(parents=True)
        (clandir / "clan_cats.json").write_text(json.dumps([
            {"ID": "001", "status": "warrior", "dead": True},
            {"ID": "002", "status": "leader"},
        ]))
        clan = load_clan(list_clans(root)[0])

        # conditions: missing -> empty skeleton; write -> round-trip; backup on rewrite
        assert load_conditions(clan, "001") == {"illnesses": {}, "injuries": {}, "permanent conditions": {}}
        data = {"illnesses": {"greencough": {"severity": "major", "mortality": 18, "moon_start": 3}},
                "injuries": {}, "permanent conditions": {}}
        b1 = write_conditions(clan, "001", data)
        assert b1 is None, "first write has no backup"
        assert load_conditions(clan, "001")["illnesses"]["greencough"]["mortality"] == 18
        b2 = write_conditions(clan, "001", data)
        assert b2 is not None and b2.exists(), "second write creates backup"
        print("OK  conditions round-trip + backup-on-rewrite")

        # relationships: missing -> []; write array -> round-trip
        assert load_relationships(clan, "001") == []
        recs = [{"cat_from_id": "001", "cat_to_id": "002", "mates": False, "family": False,
                 "romantic_love": 0, "platonic_like": 40, "dislike": 0, "admiration": 20,
                 "comfortable": 35, "jealousy": 0, "trust": 50, "log": []}]
        write_relationships(clan, "001", recs)
        assert load_relationships(clan, "001")[0]["platonic_like"] == 40
        print("OK  relationships round-trip")

        # clan.json sits BESIDE the folder, named "<Name>clan.json"
        cjp = clan_json_path(clan)
        assert cjp == root / "ThunderClanclan.json", cjp
        assert cjp.parent == root and "ThunderClan" not in [p.name for p in [cjp.parent]]
        write_clan_json(clan, {"clanname": "ThunderClan", "leader_lives": 9,
                               "starclan_cats": ["001", "002"], "darkforest_cats": [],
                               "unknown_cats": "003,001"})
        assert cjp.is_file(), "clan.json written beside folder"
        cj = load_clan_json(clan)
        assert cj["leader_lives"] == 9
        print(f"OK  clan.json written at sibling path {cjp.name}")

        # resurrect: remove id from all rosters (list AND comma-string shapes)
        pruned = remove_from_afterlife(cj, "001")
        assert pruned["starclan_cats"] == ["002"], pruned["starclan_cats"]
        assert pruned["unknown_cats"] == "003", pruned["unknown_cats"]
        assert cj["starclan_cats"] == ["001", "002"], "original not mutated"
        print("OK  remove_from_afterlife prunes list + comma-string rosters")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
