"""Entry point. Run with ``python -m lifegen_editor`` or via the installed
``lifegen-save-editor`` script.

If ``LIFEGEN_EDITOR_SELFTEST=1`` is set, the app constructs the main window,
renders the preview once, prints OK, and exits 0. Used by packaging smoke
tests to verify a frozen binary boots and finds its bundled assets.
"""
import os
import sys

# Absolute imports — PyInstaller runs this script as the top-level __main__,
# so relative imports break inside the frozen binary.
from lifegen_editor.ui.main_window import MainWindow, run


def _selftest() -> int:
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    win = MainWindow()
    win.preview.render()
    app.processEvents()
    print(f"LIFEGEN_EDITOR_SELFTEST OK cat={win.cat.pelt_name}/{win.cat.colour}")
    return 0


def main() -> int:
    if os.environ.get("LIFEGEN_EDITOR_SELFTEST") == "1":
        return _selftest()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
