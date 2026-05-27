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
        # Explicit text color too, otherwise dark-mode Windows themes paint the
        # QLabel in white and it's unreadable on the pale background.
        self.setStyleSheet(
            "QWidget { background-color: #fff7d6; color: #1f1f1f; }"
            "QPushButton { background-color: #fff; color: #1f1f1f; }"
        )
        self.hide()

    def show_for(self, manifest: dict, asset: dict) -> None:
        self._manifest = manifest
        self._asset = asset
        self.label.setText(f"v{manifest['version']} is available.")
        self.show()

    def _on_update_clicked(self) -> None:
        if self._manifest and self._asset:
            self.update_requested.emit(self._manifest, self._asset)


# -----------------------------------------------------------------------------
# Help → Check for Updates… dialog.
# -----------------------------------------------------------------------------

class CheckForUpdatesDialog(QDialog):
    update_requested = Signal(dict, dict)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Check for Updates")
        self.setMinimumWidth(380)

        self._manifest: dict | None = None
        self._asset: dict | None = None

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

    def _on_finished(self, manifest, asset, error) -> None:
        if error is not None:
            self._show_error(error)
            return
        if manifest is None:
            from lifegen_editor import __version__
            self._label.setText(f"You're on the latest version ({__version__}).")
            return
        self._manifest = manifest
        self._asset = asset
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
        assert self._manifest is not None
        notes = self._manifest.get("notes_url")
        text = f"<b>Version {self._manifest['version']}</b> is available."
        if notes:
            text += f'<br><a href="{notes}">Release notes</a>'
        self._label.setText(text)
        self._label.setOpenExternalLinks(True)
        update = QPushButton("Update")
        update.clicked.connect(self._emit_update)
        self._buttons.addButton(update, QDialogButtonBox.ButtonRole.AcceptRole)

    def _emit_update(self) -> None:
        if self._manifest and self._asset:
            self.update_requested.emit(self._manifest, self._asset)
            self.accept()


# -----------------------------------------------------------------------------
# Download progress dialog. Spawns the updater on success.
# -----------------------------------------------------------------------------

class _DownloadExtractWorker(QObject):
    """Downloads the asset and extracts it. Both phases run on the worker thread
    so the UI stays responsive — extracting a PyInstaller --onedir Windows zip
    is hundreds of MB and thousands of files, which is far too long to block
    the UI thread on."""

    progress = Signal(int, int)  # bytes_so_far, total (or -1) — download phase
    state = Signal(str)          # "downloading" | "extracting"
    finished = Signal(object, object)  # (staging_path or None, error or None)

    def __init__(self, asset: dict, archive_dest: Path, staging_parent: Path) -> None:
        super().__init__()
        self._asset = asset
        self._archive_dest = archive_dest
        self._staging_parent = staging_parent

    def run(self) -> None:
        try:
            self.state.emit("downloading")
            def cb(done: int, total: int | None) -> None:
                self.progress.emit(done, total if total is not None else -1)
            archive = client.download(self._asset, self._archive_dest, progress_cb=cb)
            self.state.emit("extracting")
            staging = client.extract(archive, self._staging_parent)
            self.finished.emit(staging, None)
        except Exception as e:  # noqa: BLE001
            self.finished.emit(None, e)


def run_download_and_swap(parent: QWidget, manifest: dict, asset: dict) -> None:
    """Show a modal progress dialog, download + extract on a worker thread, then
    spawn the updater and quit."""
    # Use a temp directory per update attempt; updater cleans it up later.
    temp_root = Path(tempfile.mkdtemp(prefix="lifegen-update-"))
    archive_path = temp_root / Path(asset["url"]).name

    dlg = QDialog(parent)
    dlg.setWindowTitle("Updating")
    dlg.setMinimumWidth(380)
    label = QLabel(f"Downloading v{manifest['version']}…")
    bar = QProgressBar()
    bar.setRange(0, 0)  # indeterminate until we know total
    cancel = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
    cancel.rejected.connect(dlg.reject)
    v = QVBoxLayout(dlg)
    v.addWidget(label)
    v.addWidget(bar)
    v.addWidget(cancel)

    thread = QThread(parent)
    worker = _DownloadExtractWorker(asset, archive_path, temp_root)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            if bar.maximum() != total:
                bar.setRange(0, total)
            bar.setValue(done)

    def on_state(state: str) -> None:
        if state == "downloading":
            label.setText(f"Downloading v{manifest['version']}…")
        elif state == "extracting":
            label.setText(f"Extracting v{manifest['version']}…")
            # Switch the bar to indeterminate during extract — extract doesn't
            # emit per-file progress, and a frozen 100% bar looks broken.
            bar.setRange(0, 0)

    def on_finished(staging, error) -> None:
        thread.quit()
        if error is not None:
            dlg.reject()
            QMessageBox.critical(parent, "Update failed", str(error))
            return

        label.setText("Launching updater…")
        bar.setRange(0, 0)

        install_dir = swap.current_install_dir()
        new_root = _resolve_new_root(staging, install_dir)
        new_exe = _resolve_new_exe(new_root)

        import subprocess, sys as _sys
        popen_kwargs = {"close_fds": True}
        if _sys.platform == "win32":
            # Detach the child from this process's console/job so it survives
            # our quit cleanly and Windows doesn't propagate the shutdown.
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            popen_kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        subprocess.Popen([
            str(new_exe),
            "--finish-update",
            "--install-dir", str(install_dir),
            "--staging-dir", str(new_root),
            "--parent-pid", str(os.getpid()),
        ], **popen_kwargs)
        dlg.accept()
        # Give the OS a moment to register the child, then quit.
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        QTimer.singleShot(200, QApplication.instance().quit)

    worker.progress.connect(on_progress)
    worker.state.connect(on_state)
    worker.finished.connect(on_finished)
    thread.start()
    dlg.exec()


def _resolve_new_root(staging: Path, install_dir: Path) -> Path:
    """Find the directory inside ``staging`` that should replace ``install_dir``.

    Archives we publish contain a single top-level directory (the
    PyInstaller output dir on Windows/Linux, or the .app bundle on macOS).
    """
    entries = [p for p in staging.iterdir() if not p.name.startswith(".")]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return staging


def _resolve_new_exe(new_root: Path) -> Path:
    """Path of the executable inside the freshly-extracted new build."""
    import sys
    if sys.platform == "win32":
        return new_root / "lifegen-save-editor.exe"
    if sys.platform == "darwin":
        return new_root / "Contents" / "MacOS" / "lifegen-save-editor"
    return new_root / "lifegen-save-editor"
