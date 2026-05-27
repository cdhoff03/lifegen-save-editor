"""Qt-side UI for the updater: banner + Check-for-Updates dialog."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from . import client, swap


# -----------------------------------------------------------------------------
# Background worker for the network calls (manifest fetch + download).
# -----------------------------------------------------------------------------

class _CheckWorker(QObject):
    """Runs ``client.check_for_update()`` off the UI thread."""

    finished = Signal(object, object, object)  # (manifest_or_None, asset_or_None, error_or_None)

    def run(self) -> None:
        try:
            result = client.check_for_update()
        except client.UpdateCheckError as e:
            self.finished.emit(None, None, e)
            return
        if result is None:
            self.finished.emit(None, None, None)
        else:
            manifest, asset = result
            self.finished.emit(manifest, asset, None)


# -----------------------------------------------------------------------------
# Top-of-window banner shown when an auto-check finds a new version.
# -----------------------------------------------------------------------------

class UpdateBanner(QWidget):
    update_requested = Signal(dict, dict)  # (manifest, asset)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._manifest: dict | None = None
        self._asset: dict | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.label = QLabel("Update available.")
        update_btn = QPushButton("Update")
        update_btn.clicked.connect(self._on_update_clicked)
        dismiss_btn = QPushButton("Dismiss")
        dismiss_btn.clicked.connect(self.hide)

        layout.addWidget(self.label, 1)
        layout.addWidget(update_btn)
        layout.addWidget(dismiss_btn)

        # Subtle highlighted background so it's noticeable but not screaming.
        self.setStyleSheet("background-color: #fff7d6;")
        self.hide()

    def show_for(self, manifest: dict, asset: dict) -> None:
        self._manifest = manifest
        self._asset = asset
        self.label.setText(f"v{manifest['version']} is available.")
        self.show()

    def _on_update_clicked(self) -> None:
        if self._manifest and self._asset:
            self.update_requested.emit(self._manifest, self._asset)
