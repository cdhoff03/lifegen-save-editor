"""Main application window. Wires the three panels together."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QWidget,
)

from ..io import CatData, parse_pcm_json, parse_pcm_url, to_pcm_json, to_pcm_url
from ..saves import Clan, write_clan_with_backup
from ..sprites import SpriteLoader, draw_cat
from .editor_panel import EditorPanel
from .preview import PreviewPanel
from .save_panel import SavePanel


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LifeGen / ClanGen Save Editor")
        self.resize(1280, 800)

        self.loader = SpriteLoader()
        self.cat = CatData()

        self.editor = EditorPanel(self.cat)
        self.preview = PreviewPanel(self.cat, self.loader)
        self.save_panel = SavePanel()

        self.editor.changed.connect(self.preview.render)
        self.preview.export_json_requested.connect(self._copy_json)
        self.preview.copy_url_requested.connect(self._copy_url)
        self.preview.save_png_requested.connect(self._save_png)
        self.save_panel.cat_picked.connect(self._on_cat_picked)
        self.save_panel.apply_requested.connect(self._on_apply_clicked)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.editor)
        splitter.addWidget(self.preview)
        splitter.addWidget(self.save_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([320, 640, 320])
        self.setCentralWidget(splitter)

        self._build_menu()
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready. Pick a cat and start editing.")

    # ---- menu ----
    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")

        act_import_json = QAction("&Import pixel-cat-maker JSON…", self)
        act_import_json.triggered.connect(self._import_json)
        file_menu.addAction(act_import_json)

        act_import_url = QAction("Import from share &URL…", self)
        act_import_url.triggered.connect(self._import_url)
        file_menu.addAction(act_import_url)

        file_menu.addSeparator()

        act_export_json = QAction("Copy current as &JSON", self)
        act_export_json.triggered.connect(self._copy_json)
        file_menu.addAction(act_export_json)

        act_export_url = QAction("Copy current as share UR&L", self)
        act_export_url.triggered.connect(self._copy_url)
        file_menu.addAction(act_export_url)

        act_save_png = QAction("Save &PNG…", self)
        act_save_png.triggered.connect(self._save_png)
        file_menu.addAction(act_save_png)

        file_menu.addSeparator()

        act_quit = QAction("&Quit", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        file_menu.addAction(act_quit)

        help_menu = bar.addMenu("&Help")
        about = QAction("&About", self)
        about.triggered.connect(self._show_about)
        help_menu.addAction(about)

    # ---- actions ----
    def _import_json(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import pixel-cat-maker JSON", filter="JSON (*.json);;All (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
            self.cat = parse_pcm_json(text)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self._sync_after_replace()
        self.statusBar().showMessage(f"Imported {Path(path).name}")

    def _import_url(self) -> None:
        # If clipboard has a likely URL, prefill.
        clip = QGuiApplication.clipboard().text() if QGuiApplication.clipboard() else ""
        if "pixel-cat-maker" not in clip:
            clip = ""
        url, ok = QInputDialog.getText(
            self, "Import share URL",
            "Paste a pixel-cat-maker share URL:", text=clip,
        )
        if not ok or not url:
            return
        try:
            self.cat = parse_pcm_url(url)
        except Exception as e:
            QMessageBox.critical(self, "Import failed", str(e))
            return
        self._sync_after_replace()
        self.statusBar().showMessage("Imported URL")

    def _copy_json(self) -> None:
        text = to_pcm_json(self.cat)
        QGuiApplication.clipboard().setText(text)
        self.statusBar().showMessage("Copied JSON to clipboard")

    def _copy_url(self) -> None:
        url = to_pcm_url(self.cat)
        QGuiApplication.clipboard().setText(url)
        self.statusBar().showMessage("Copied share URL to clipboard")

    def _save_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Save preview PNG", "cat.png", filter="PNG (*.png)")
        if not path:
            return
        try:
            from PIL import Image as PILImage
            img = draw_cat(
                self.cat.to_pelt(), self.cat.sprite_number, self.loader,
                dead=self.cat.dead, dark_forest=self.cat.dark_forest,
                shading=self.cat.shading, april_fools=self.cat.april_fools,
            )
            scale = self.preview.scale_combo.currentData() or 4
            img = img.resize((img.width * scale, img.height * scale), PILImage.NEAREST)
            img.save(path)
            self.statusBar().showMessage(f"Saved {Path(path).name}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _on_cat_picked(self, clan: Clan, index: int) -> None:
        # Load that cat's appearance into the editor (so the user sees what
        # they're about to overwrite).
        cat = clan.cats[index]
        try:
            self.cat = CatData.from_save_cat(cat.raw)
        except Exception as e:
            QMessageBox.warning(self, "Could not parse cat", str(e))
            return
        self._sync_after_replace()
        self.statusBar().showMessage(f"Loaded {cat.display_name} from save.")

    def _on_apply_clicked(self, clan: Clan, index: int) -> None:
        cat_ref = clan.cats[index]
        confirm = QMessageBox.question(
            self, "Apply appearance",
            f"Overwrite the appearance of {cat_ref.display_name} in clan "
            f"“{clan.name}”?\n\nA backup of clan_cats.json will be created first.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            self.cat.apply_to_save_cat(cat_ref.raw)
            backup = write_clan_with_backup(clan)
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))
            return
        self.save_panel.report_applied(backup)
        self.statusBar().showMessage(f"Saved. Backup: {backup.name}")

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "<h3>LifeGen / ClanGen Save Editor</h3>"
            "<p>Edit the appearance of cats in ClanGen and LifeGen save files.</p>"
            "<p>Sprite assets © the ClanGen Team (CC BY-NC 4.0). "
            "Compositor logic ported from "
            "<a href='https://github.com/cgen-tools/pixel-cat-maker'>pixel-cat-maker</a> "
            "(MPL-2.0). Not affiliated with the ClanGen or LifeGen teams.</p>",
        )

    # ---- helpers ----
    def _sync_after_replace(self) -> None:
        """Whenever ``self.cat`` is reassigned, both editor and preview need
        to be repointed at the new instance."""
        self.editor.replace_cat(self.cat)
        self.preview.replace_cat(self.cat)


def run() -> int:
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.show()
    return app.exec()
