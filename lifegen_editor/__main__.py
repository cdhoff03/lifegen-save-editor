"""Entry point. Run with ``python -m lifegen_editor`` or via the installed
``lifegen-save-editor`` script.

Modes:
- Normal: launch the GUI.
- ``LIFEGEN_EDITOR_SELFTEST=1``: render the preview once, print OK, exit.
"""
import os
import sys


def _selftest() -> int:
    from PySide6.QtWidgets import QApplication
    from lifegen_editor.ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.preview.render()
    app.processEvents()
    print(f"LIFEGEN_EDITOR_SELFTEST OK cat={win.cat.pelt_name}/{win.cat.colour}")
    return 0


def main() -> int:
    if os.environ.get("LIFEGEN_EDITOR_SELFTEST") == "1":
        return _selftest()

    # Absolute imports — PyInstaller runs this script as the top-level __main__,
    # so relative imports break inside the frozen binary.
    from lifegen_editor.ui.main_window import run
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
