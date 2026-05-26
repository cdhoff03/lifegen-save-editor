"""Live preview canvas. Renders the current CatData with the compositor."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPalette
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..io import CatData
from ..sprites import SpriteLoader, draw_cat, CELL_SIZE
from .qt_image import pil_to_qpixmap


class PreviewPanel(QWidget):
    """Central preview area: scaled cat image, pose stepper, scale selector,
    and quick export buttons."""

    export_json_requested = Signal()
    copy_url_requested = Signal()
    save_png_requested = Signal()

    SCALES = (2, 4, 6, 8, 12)

    def __init__(self, cat: CatData, loader: SpriteLoader, parent=None):
        super().__init__(parent)
        self.cat = cat
        self.loader = loader

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # Image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setMinimumSize(CELL_SIZE * 4, CELL_SIZE * 4)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.image_label.setFrameShape(QFrame.Shape.StyledPanel)
        # Subtle background so transparent cat edges are visible.
        pal = self.image_label.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor("#202024"))
        self.image_label.setAutoFillBackground(True)
        self.image_label.setPalette(pal)
        outer.addWidget(self.image_label, 1)

        # Controls
        row = QHBoxLayout()
        row.addWidget(QLabel("Scale:"))
        self.scale_combo = QComboBox()
        for s in self.SCALES:
            self.scale_combo.addItem(f"{s}x", userData=s)
        self.scale_combo.setCurrentIndex(self.SCALES.index(6))
        self.scale_combo.currentIndexChanged.connect(self.render)
        row.addWidget(self.scale_combo)
        row.addStretch(1)
        outer.addLayout(row)

        # Export row
        exp = QHBoxLayout()
        save_btn = QPushButton("Save PNG…")
        save_btn.clicked.connect(self.save_png_requested.emit)
        exp.addWidget(save_btn)
        json_btn = QPushButton("Copy JSON")
        json_btn.clicked.connect(self.export_json_requested.emit)
        exp.addWidget(json_btn)
        url_btn = QPushButton("Copy share URL")
        url_btn.clicked.connect(self.copy_url_requested.emit)
        exp.addWidget(url_btn)
        outer.addLayout(exp)

        self.render()

    def replace_cat(self, cat: CatData) -> None:
        self.cat = cat
        self.render()

    def render(self) -> None:
        pelt = self.cat.to_pelt()
        try:
            img = draw_cat(
                pelt,
                self.cat.sprite_number,
                self.loader,
                dead=self.cat.dead,
                dark_forest=self.cat.dark_forest,
                shading=self.cat.shading,
                april_fools=self.cat.april_fools,
            )
        except Exception as e:
            self.image_label.setText(f"Render error:\n{e}")
            return
        scale = self.scale_combo.currentData() or 4
        from PIL import Image as PILImage
        scaled = img.resize((img.width * scale, img.height * scale), PILImage.NEAREST)
        self.image_label.setPixmap(pil_to_qpixmap(scaled))
