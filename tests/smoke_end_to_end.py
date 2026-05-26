"""End-to-end: load a fake clan into the UI, mutate the cat, click Apply,
verify the on-disk save was written correctly with a backup.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication, QMessageBox

from lifegen_editor.ui.main_window import MainWindow


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "ClanGen-saves"
        clan_dir = root / "TestClan"
        clan_dir.mkdir(parents=True)
        cats = [
            {"ID": "001", "name_prefix": "Bright", "name_suffix": "heart",
             "status": "warrior", "moons": 50, "pelt_name": "Tabby",
             "pelt_color": "BROWN", "eye_colour": "AMBER", "skin": "BLACK",
             "relationships": [1, 2, 3]},
            {"ID": "002", "name_prefix": "Tall", "name_suffix": "star",
             "status": "leader", "moons": 100, "pelt_name": "SingleColour",
             "pelt_color": "BLACK", "eye_colour": "YELLOW", "skin": "BLACK"},
        ]
        (clan_dir / "clan_cats.json").write_text(json.dumps(cats))

        w = MainWindow()
        w.show()

        # Browse to the tmp save root via the panel API
        w.save_panel.current_save_root = root
        w.save_panel._reload_clans()  # internal, but exercises the same code path
        app.processEvents()

        assert w.save_panel.current_clan is not None, "clan should load"
        assert len(w.save_panel.current_clan.cats) == 2, "two cats expected"

        # Select Brightheart (row 0); the main window will load her appearance into the editor.
        w.save_panel.cat_list.setCurrentRow(0)
        app.processEvents()

        # The editor should reflect Brightheart's current appearance.
        assert w.cat.pelt_name == "Tabby"
        assert w.cat.colour == "BROWN"
        assert w.cat.eye_colour == "AMBER"
        print(f"OK  loaded Brightheart: {w.cat.pelt_name} {w.cat.colour} {w.cat.eye_colour}")

        # Mutate the appearance via the editor widgets
        w.editor.pelt_combo.setCurrentText("Bengal")
        w.editor.colour_combo.setCurrentText("GINGER")
        w.editor.eye_combo.setCurrentText("BLUE")
        ix = w.editor.accessory_combo.findData("CRIMSONBELL")
        assert ix >= 0
        w.editor.accessory_combo.setCurrentIndex(ix)
        w.editor._add_accessory()
        ix = w.editor.accessory_combo.findData("MAPLE LEAF")
        assert ix >= 0
        w.editor.accessory_combo.setCurrentIndex(ix)
        w.editor._add_accessory()
        app.processEvents()
        assert w.cat.accessories == ["CRIMSONBELL", "MAPLE LEAF"], w.cat.accessories

        # Suppress the confirmation dialog
        QMessageBox.question = staticmethod(lambda *a, **kw: QMessageBox.StandardButton.Yes)  # type: ignore[assignment]

        # Trigger apply
        w._on_apply_clicked(w.save_panel.current_clan, 0)
        app.processEvents()

        on_disk = json.loads((clan_dir / "clan_cats.json").read_text())
        assert on_disk[0]["pelt_name"] == "Bengal", on_disk[0]
        assert on_disk[0]["pelt_color"] == "GINGER", on_disk[0]
        assert on_disk[0]["eye_colour"] == "BLUE", on_disk[0]
        # Original cat had no accessories field at all → legacy single schema →
        # writes first item only.
        assert on_disk[0]["accessory"] == "CRIMSONBELL", on_disk[0]
        # Identity preserved
        assert on_disk[0]["moons"] == 50
        assert on_disk[0]["relationships"] == [1, 2, 3]
        # Other cat untouched
        assert on_disk[1]["pelt_name"] == "SingleColour"

        # Backup exists
        backups = list(clan_dir.glob("clan_cats.json.bak-*"))
        assert backups, "backup file should be created"
        print(f"OK  applied: pelt now Bengal/GINGER/BLUE, backup at {backups[0].name}")
        print("OK  Brightheart's moons + relationships preserved")
        print("OK  Tallstar (other cat) untouched")

        w.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
