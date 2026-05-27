"""Integration tests for the directory swap logic.

These do not exercise the parent-PID wait or relaunch — they use the
unit-level ``_swap_directories`` helper, which is what those branches
delegate to.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.updater import swap


def test_swap_happy_path(tmp: Path) -> None:
    install = tmp / "install"
    install.mkdir()
    (install / "app.txt").write_text("old")

    staging = tmp / "staging"
    staging.mkdir()
    (staging / "app.txt").write_text("new")

    swap._swap_directories(install_dir=install, staging_dir=staging)

    assert (install / "app.txt").read_text() == "new"
    # The old directory was renamed aside; one .old.* sibling should exist.
    siblings = list(tmp.glob("install.old.*"))
    assert len(siblings) == 1
    assert (siblings[0] / "app.txt").read_text() == "old"


def test_swap_rollback_on_move_failure(tmp: Path) -> None:
    install = tmp / "install"
    install.mkdir()
    (install / "app.txt").write_text("old")
    # Staging path does not exist — move will fail.
    staging = tmp / "does-not-exist"

    try:
        swap._swap_directories(install_dir=install, staging_dir=staging)
    except swap.SwapError:
        pass
    else:
        raise AssertionError("expected SwapError")

    # Original install is still intact at the original path.
    assert install.exists()
    assert (install / "app.txt").read_text() == "old"
    # No stray .old.* siblings left behind.
    assert list(tmp.glob("install.old.*")) == []


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        test_swap_happy_path(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_swap_rollback_on_move_failure(Path(td))
    print("smoke_updater_swap OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
