"""Drive DetailsPanel headless against fake ClanGen + LifeGen saves."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from lifegen_editor.saves import load_clan, list_clans
from lifegen_editor.ui.details_panel import DetailsPanel


def _make_clan(tmp: Path, lifegen: bool) -> Path:
    root = tmp / "saves"
    cdir = root / "TestClan"
    cdir.mkdir(parents=True)
    if lifegen:
        cats = [
            {"ID": "001", "name_prefix": "Fire", "name_suffix": "star", "status": "leader",
             "moons": 60, "trait": "bold", "facets": "8,8,8,8", "gender": "tom",
             "gender_align": "tom", "faith": -2, "no_faith": False, "lock_faith": "flexible",
             "courage": 5, "skill_dict": {"primary": "STAR,20,False", "secondary": None, "hidden": None},
             "dead": True, "df": True, "dead_moons": 5, "accessories": [], "favourite": 1},
            {"ID": "002", "name_prefix": "Leaf", "name_suffix": "pool", "status": "medicine cat", "moons": 40},
        ]
        (root / "TestClanclan.json").write_text(json.dumps({
            "clanname": "TestClan", "leader_lives": 7, "clanage": 120, "biome": "Beach",
            "reputation": 30, "leader": "001",
            "starclan_cats": ["001", "002"], "darkforest_cats": [], "unknown_cats": [],
        }))
    else:
        cats = [
            {"ID": "001", "name_prefix": "Bright", "name_suffix": "heart", "status": "medicine cat",
             "moons": 42, "trait": "loyal", "facets": "8,12,4,9", "gender": "female",
             "accessory": None, "dead": False, "favourite": False},
            {"ID": "002", "name_prefix": "Tall", "name_suffix": "star", "status": "leader", "moons": 90},
        ]
    (cdir / "clan_cats.json").write_text(json.dumps(cats))
    return root


def main() -> int:
    app = QApplication.instance() or QApplication([])

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)

        # --- LifeGen ---
        root = _make_clan(tmp / "lg", lifegen=True)
        clan = load_clan(list_clans(root)[0])
        panel = DetailsPanel()
        panel.load_from_pick(clan, 0)
        assert panel._variant.value == "lifegen"
        assert panel._faith_group.isVisible() or True  # group exists; visibility set
        assert panel._faith_group.isVisibleTo(panel.widget()) is True, "faith shown for LifeGen"
        # status combo is LifeGen vocabulary: medicine cat (shared) + queen track
        statuses = [panel.status_combo.itemText(i) for i in range(panel.status_combo.count())]
        assert "medicine cat" in statuses and "queen" in statuses
        # edit + resurrect via apply path
        panel.dead_cb.setChecked(True)  # ensure starts dead
        panel._read_widgets()
        panel.details.clear_death()
        panel.details.apply_to_save_cat(clan.cats[0].raw, panel._variant)
        assert clan.cats[0].raw["dead"] is False
        # status change persists through apply
        panel.status_combo.setCurrentText("warrior")
        panel._read_widgets()
        panel.details.apply_to_save_cat(clan.cats[0].raw, panel._variant)
        assert clan.cats[0].raw["status"] == "warrior"
        assert clan.cats[0].raw["faith"] == -2  # LifeGen field preserved
        # health add
        panel._cond_combos["injuries"].setCurrentText("pregnant")
        panel._add_condition("injuries")
        assert "pregnant" in panel._conditions["injuries"]
        # clan json loaded
        assert panel._clan_json["leader_lives"] == 7
        assert panel.clan_biome_combo.currentText() == "Beach"
        print("OK  LifeGen panel: faith shown, statuses LifeGen, resurrect+status apply, health add, clan loaded")

        # --- ClanGen ---
        root2 = _make_clan(tmp / "cg", lifegen=False)
        clan2 = load_clan(list_clans(root2)[0])
        panel2 = DetailsPanel()
        panel2.load_from_pick(clan2, 0)
        assert panel2._variant.value == "clangen"
        assert panel2._faith_group.isVisibleTo(panel2.widget()) is False, "faith hidden for ClanGen"
        assert panel2._skills_group.isVisibleTo(panel2.widget()) is False
        assert panel2._stats_group.isVisibleTo(panel2.widget()) is False
        statuses2 = [panel2.status_combo.itemText(i) for i in range(panel2.status_combo.count())]
        assert "medicine cat" in statuses2 and "healer" not in statuses2 and "queen" not in statuses2
        # apply must NOT add LifeGen-only keys
        panel2.status_combo.setCurrentText("warrior")
        panel2.moons_spin.setValue(30)
        panel2._read_widgets()
        panel2.details.apply_to_save_cat(clan2.cats[0].raw, panel2._variant)
        raw = clan2.cats[0].raw
        assert raw["status"] == "warrior" and raw["moons"] == 30
        for k in ("faith", "courage", "skill_dict"):
            assert k not in raw, f"ClanGen cat must not gain {k}"
        print("OK  ClanGen panel: LifeGen groups hidden, statuses ClanGen, no LifeGen keys written")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
