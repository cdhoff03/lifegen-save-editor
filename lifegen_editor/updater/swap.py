"""Cross-platform swap-and-relaunch logic for the auto-updater.

This module is also the ``--finish-update`` entry point: when the running
app downloads a new build, it spawns the new exe with ``--finish-update``
plus install/staging/parent-PID args, then exits. The new exe (running
from a temp location) waits for the parent to exit, swaps the install
directory, and relaunches the freshly-installed exe.

See docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md.
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Locating the current install on disk.
# -----------------------------------------------------------------------------

def current_executable() -> Path:
    """Return the path of the running executable (frozen) or sys.executable (dev)."""
    return Path(sys.executable).resolve()


def current_install_dir() -> Path:
    """Return the install directory.

    Windows / Linux: parent of the running exe (PyInstaller --onedir layout).
    macOS: the ``*.app`` bundle root, walking up from sys.executable.
    """
    exe = current_executable()
    if sys.platform == "darwin":
        for p in [exe, *exe.parents]:
            if p.suffix == ".app":
                return p
        raise RuntimeError(f"could not locate .app bundle from {exe}")
    return exe.parent


# -----------------------------------------------------------------------------
# Atomic directory swap with rollback.
# -----------------------------------------------------------------------------


class SwapError(RuntimeError):
    """The swap could not be completed; the install is left untouched."""


def _swap_directories(install_dir: Path, staging_dir: Path) -> Path:
    """Atomically replace ``install_dir`` with ``staging_dir``.

    On success returns the path of the renamed-aside old install, so the
    caller can clean it up.

    On failure raises ``SwapError`` and leaves ``install_dir`` in its
    original state.
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    old_path = install_dir.with_name(install_dir.name + f".old.{timestamp}")

    # Step 1: rename current install aside.
    try:
        install_dir.rename(old_path)
    except OSError as e:
        raise SwapError(f"could not rename install dir aside: {e}") from e

    # Step 2: move staging into place.
    try:
        shutil.move(str(staging_dir), str(install_dir))
    except OSError as e:
        # Try to roll back so the user is not left without an install.
        try:
            old_path.rename(install_dir)
        except OSError:
            pass
        raise SwapError(f"could not move staging into place: {e}") from e

    return old_path


def _wait_for_pid_exit(pid: int, timeout: float = 30.0, interval: float = 0.2) -> bool:
    """Block until ``pid`` exits or ``timeout`` elapses. Returns True if it exited."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(interval)
    return not _pid_alive(pid)


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # Use the Win32 API to avoid spawning tasklist; ctypes is in stdlib.
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _relaunch(install_dir: Path) -> None:
    """Spawn the freshly-installed executable, detached from this process."""
    if sys.platform == "win32":
        exe = install_dir / "lifegen-save-editor.exe"
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [str(exe)],
            close_fds=True,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
        )
    elif sys.platform == "darwin":
        # install_dir is the .app bundle root.
        subprocess.Popen(["open", "-a", str(install_dir)])
    else:
        exe = install_dir / "lifegen-save-editor"
        subprocess.Popen([str(exe)], start_new_session=True, close_fds=True)


def _schedule_cleanup(path: Path) -> None:
    """Best-effort removal. On Windows, fall back to delete-on-reboot."""
    try:
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return
    except Exception:  # noqa: BLE001
        pass
    if sys.platform == "win32":
        try:
            import ctypes
            MOVEFILE_DELAY_UNTIL_REBOOT = 0x4
            ctypes.windll.kernel32.MoveFileExW(str(path), None, MOVEFILE_DELAY_UNTIL_REBOOT)
        except Exception:  # noqa: BLE001
            pass


def _write_failure_log(install_dir: Path, message: str) -> None:
    """Write a failure marker next to the install directory."""
    target = install_dir.with_name("update-failed.log")
    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(f"{datetime.utcnow().isoformat()}Z {message}\n")
    except OSError:
        pass


# -----------------------------------------------------------------------------
# Top-level entry point used by __main__.py when --finish-update is present.
# -----------------------------------------------------------------------------

def run_finish_update(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="lifegen-save-editor --finish-update")
    parser.add_argument("--install-dir", required=True, type=Path)
    parser.add_argument("--staging-dir", required=True, type=Path)
    parser.add_argument("--parent-pid", required=True, type=int)
    args = parser.parse_args(argv)

    install_dir = args.install_dir.resolve()
    staging_dir = args.staging_dir.resolve()

    if not _wait_for_pid_exit(args.parent_pid):
        _write_failure_log(install_dir, f"parent pid {args.parent_pid} did not exit in 30s")
        return 2

    try:
        old_path = _swap_directories(install_dir=install_dir, staging_dir=staging_dir)
    except SwapError as e:
        _write_failure_log(install_dir, f"swap failed: {e}")
        return 3

    try:
        _relaunch(install_dir)
    except Exception as e:  # noqa: BLE001
        _write_failure_log(install_dir, f"relaunch failed: {e}")
        return 4

    _schedule_cleanup(old_path)
    # The staging archive directory (parent of staging_dir) is in TEMP; best-effort.
    _schedule_cleanup(staging_dir.parent)
    return 0
