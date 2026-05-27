"""Qt-side UI for the updater: banner + Check-for-Updates dialog."""
from __future__ import annotations

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


# -----------------------------------------------------------------------------
# Background worker for the network calls (update check).
# -----------------------------------------------------------------------------

class _CheckWorker(QObject):
    """Runs ``tufup_client.check_for_update()`` off the UI thread."""

    finished = Signal(object, object)  # (target_meta_or_None, error_or_None)

    def run(self) -> None:
        from . import tufup_client
        try:
            target = tufup_client.check_for_update()
        except Exception as e:  # noqa: BLE001
            self.finished.emit(None, e)
            return
        self.finished.emit(target, None)


# -----------------------------------------------------------------------------
# Top-of-window banner shown when an auto-check finds a new version.
# -----------------------------------------------------------------------------

class UpdateBanner(QWidget):
    update_requested = Signal(object)  # tufup TargetMeta

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target = None

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

        self.setStyleSheet(
            "QWidget { background-color: #fff7d6; color: #1f1f1f; }"
            "QPushButton { background-color: #fff; color: #1f1f1f; }"
        )
        self.hide()

    def show_for(self, target) -> None:
        """Show the banner for a tufup TargetMeta describing the new version."""
        self._target = target
        version_str = str(getattr(target, "version", "")) or "a new version"
        self.label.setText(f"v{version_str} is available.")
        self.show()

    def _on_update_clicked(self) -> None:
        if self._target is not None:
            self.update_requested.emit(self._target)


# -----------------------------------------------------------------------------
# Help → Check for Updates… dialog.
# -----------------------------------------------------------------------------

class CheckForUpdatesDialog(QDialog):
    update_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(380)

        self._target = None

        self._label = QLabel("Checking for updates…")
        self._buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self._buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._label)
        layout.addWidget(self._buttons)

        self._thread: QThread | None = None
        self._worker: _CheckWorker | None = None
        self._start_check()

    def _start_check(self) -> None:
        self._thread = QThread(self)
        self._worker = _CheckWorker()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_finished)
        self._worker.finished.connect(self._thread.quit)
        self._thread.start()

    def _on_finished(self, target, error) -> None:
        if error is not None:
            self._show_error(error)
            return
        if target is None:
            from lifegen_editor import __version__
            self._label.setText(f"You're on the latest version ({__version__}).")
            return
        self._target = target
        self._show_update_available()

    def _show_error(self, error: Exception) -> None:
        self._label.setText(f"Could not check for updates: {error}")
        retry = QPushButton("Retry")
        retry.clicked.connect(self._retry)
        self._buttons.addButton(retry, QDialogButtonBox.ButtonRole.ActionRole)

    def _retry(self) -> None:
        # Reset UI and re-run.
        for btn in self._buttons.buttons():
            if btn.text() == "Retry":
                self._buttons.removeButton(btn)
        self._label.setText("Checking for updates…")
        self._start_check()

    def _show_update_available(self) -> None:
        assert self._target is not None
        version_str = str(getattr(self._target, "version", "")) or "a new version"
        self._label.setText(f"<b>Version {version_str}</b> is available.")
        update = QPushButton("Update")
        update.clicked.connect(self._emit_update)
        self._buttons.addButton(update, QDialogButtonBox.ButtonRole.AcceptRole)

    def _emit_update(self) -> None:
        if self._target is not None:
            self.update_requested.emit(self._target)
            self.accept()


# -----------------------------------------------------------------------------
# Download / install worker and orchestration function (tufup-driven).
# -----------------------------------------------------------------------------

class _UpdateWorker(QObject):
    progress = Signal(int, int)        # bytes_so_far, total (or -1)
    finished = Signal(object)          # error or None — on success this never fires
                                       # because tufup spawns the installer and exits

    def __init__(self, target) -> None:
        super().__init__()
        self._target = target

    def run(self) -> None:
        from . import tufup_client
        try:
            def cb(done: int, total: int | None) -> None:
                self.progress.emit(done, total if total is not None else -1)
            # download_and_apply_update either spawns the install script and
            # terminates this process, or raises. It does not return normally.
            tufup_client.perform_update(progress_cb=cb)
        except Exception as e:  # noqa: BLE001
            self.finished.emit(e)


def run_update(parent: QWidget, target) -> None:
    """Show a modal progress dialog and run the tufup-driven update.

    On the happy path the process exits before this function returns (tufup
    spawns the install script and calls sys.exit). On failure we report the
    error and leave the running install intact.
    """
    dlg = QDialog(parent)
    dlg.setWindowTitle("Updating")
    dlg.setMinimumWidth(380)
    version_str = str(getattr(target, "version", "")) or "the new version"
    label = QLabel(f"Downloading and installing v{version_str}…")
    bar = QProgressBar()
    bar.setRange(0, 0)  # indeterminate; tufup may not report progress
    cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    cancel.rejected.connect(dlg.reject)
    v = QVBoxLayout(dlg)
    v.addWidget(label)
    v.addWidget(bar)
    v.addWidget(cancel)

    thread = QThread(parent)
    worker = _UpdateWorker(target)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            if bar.maximum() != total:
                bar.setRange(0, total)
            bar.setValue(done)

    def on_finished(error) -> None:
        thread.quit()
        dlg.reject()
        QMessageBox.critical(parent, "Update failed", str(error))

    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    thread.start()
    dlg.exec()
