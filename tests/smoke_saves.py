"""Verify save locator + load/write/backup round-trip on a fake clan."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.io import CatData
from lifegen_editor.saves import list_clans, load_clan, write_clan_with_backup
from lifegen_editor.saves.locator import candidate_roots


def main() -> int:
    for r in candidate_roots():
        print(f"  candidate save root: {r.name:7s} {r.save_root} (exists={r.exists})")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "saves"
        clan = root / "ThunderClan"
        clan.mkdir(parents=True)
        original = [
            {"ID": "001", "name_prefix": "Bright", "name_suffix": "heart",
             "status": "warrior", "moons": 50,
             "pelt_name": "Tabby", "pelt_color": "BROWN", "eye_colour": "AMBER",
             "skin": "BLACK", "relationships": [1, 2, 3]},
            {"ID": "002", "name_prefix": "Tall", "name_suffix": "star",
             "status": "leader", "moons": 100,
             "pelt_name": "SingleColour", "pelt_color": "BLACK", "eye_colour": "YELLOW",
             "skin": "BLACK"},
        ]
        (clan / "clan_cats.json").write_text(json.dumps(original))

        clans = list_clans(root)
        assert len(clans) == 1 and clans[0].name == "ThunderClan"

        loaded = load_clan(clans[0])
        assert len(loaded.cats) == 2
        assert loaded.cats[0].display_name == "Brightheart (warrior)"
        print(f"OK  loaded clan {loaded.name!r} with {len(loaded.cats)} cats")
        for c in loaded.cats:
            print(f"    [{c.index}] {c.display_name}  id={c.cat_id}")

        # Apply new appearance to Brightheart
        new = CatData(pelt_name="Bengal", colour="GINGER", eye_colour="BLUE",
                      eye_colour2="GREEN", accessories=["CRIMSONBELL"])
        new.apply_to_save_cat(loaded.cats[0].raw)

        backup = write_clan_with_backup(loaded)
        assert backup.exists()
        on_disk = json.loads((clan / "clan_cats.json").read_text())
        assert on_disk[0]["pelt_name"] == "Bengal"
        assert on_disk[0]["pelt_color"] == "GINGER"
        assert on_disk[0]["eye_colour"] == "BLUE"
        assert on_disk[0]["eye_colour2"] == "GREEN"
        # Legacy single schema (fake save has no `accessories` key and no list).
        assert on_disk[0]["accessory"] == "CRIMSONBELL"
        # non-appearance preserved
        assert on_disk[0]["moons"] == 50
        assert on_disk[0]["relationships"] == [1, 2, 3]
        # other cat untouched
        assert on_disk[1]["pelt_name"] == "SingleColour"
        print(f"OK  wrote save, backup at {backup.name}")
        print("OK  Brightheart's identity + relationships preserved; appearance overwritten")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
