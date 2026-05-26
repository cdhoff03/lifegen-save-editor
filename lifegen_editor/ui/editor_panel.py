"""Left-hand panel: every control needed to edit a cat's appearance.

Emits :pyattr:`EditorPanel.changed` whenever any control updates the underlying
CatData. The owning window listens and re-renders the preview.
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..io import CatData
from . import options as opt


def _combo(items: list[str], initial: str | None = None) -> QComboBox:
    box = QComboBox()
    for i in items:
        box.addItem(i)
    if initial is not None and initial in items:
        box.setCurrentText(initial)
    return box


def _opt_combo(items: list[str], initial: str | None = None) -> QComboBox:
    """Combo with a leading "(none)" entry for nullable fields."""
    box = QComboBox()
    box.addItem("(none)", userData=None)
    for i in items:
        box.addItem(i, userData=i)
    if initial:
        ix = box.findData(initial)
        if ix >= 0:
            box.setCurrentIndex(ix)
    return box


class EditorPanel(QScrollArea):
    """Scrollable form. Holds widgets for every CatData field; pushes changes
    back to a shared CatData instance."""

    changed = Signal()

    def __init__(self, cat: CatData, parent=None):
        super().__init__(parent)
        self.cat = cat
        self._loading = False
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        self.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        layout.addWidget(self._build_pose_group())
        layout.addWidget(self._build_pelt_group())
        layout.addWidget(self._build_tortie_group())
        layout.addWidget(self._build_eyes_group())
        layout.addWidget(self._build_skin_group())
        layout.addWidget(self._build_whites_group())
        layout.addWidget(self._build_scars_group())
        layout.addWidget(self._build_accessory_group())
        layout.addStretch(1)

        self.load_from_cat()

    # ---------- groups ----------
    def _build_pose_group(self) -> QGroupBox:
        g = QGroupBox("Pose and Lineart")
        f = QFormLayout(g)

        self.pose_spin = QSpinBox()
        self.pose_spin.setRange(0, opt.POSE_COUNT - 1)
        self.pose_spin.valueChanged.connect(self._on_change(lambda v: self._set("sprite_number", v)))
        f.addRow("Pose", self.pose_spin)

        self.lineart_combo = QComboBox()
        for label, _ in opt.LINEART_STYLES:
            self.lineart_combo.addItem(label)
        self.lineart_combo.currentIndexChanged.connect(self._on_change(self._set_lineart))
        f.addRow("Lineart", self.lineart_combo)

        toggles = QWidget()
        h = QHBoxLayout(toggles)
        h.setContentsMargins(0, 0, 0, 0)
        self.reverse_cb = QCheckBox("Reverse (mirror)")
        self.reverse_cb.toggled.connect(self._on_change(lambda v: self._set("reverse", bool(v))))
        h.addWidget(self.reverse_cb)
        self.shading_cb = QCheckBox("Shading")
        self.shading_cb.toggled.connect(self._on_change(lambda v: self._set("shading", bool(v))))
        h.addWidget(self.shading_cb)
        h.addStretch(1)
        f.addRow(toggles)
        return g

    def _build_pelt_group(self) -> QGroupBox:
        g = QGroupBox("Pelt")
        f = QFormLayout(g)

        self.pelt_combo = _combo(opt.PELT_NAMES)
        self.pelt_combo.currentTextChanged.connect(self._on_change(lambda v: self._set("pelt_name", v)))
        f.addRow("Pattern", self.pelt_combo)

        self.colour_combo = _combo(opt.colours())
        self.colour_combo.currentTextChanged.connect(self._on_change(lambda v: self._set("colour", v)))
        f.addRow("Colour", self.colour_combo)

        self.tint_combo = _combo(opt.tint_names())
        self.tint_combo.currentTextChanged.connect(self._on_change(lambda v: self._set("tint", v)))
        f.addRow("Tint", self.tint_combo)
        return g

    def _build_tortie_group(self) -> QGroupBox:
        g = QGroupBox("Tortoiseshell")
        f = QFormLayout(g)

        self.tortie_cb = QCheckBox("Enable tortie / calico")
        self.tortie_cb.toggled.connect(self._on_change(lambda v: self._set("is_tortie", bool(v))))
        f.addRow(self.tortie_cb)

        self.tortie_mask_combo = _opt_combo(opt.tortie_masks())
        self.tortie_mask_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("tortie_mask", self.tortie_mask_combo.currentData()))
        )
        f.addRow("Mask", self.tortie_mask_combo)

        self.tortie_pattern_combo = _opt_combo(opt.tortie_pattern_names())
        self.tortie_pattern_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("tortie_pattern", self.tortie_pattern_combo.currentData()))
        )
        f.addRow("Overlay pattern", self.tortie_pattern_combo)

        self.tortie_colour_combo = _opt_combo(opt.colours())
        self.tortie_colour_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("tortie_colour", self.tortie_colour_combo.currentData()))
        )
        f.addRow("Overlay colour", self.tortie_colour_combo)
        return g

    def _build_eyes_group(self) -> QGroupBox:
        g = QGroupBox("Eyes")
        f = QFormLayout(g)
        self.eye_combo = _combo(opt.eye_colours())
        self.eye_combo.currentTextChanged.connect(self._on_change(lambda v: self._set("eye_colour", v)))
        f.addRow("Primary", self.eye_combo)

        self.eye2_combo = _opt_combo(opt.secondary_eye_colours())
        self.eye2_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("eye_colour2", self.eye2_combo.currentData()))
        )
        f.addRow("Heterochromia", self.eye2_combo)
        return g

    def _build_skin_group(self) -> QGroupBox:
        g = QGroupBox("Skin")
        f = QFormLayout(g)
        self.skin_combo = _combo(opt.skin_colours())
        self.skin_combo.currentTextChanged.connect(self._on_change(lambda v: self._set("skin", v)))
        f.addRow("Skin tone", self.skin_combo)
        return g

    def _build_whites_group(self) -> QGroupBox:
        g = QGroupBox("White patches / Points / Vitiligo")
        f = QFormLayout(g)
        self.white_combo = _opt_combo(opt.white_patches_only())
        self.white_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("white_patches", self.white_combo.currentData()))
        )
        f.addRow("White patches", self.white_combo)

        self.white_tint_combo = _combo(opt.white_tint_names())
        self.white_tint_combo.currentTextChanged.connect(
            self._on_change(lambda v: self._set("white_patches_tint", v))
        )
        f.addRow("White tint", self.white_tint_combo)

        self.points_combo = _opt_combo(opt.POINT_MARKINGS)
        self.points_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("points", self.points_combo.currentData()))
        )
        f.addRow("Points", self.points_combo)

        self.vitiligo_combo = _opt_combo(opt.VITILIGO_MARKINGS)
        self.vitiligo_combo.currentIndexChanged.connect(
            self._on_change(lambda _: self._set("vitiligo", self.vitiligo_combo.currentData()))
        )
        f.addRow("Vitiligo", self.vitiligo_combo)
        return g

    def _build_scars_group(self) -> QGroupBox:
        g = QGroupBox("Scars (multi-select)")
        v = QVBoxLayout(g)
        self.scar_list = QListWidget()
        self.scar_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for scar in opt.all_scars():
            item = QListWidgetItem(scar)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.scar_list.addItem(item)
        self.scar_list.itemChanged.connect(self._on_change(self._on_scar_changed))
        self.scar_list.setMaximumHeight(160)
        v.addWidget(self.scar_list)
        return g

    def _build_accessory_group(self) -> QGroupBox:
        g = QGroupBox("Accessories (stacked; bottom of list draws on top)")
        v = QVBoxLayout(g)

        add_row = QHBoxLayout()
        self.accessory_combo = QComboBox()
        for label, value in opt.all_accessories():
            self.accessory_combo.addItem(label, userData=value)
        add_row.addWidget(self.accessory_combo, 1)
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._on_change(self._add_accessory))
        add_row.addWidget(add_btn)
        v.addLayout(add_row)

        body = QHBoxLayout()
        self.accessory_list = QListWidget()
        self.accessory_list.setMaximumHeight(120)
        body.addWidget(self.accessory_list, 1)
        btns = QVBoxLayout()
        up_btn = QPushButton("↑")
        up_btn.clicked.connect(self._on_change(lambda: self._move_accessory(-1)))
        down_btn = QPushButton("↓")
        down_btn.clicked.connect(self._on_change(lambda: self._move_accessory(1)))
        rm_btn = QPushButton("×")
        rm_btn.clicked.connect(self._on_change(self._remove_accessory))
        btns.addWidget(up_btn)
        btns.addWidget(down_btn)
        btns.addWidget(rm_btn)
        btns.addStretch(1)
        body.addLayout(btns)
        v.addLayout(body)
        return g

    def _add_accessory(self) -> None:
        value = self.accessory_combo.currentData()
        if not value or value in self.cat.accessories:
            return
        self.cat.accessories.append(value)
        self._refresh_accessory_list()

    def _remove_accessory(self) -> None:
        row = self.accessory_list.currentRow()
        if row < 0 or row >= len(self.cat.accessories):
            return
        del self.cat.accessories[row]
        self._refresh_accessory_list()
        new_row = min(row, len(self.cat.accessories) - 1)
        if new_row >= 0:
            self.accessory_list.setCurrentRow(new_row)

    def _move_accessory(self, delta: int) -> None:
        row = self.accessory_list.currentRow()
        new = row + delta
        if row < 0 or new < 0 or new >= len(self.cat.accessories):
            return
        self.cat.accessories[row], self.cat.accessories[new] = (
            self.cat.accessories[new],
            self.cat.accessories[row],
        )
        self._refresh_accessory_list()
        self.accessory_list.setCurrentRow(new)

    def _refresh_accessory_list(self) -> None:
        self.accessory_list.clear()
        for acc in self.cat.accessories:
            self.accessory_list.addItem(acc)

    # ---------- bind ----------
    def _set_lineart(self, idx: int) -> None:
        _, flags = opt.LINEART_STYLES[idx]
        for k, v in flags.items():
            setattr(self.cat, k, v)

    def _on_scar_changed(self, item: QListWidgetItem) -> None:
        self.cat.scars = [
            self.scar_list.item(i).text()
            for i in range(self.scar_list.count())
            if self.scar_list.item(i).checkState() == Qt.CheckState.Checked
        ]

    def _set(self, attr: str, value) -> None:
        setattr(self.cat, attr, value)

    def _on_change(self, handler: Callable):
        def _wrapped(*args, **kwargs):
            if self._loading:
                return
            handler(*args, **kwargs)
            self.changed.emit()
        return _wrapped

    # ---------- public ----------
    def load_from_cat(self) -> None:
        """Push the current `cat` values into every widget without emitting changes."""
        self._loading = True
        try:
            self.pose_spin.setValue(self.cat.sprite_number)
            self.reverse_cb.setChecked(self.cat.reverse)
            self.shading_cb.setChecked(self.cat.shading)
            for ix, (_, flags) in enumerate(opt.LINEART_STYLES):
                if (self.cat.dead == flags["dead"] and self.cat.dark_forest == flags["dark_forest"]
                        and self.cat.april_fools == flags["april_fools"]):
                    self.lineart_combo.setCurrentIndex(ix)
                    break

            self.pelt_combo.setCurrentText(self.cat.pelt_name)
            self.colour_combo.setCurrentText(self.cat.colour)
            self.tint_combo.setCurrentText(self.cat.tint)

            self.tortie_cb.setChecked(self.cat.is_tortie)
            self._select_data(self.tortie_mask_combo, self.cat.tortie_mask)
            self._select_data(self.tortie_pattern_combo, self.cat.tortie_pattern)
            self._select_data(self.tortie_colour_combo, self.cat.tortie_colour)

            self.eye_combo.setCurrentText(self.cat.eye_colour)
            self._select_data(self.eye2_combo, self.cat.eye_colour2)

            self.skin_combo.setCurrentText(self.cat.skin)

            self._select_data(self.white_combo, self.cat.white_patches)
            self.white_tint_combo.setCurrentText(self.cat.white_patches_tint)
            self._select_data(self.points_combo, self.cat.points)
            self._select_data(self.vitiligo_combo, self.cat.vitiligo)

            scar_set = set(self.cat.scars)
            for i in range(self.scar_list.count()):
                item = self.scar_list.item(i)
                item.setCheckState(
                    Qt.CheckState.Checked if item.text() in scar_set else Qt.CheckState.Unchecked
                )

            self._refresh_accessory_list()
        finally:
            self._loading = False

    def replace_cat(self, cat: CatData) -> None:
        """Switch to editing a different CatData instance and refresh the UI."""
        self.cat = cat
        self.load_from_cat()
        self.changed.emit()

    @staticmethod
    def _select_data(combo: QComboBox, value):
        ix = combo.findData(value)
        if ix >= 0:
            combo.setCurrentIndex(ix)
        else:
            combo.setCurrentIndex(0)  # "(none)"
