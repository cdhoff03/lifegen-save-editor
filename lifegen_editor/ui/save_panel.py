"""Right-hand panel: pick a game install, browse clans + cats, apply edits."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Signal
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

from ..saves import Clan, list_clans, load_clan, write_clan_with_backup
from ..saves.locator import candidate_roots


class SavePanel(QWidget):
    """Save-file pane. Emits :pyattr:`cat_picked` with a (clan, index) tuple when
    the user clicks a cat — the main window decides what to do with the click.
    Emits :pyattr:`apply_requested` when "Apply appearance" is clicked."""

    cat_picked = Signal(object, int)  # Clan, cat index
    apply_requested = Signal(object, int)  # Clan, cat index

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_clan: Optional[Clan] = None
        self.current_save_root: Optional[Path] = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)

        # Game install
        install_group = QGroupBox("Save location")
        gl = QVBoxLayout(install_group)
        self.root_combo = QComboBox()
        for inst in candidate_roots():
            label = f"{inst.name} — {inst.save_root}"
            if not inst.exists:
                label += "  (not found)"
            self.root_combo.addItem(label, userData=str(inst.save_root))
        self.root_combo.currentIndexChanged.connect(self._on_root_change)
        gl.addWidget(self.root_combo)
        browse_row = QHBoxLayout()
        browse_btn = QPushButton("Browse for folder…")
        browse_btn.clicked.connect(self._on_browse)
        browse_row.addWidget(browse_btn)
        browse_row.addStretch(1)
        gl.addLayout(browse_row)
        outer.addWidget(install_group)

        # Clan picker
        clan_group = QGroupBox("Clan")
        cl = QVBoxLayout(clan_group)
        self.clan_combo = QComboBox()
        self.clan_combo.currentIndexChanged.connect(self._on_clan_change)
        cl.addWidget(self.clan_combo)
        outer.addWidget(clan_group)

        # Cats
        cats_group = QGroupBox("Cats")
        cl2 = QVBoxLayout(cats_group)
        self.cat_list = QListWidget()
        self.cat_list.currentRowChanged.connect(self._on_cat_change)
        cl2.addWidget(self.cat_list, 1)
        outer.addWidget(cats_group, 1)

        # Action
        action_group = QGroupBox("Action")
        ag = QVBoxLayout(action_group)
        self.apply_btn = QPushButton("Apply appearance → selected cat")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._on_apply)
        ag.addWidget(self.apply_btn)
        self.status_label = QLabel("No save loaded.")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        ag.addWidget(self.status_label)
        outer.addWidget(action_group)

        # Auto-load first existing root
        self._on_root_change(self.root_combo.currentIndex())

    # ---- events ----
    def _on_root_change(self, idx: int) -> None:
        path_str = self.root_combo.itemData(idx)
        if not path_str:
            return
        self.current_save_root = Path(path_str)
        self._reload_clans()

    def _on_browse(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select a saves folder")
        if not path:
            return
        self.current_save_root = Path(path)
        # Add to combo as a new entry, select it
        label = f"Custom — {path}"
        self.root_combo.blockSignals(True)
        self.root_combo.addItem(label, userData=path)
        self.root_combo.setCurrentIndex(self.root_combo.count() - 1)
        self.root_combo.blockSignals(False)
        self._reload_clans()

    def _reload_clans(self) -> None:
        self.clan_combo.blockSignals(True)
        self.clan_combo.clear()
        if self.current_save_root is None:
            self.clan_combo.blockSignals(False)
            return
        clans = list_clans(self.current_save_root)
        for path in clans:
            self.clan_combo.addItem(path.name, userData=str(path))
        self.clan_combo.blockSignals(False)
        if not clans:
            self.cat_list.clear()
            self.current_clan = None
            self.apply_btn.setEnabled(False)
            self.status_label.setText(
                f"No clans found under {self.current_save_root}." if self.current_save_root.exists()
                else f"Folder does not exist: {self.current_save_root}"
            )
            return
        self._on_clan_change(0)

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

    def _on_cat_change(self, row: int) -> None:
        if row < 0 or self.current_clan is None:
            self.apply_btn.setEnabled(False)
            return
        self.apply_btn.setEnabled(True)
        cat = self.current_clan.cats[row]
        self.apply_btn.setText(f"Apply appearance → {cat.display_name}")
        self.cat_picked.emit(self.current_clan, row)

    def _on_apply(self) -> None:
        row = self.cat_list.currentRow()
        if row < 0 or self.current_clan is None:
            return
        self.apply_requested.emit(self.current_clan, row)

    # ---- driven by main window ----
    def report_applied(self, backup_path: Path) -> None:
        self.status_label.setText(f"Saved. Backup: {backup_path.name}")

    def selected_cat_index(self) -> int:
        return self.cat_list.currentRow()
