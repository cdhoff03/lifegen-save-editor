# Paste JSON & Cat-List Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Paste pixel-cat-maker JSON…" dialog and an `Import from clipboard` shortcut to the File menu, and a live-filtering search box above the cat list in the save panel.

**Architecture:** Two independent UI additions. Feature 1 (paste/clipboard) lives entirely in `lifegen_editor/ui/main_window.py` and reuses the existing `parse_pcm_json` / `parse_pcm_url` plumbing — no changes to `io/`. Feature 2 (search) adds a `QLineEdit` inside the existing `cats_group` in `lifegen_editor/ui/save_panel.py` and hides non-matching `QListWidgetItem`s via `setHidden`, so the existing `cat_picked` / `apply_requested` signal contracts stay intact.

**Tech Stack:** Python 3.9+, PySide6 (Qt6), existing `lifegen_editor.io.parse_pcm_json` and `parse_pcm_url`.

**Spec:** `docs/superpowers/specs/2026-05-26-paste-json-and-cat-search-design.md`

---

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `lifegen_editor/ui/main_window.py` | modify | +2 menu actions, +2 handlers, +1 module helper (`_detect_clipboard_format`). |
| `lifegen_editor/ui/save_panel.py` | modify | +1 `QLineEdit`, +1 `_on_search_changed`, +3 lines in `_on_clan_change`. |
| `tests/smoke_clipboard_import.py` | create | Unit-style test for `_detect_clipboard_format`. |
| `tests/smoke_cat_list_filter.py` | create | Integration test that loads a fake clan, types into the search box, and asserts which rows are hidden. |

---

## Task 1: TDD `_detect_clipboard_format` helper

**Files:**
- Create: `tests/smoke_clipboard_import.py`
- Modify: `lifegen_editor/ui/main_window.py`

- [ ] **Step 1: Write the failing test**

Write `tests/smoke_clipboard_import.py`:

```python
"""Tests for the clipboard-format sniffer used by Import from clipboard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.ui.main_window import _detect_clipboard_format


def test_detect_url() -> None:
    assert _detect_clipboard_format("https://cgen-tools.github.io/pixel-cat-maker/#abc") == "url"
    assert _detect_clipboard_format("http://example.com/x") == "url"
    # Whitespace around the input is tolerated.
    assert _detect_clipboard_format("  https://x  ") == "url"


def test_detect_json() -> None:
    assert _detect_clipboard_format('{"pelt_name": "Tabby"}') == "json"
    assert _detect_clipboard_format('  {"a":1}\n') == "json"


def test_detect_garbage() -> None:
    assert _detect_clipboard_format("") is None
    assert _detect_clipboard_format("just some text") is None
    assert _detect_clipboard_format("[1, 2, 3]") is None  # array, not an object
    assert _detect_clipboard_format("ftp://x") is None


def main() -> int:
    test_detect_url()
    test_detect_json()
    test_detect_garbage()
    print("smoke_clipboard_import OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python tests/smoke_clipboard_import.py`
Expected: `ImportError: cannot import name '_detect_clipboard_format' from 'lifegen_editor.ui.main_window'`.

- [ ] **Step 3: Add the helper to main_window.py**

Open `lifegen_editor/ui/main_window.py`. Find the module-level `def run() -> int:` near the bottom of the file. Immediately ABOVE it, insert:

```python
def _detect_clipboard_format(text: str) -> str | None:
    """Return ``"url"`` / ``"json"`` / ``None`` based on a quick sniff of ``text``.

    Used by File → Import from clipboard so it can route to the right parser
    without a second dialog.
    """
    s = text.strip()
    if s.startswith(("http://", "https://")):
        return "url"
    if s.startswith("{"):
        return "json"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python tests/smoke_clipboard_import.py`
Expected: `smoke_clipboard_import OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_clipboard_import.py lifegen_editor/ui/main_window.py
git commit -m "feat(ui): clipboard format sniffer for paste / import shortcuts"
```

---

## Task 2: Add `Paste pixel-cat-maker JSON…` menu item

**Files:**
- Modify: `lifegen_editor/ui/main_window.py`

- [ ] **Step 1: Add the handler method**

Open `lifegen_editor/ui/main_window.py`. Inside the `MainWindow` class, find the existing `_import_url` method (around line 139). Immediately AFTER its closing block (right before `_copy_json`), insert:

```python
    def _paste_json(self) -> None:
        clip = QGuiApplication.clipboard().text() if QGuiApplication.clipboard() else ""
        prefill = clip if clip.strip().startswith("{") else ""
        text, ok = QInputDialog.getMultiLineText(
            self, "Paste pixel-cat-maker JSON",
            "Paste the JSON exported from pixel-cat-maker:",
            prefill,
        )
        if not ok or not text.strip():
            return
        try:
            self.cat = parse_pcm_json(text)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self._sync_after_replace()
        self.statusBar().showMessage("Imported pasted JSON")
```

- [ ] **Step 2: Wire the menu item**

In the same file, find `_build_menu`. Locate the existing block that ends with:

```python
        act_import_url = QAction("Import from share &URL…", self)
        act_import_url.triggered.connect(self._import_url)
        file_menu.addAction(act_import_url)

        file_menu.addSeparator()
```

Insert a new action BEFORE the separator:

```python
        act_paste_json = QAction("&Paste pixel-cat-maker JSON…", self)
        act_paste_json.triggered.connect(self._paste_json)
        file_menu.addAction(act_paste_json)

```

So the result is:

```python
        act_import_url = QAction("Import from share &URL…", self)
        act_import_url.triggered.connect(self._import_url)
        file_menu.addAction(act_import_url)

        act_paste_json = QAction("&Paste pixel-cat-maker JSON…", self)
        act_paste_json.triggered.connect(self._paste_json)
        file_menu.addAction(act_paste_json)

        file_menu.addSeparator()
```

- [ ] **Step 3: Smoke-test the file still imports and selftest passes**

Run: `LIFEGEN_EDITOR_SELFTEST=1 .venv/bin/python -m lifegen_editor`
Expected: `LIFEGEN_EDITOR_SELFTEST OK cat=...`. (Selftest doesn't open the menu so it can't validate the dialog itself; this just confirms no syntax/import errors.)

- [ ] **Step 4: Manual smoke (optional)**

Run: `.venv/bin/python -m lifegen_editor`
Open File → Paste pixel-cat-maker JSON…. Paste any valid pixel-cat-maker JSON (e.g., what `File → Copy current as JSON` puts on the clipboard). Confirm the preview updates.

- [ ] **Step 5: Commit**

```bash
git add lifegen_editor/ui/main_window.py
git commit -m "feat(ui): File → Paste pixel-cat-maker JSON…"
```

---

## Task 3: Add `Import from clipboard` menu item with Ctrl+Shift+V

**Files:**
- Modify: `lifegen_editor/ui/main_window.py`

- [ ] **Step 1: Add the handler method**

In `lifegen_editor/ui/main_window.py`, immediately AFTER the `_paste_json` method you added in Task 2, insert:

```python
    def _import_clipboard(self) -> None:
        text = QGuiApplication.clipboard().text() if QGuiApplication.clipboard() else ""
        kind = _detect_clipboard_format(text)
        if kind is None:
            QMessageBox.information(
                self, "Nothing to import",
                "Clipboard didn't look like a pixel-cat-maker URL or JSON.",
            )
            return
        try:
            self.cat = parse_pcm_url(text) if kind == "url" else parse_pcm_json(text)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self._sync_after_replace()
        self.statusBar().showMessage(f"Imported from clipboard ({kind})")
```

- [ ] **Step 2: Wire the menu item with shortcut**

In `_build_menu`, immediately AFTER the `act_paste_json` block from Task 2 (still before the separator), insert:

```python
        act_import_clip = QAction("Import from &clipboard", self)
        act_import_clip.setShortcut("Ctrl+Shift+V")
        act_import_clip.triggered.connect(self._import_clipboard)
        file_menu.addAction(act_import_clip)

```

- [ ] **Step 3: Smoke-test imports + selftest**

Run: `LIFEGEN_EDITOR_SELFTEST=1 .venv/bin/python -m lifegen_editor`
Expected: `LIFEGEN_EDITOR_SELFTEST OK cat=...`.

- [ ] **Step 4: Manual smoke (optional)**

1. Run: `.venv/bin/python -m lifegen_editor`
2. With no relevant clipboard contents, press Ctrl+Shift+V → expect "Nothing to import" dialog.
3. Copy a valid pixel-cat-maker URL into the clipboard → Ctrl+Shift+V → preview updates.
4. Copy a valid pixel-cat-maker JSON object → Ctrl+Shift+V → preview updates.

- [ ] **Step 5: Commit**

```bash
git add lifegen_editor/ui/main_window.py
git commit -m "feat(ui): File → Import from clipboard (Ctrl+Shift+V)"
```

---

## Task 4: Add the search QLineEdit + filter to `SavePanel`

**Files:**
- Modify: `lifegen_editor/ui/save_panel.py`

- [ ] **Step 1: Add `QLineEdit` to the imports**

In `lifegen_editor/ui/save_panel.py`, change the existing block:

```python
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
```

to add `QLineEdit` (in alphabetical position):

```python
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)
```

- [ ] **Step 2: Add the search box above the cat list**

Still in `save_panel.py`, find this block in `__init__` (around line 72):

```python
        # Cats
        cats_group = QGroupBox("Cats")
        cl2 = QVBoxLayout(cats_group)
        self.cat_list = QListWidget()
        self.cat_list.currentRowChanged.connect(self._on_cat_change)
        cl2.addWidget(self.cat_list, 1)
        outer.addWidget(cats_group, 1)
```

Replace it with:

```python
        # Cats
        cats_group = QGroupBox("Cats")
        cl2 = QVBoxLayout(cats_group)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search…")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_changed)
        cl2.addWidget(self.search_edit)
        self.cat_list = QListWidget()
        self.cat_list.currentRowChanged.connect(self._on_cat_change)
        cl2.addWidget(self.cat_list, 1)
        outer.addWidget(cats_group, 1)
```

- [ ] **Step 3: Add the `_on_search_changed` method**

In `save_panel.py`, in the `# ---- events ----` section (after `_on_cat_change` and before `_on_apply`), add:

```python
    def _on_search_changed(self, text: str) -> None:
        needle = text.strip().lower()
        for i in range(self.cat_list.count()):
            item = self.cat_list.item(i)
            item.setHidden(bool(needle) and needle not in item.text().lower())
```

- [ ] **Step 4: Clear the search box on clan change**

Find `_on_clan_change` (around line 136). Replace its existing body:

```python
    def _on_clan_change(self, idx: int) -> None:
        path_str = self.clan_combo.itemData(idx)
        if not path_str:
            return
        try:
            self.current_clan = load_clan(Path(path_str))
        except Exception as e:
            self.status_label.setText(f"Failed to load clan: {e}")
            self.current_clan = None
            self.cat_list.clear()
            self.apply_btn.setEnabled(False)
            return
        self.cat_list.clear()
        for cat in self.current_clan.cats:
            item = QListWidgetItem(cat.display_name)
            self.cat_list.addItem(item)
        self.status_label.setText(f"Loaded {self.current_clan.name} ({len(self.current_clan.cats)} cats).")
        if self.current_clan.cats:
            self.cat_list.setCurrentRow(0)
```

With (only difference: the 3-line `search_edit` reset right after the `try/except` block, before populating the list):

```python
    def _on_clan_change(self, idx: int) -> None:
        path_str = self.clan_combo.itemData(idx)
        if not path_str:
            return
        try:
            self.current_clan = load_clan(Path(path_str))
        except Exception as e:
            self.status_label.setText(f"Failed to load clan: {e}")
            self.current_clan = None
            self.cat_list.clear()
            self.apply_btn.setEnabled(False)
            return
        self.search_edit.blockSignals(True)
        self.search_edit.clear()
        self.search_edit.blockSignals(False)
        self.cat_list.clear()
        for cat in self.current_clan.cats:
            item = QListWidgetItem(cat.display_name)
            self.cat_list.addItem(item)
        self.status_label.setText(f"Loaded {self.current_clan.name} ({len(self.current_clan.cats)} cats).")
        if self.current_clan.cats:
            self.cat_list.setCurrentRow(0)
```

- [ ] **Step 5: Smoke-test the existing end-to-end test still passes**

Run: `.venv/bin/python tests/smoke_end_to_end.py`
Expected: prints OKs and exits 0. This is the existing fake-clan test — it exercises `_on_clan_change` and selects cats, so it confirms the new search-clear step didn't break anything.

- [ ] **Step 6: Commit**

```bash
git add lifegen_editor/ui/save_panel.py
git commit -m "feat(ui): live search box above the cat list"
```

---

## Task 5: Smoke test for cat-list search behavior

**Files:**
- Create: `tests/smoke_cat_list_filter.py`

- [ ] **Step 1: Write the test**

Write `tests/smoke_cat_list_filter.py`:

```python
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
```

- [ ] **Step 2: Run the test**

Run: `.venv/bin/python tests/smoke_cat_list_filter.py`
Expected:
```
OK  empty filter: ['Brightheart (warrior)', 'Tallstar (leader)', 'Mistyfoot (warrior)']
OK  filter 'tall' -> ['Tallstar (leader)']
OK  filter 'WARRIOR' -> ['Brightheart (warrior)', 'Mistyfoot (warrior)']
OK  filter 'zzzz' -> []
OK  cleared filter -> 3 visible
smoke_cat_list_filter OK
```

- [ ] **Step 3: Commit**

```bash
git add tests/smoke_cat_list_filter.py
git commit -m "test: smoke test for live cat-list search"
```

---

## Task 6: Final integration smoke

**Files:** (none modified)

- [ ] **Step 1: Run every smoke test**

```bash
.venv/bin/python tests/smoke_clipboard_import.py
.venv/bin/python tests/smoke_cat_list_filter.py
.venv/bin/python tests/smoke_io.py
.venv/bin/python tests/smoke_saves.py
.venv/bin/python tests/smoke_end_to_end.py
LIFEGEN_EDITOR_SELFTEST=1 .venv/bin/python -m lifegen_editor
python3 tests/smoke_updater_client.py
python3 tests/smoke_updater_swap.py
```

Expected: every command exits 0 with its respective "… OK" line.

- [ ] **Step 2: Quick manual UX check (no commit needed)**

```bash
.venv/bin/python -m lifegen_editor
```

Inspect the File menu — the order should be:

1. Import pixel-cat-maker JSON…
2. Import from share URL…
3. Paste pixel-cat-maker JSON…
4. Import from clipboard  (Ctrl+Shift+V)
5. ───────────
6. Copy current as JSON
7. … (rest unchanged)

Inspect the right panel — under "Cats", confirm the search box with ✕ clear button appears above the list.

- [ ] **Step 3: If a small cleanup commit is needed, do it now**

```bash
git status
# If clean, no commit needed.
```

---

## Self-review notes

**Spec coverage:**

| Spec requirement | Implemented by |
|---|---|
| New `Paste pixel-cat-maker JSON…` menu item with multi-line dialog | Task 2 |
| New `Import from clipboard` shortcut, Ctrl+Shift+V, auto-detects URL vs JSON | Tasks 1, 3 |
| Failure modes (empty paste / unparseable / unrecognized clipboard) | Tasks 2, 3 (existing `QMessageBox.critical` reused; explicit information dialog for unrecognized) |
| `_detect_clipboard_format` helper | Task 1 |
| `QLineEdit` above cat list with placeholder + clear button | Task 4 |
| `_on_search_changed` hides non-matching items via `setHidden` | Task 4 |
| Search cleared on clan change | Task 4 |
| Unit test for clipboard sniffer | Task 1 |
| Integration test for cat list filter | Task 5 |

**Placeholder scan:** No TBDs. All code is complete; commands have exact expected outputs.

**Type consistency:** `_detect_clipboard_format` returns `"url" | "json" | None` in Task 1; Task 3 reads it as `kind` and branches on those exact strings. `search_edit` is `QLineEdit`, `cat_list` is `QListWidget` — both used consistently.
