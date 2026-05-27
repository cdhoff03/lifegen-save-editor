"""Integration test: live filter on the SavePanel cat list."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication

from lifegen_editor.ui.save_panel import SavePanel


def _make_clan(root: Path) -> None:
    clan_dir = root / "FilterClan"
    clan_dir.mkdir(parents=True)
    cats = [
        {"ID": "001", "name_prefix": "Bright", "name_suffix": "heart",
         "status": "warrior", "moons": 50, "pelt_name": "Tabby",
         "pelt_color": "BROWN", "eye_colour": "AMBER", "skin": "BLACK"},
        {"ID": "002", "name_prefix": "Tall",   "name_suffix": "star",
         "status": "leader",  "moons": 100, "pelt_name": "SingleColour",
         "pelt_color": "BLACK", "eye_colour": "YELLOW", "skin": "BLACK"},
        {"ID": "003", "name_prefix": "Misty",  "name_suffix": "foot",
         "status": "warrior", "moons": 30,  "pelt_name": "Tabby",
         "pelt_color": "GREY",  "eye_colour": "GREEN", "skin": "BLACK"},
    ]
    (clan_dir / "clan_cats.json").write_text(json.dumps(cats))


def _visible_rows(panel: SavePanel) -> list[str]:
    out: list[str] = []
    for i in range(panel.cat_list.count()):
        item = panel.cat_list.item(i)
        if not item.isHidden():
            out.append(item.text())
    return out


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "saves"
        _make_clan(root)

        panel = SavePanel()
        panel.current_save_root = root
        panel._reload_clans()
        app.processEvents()

        assert panel.current_clan is not None, "expected clan to load"
        assert panel.cat_list.count() == 3, f"expected 3 rows, got {panel.cat_list.count()}"

        # Empty filter — everything visible.
        assert len(_visible_rows(panel)) == 3
        print(f"OK  empty filter: {_visible_rows(panel)}")

        # "tall" matches Tallstar only.
        panel.search_edit.setText("tall")
        app.processEvents()
        visible = _visible_rows(panel)
        assert len(visible) == 1 and "Tallstar" in visible[0], visible
        print(f"OK  filter 'tall' -> {visible}")

        # Case-insensitive: "WARRIOR" matches Brightheart + Mistyfoot.
        panel.search_edit.setText("WARRIOR")
        app.processEvents()
        visible = _visible_rows(panel)
        assert len(visible) == 2, visible
        print(f"OK  filter 'WARRIOR' -> {visible}")

        # No matches.
        panel.search_edit.setText("zzzz")
        app.processEvents()
        assert _visible_rows(panel) == []
        print("OK  filter 'zzzz' -> []")

        # Clearing restores all.
        panel.search_edit.setText("")
        app.processEvents()
        assert len(_visible_rows(panel)) == 3
        print("OK  cleared filter -> 3 visible")

    print("smoke_cat_list_filter OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
