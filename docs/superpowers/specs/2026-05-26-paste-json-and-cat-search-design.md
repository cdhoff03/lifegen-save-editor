# Paste JSON & Cat-List Search — Design

**Status:** Design approved 2026-05-26. Awaiting implementation plan.

## Goals

1. Let the user import a pixel-cat-maker cat by pasting JSON, in addition to picking a file. Add a one-click "import whatever's on the clipboard" shortcut that auto-detects URL vs JSON.
2. Let the user filter the cat list by typing into a search box above the list.

## Non-goals (explicit YAGNI)

- No drag-and-drop import.
- No fuzzy / regex search. Case-insensitive substring is sufficient.
- No search across clans — search scopes to the currently loaded clan only.
- No "no matches" hint UI; the status label already tells the user how many cats the clan has.
- No persistent search state across clan switches.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Paste UX | Both: explicit dialog + auto-import shortcut | User wants flexibility. |
| Search scope | Name only — case-insensitive substring against the displayed list line | Simplest; role already appears in `display_name`. |
| Filter mechanism | `QListWidgetItem.setHidden()` | Preserves row indices, so existing `cat_picked` / `apply_requested` signal contracts stay valid. |

## Feature 1 — Paste JSON & Import from Clipboard

**File:** `lifegen_editor/ui/main_window.py` only. No changes to `lifegen_editor/io/*`.

### New File-menu items

Inserted after the two existing import actions, before the separator:

| Label | Shortcut | Handler |
|---|---|---|
| `&Paste pixel-cat-maker JSON…` | — | `_paste_json` |
| `Import from &clipboard` | `Ctrl+Shift+V` | `_import_clipboard` |

### `_paste_json`

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

### `_import_clipboard`

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

### `_detect_clipboard_format`

Module-level helper, at the bottom of `main_window.py` near `run()`:

```python
def _detect_clipboard_format(text: str) -> str | None:
    s = text.strip()
    if s.startswith(("http://", "https://")):
        return "url"
    if s.startswith("{"):
        return "json"
    return None
```

### Failure modes

- **Empty clipboard / empty paste:** `_paste_json` early-returns silently if the dialog is cancelled or the text is whitespace.
- **Unparseable input:** caught by the same `QMessageBox.critical(self, "Import failed", str(e))` path the existing two import actions use.
- **Unrecognized clipboard format:** `_import_clipboard` shows an information dialog (not critical — nothing was attempted).

## Feature 2 — Cat-List Search

**File:** `lifegen_editor/ui/save_panel.py` only.

### UI change

Inside the existing `cats_group` `QVBoxLayout` (`cl2`), insert a `QLineEdit` above the `QListWidget`:

```python
self.search_edit = QLineEdit()
self.search_edit.setPlaceholderText("Search…")
self.search_edit.setClearButtonEnabled(True)
self.search_edit.textChanged.connect(self._on_search_changed)
cl2.addWidget(self.search_edit)
cl2.addWidget(self.cat_list, 1)   # existing line
```

`setClearButtonEnabled(True)` gives an inline ✕ in the field at no UI cost.

### Filter

```python
def _on_search_changed(self, text: str) -> None:
    needle = text.strip().lower()
    for i in range(self.cat_list.count()):
        item = self.cat_list.item(i)
        item.setHidden(bool(needle) and needle not in item.text().lower())
```

### Clear on clan change

In the existing `_on_clan_change`, before populating the list:

```python
self.search_edit.blockSignals(True)
self.search_edit.clear()
self.search_edit.blockSignals(False)
```

(blockSignals prevents an extra `_on_search_changed("")` from firing on a fresh list.)

### Why `setHidden` (not rebuild)

- The QListWidget still contains every cat, so `cat_list.currentRow()` keeps returning an index that maps directly to `current_clan.cats[row]`.
- `cat_picked` and `apply_requested` signals fire with that same row, so `main_window.py` needs no changes.
- Rebuilding the list with filtered items would require a parallel `visible_row → cat_index` map and rewriting the existing event handlers. Not justified.

### Edge cases

| Case | Behavior |
|---|---|
| Selected cat gets filtered out | Selection stays on the same hidden row; the Apply button still shows the previously-selected name. Standard Qt list-filter behavior. |
| All filtered out | Empty list; status label still says "Loaded ThunderClan (N cats)." so the user knows it's a filter result, not an empty clan. |
| Clan switched while search active | Search box cleared automatically (see "Clear on clan change"). |

## Testing approach

New unit tests in the existing smoke-script style:

- `tests/smoke_clipboard_import.py`
  - `_detect_clipboard_format("https://cgen-tools.github.io/...")` → `"url"`
  - `_detect_clipboard_format('{"pelt_name": "Tabby"}')` → `"json"`
  - `_detect_clipboard_format("garbage")` → `None`
  - `_detect_clipboard_format("  https://x ")` → `"url"` (strips whitespace)
- `tests/smoke_cat_list_filter.py`
  - Build a `SavePanel`, load a fake clan with three cats (Brightheart, Tallstar, Mistyfoot).
  - Set search to "tall" → only Tallstar visible.
  - Clear search → all three visible.
  - Set search to "Z" → none visible, list count still 3.
  - (Uses `QT_QPA_PLATFORM=offscreen` like the existing `tests/smoke_end_to_end.py`.)

## Files touched

| Path | Change |
|---|---|
| `lifegen_editor/ui/main_window.py` | +2 menu actions, +2 handlers, +1 module helper |
| `lifegen_editor/ui/save_panel.py` | +1 QLineEdit, +1 method, +3 lines in `_on_clan_change` |
| `tests/smoke_clipboard_import.py` | new |
| `tests/smoke_cat_list_filter.py` | new |

Estimated diff: ~80 lines added, ~3 modified.

## Open questions / future work

- Could add Cmd/Ctrl-F to focus the search box. Minor convenience; skipping for v1.
- Could persist the search string across clan switches if user feedback wants it. Skipping; default behavior less surprising.
- A "no matches" placeholder row in the QListWidget would be friendlier than an empty list. Punt unless requested.
