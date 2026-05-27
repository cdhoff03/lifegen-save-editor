"""Tests for the clipboard-format sniffer used by Import from clipboard."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.ui.main_window import _detect_clipboard_format


def test_detect_url() -> None:
    assert _detect_clipboard_format("https://cgen-tools.github.io/pixel-cat-maker/#abc") == "url"
    assert _detect_clipboard_format("http://example.com/x") == "url"
    # Whitespace around the input is tolerated.
    assert _detect_clipboard_format("  https://x  ") == "url"


def test_detect_json() -> None:
    assert _detect_clipboard_format('{"pelt_name": "Tabby"}') == "json"
    assert _detect_clipboard_format('  {"a":1}\n') == "json"


def test_detect_garbage() -> None:
    assert _detect_clipboard_format("") is None
    assert _detect_clipboard_format("just some text") is None
    assert _detect_clipboard_format("[1, 2, 3]") is None  # array, not an object
    assert _detect_clipboard_format("ftp://x") is None


def main() -> int:
    test_detect_url()
    test_detect_json()
    test_detect_garbage()
    print("smoke_clipboard_import OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
