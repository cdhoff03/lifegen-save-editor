"""Tests for lifegen_editor.updater.client (pure logic, no Qt)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.updater import client


def test_is_newer() -> None:
    # Basic ordering
    assert client.is_newer("0.1.0", "0.2.0") is True
    assert client.is_newer("0.2.0", "0.1.0") is False
    assert client.is_newer("0.2.0", "0.2.0") is False
    # Patch-level
    assert client.is_newer("1.2.3", "1.2.4") is True
    # Minor / major
    assert client.is_newer("1.9.0", "2.0.0") is True
    # Dev sentinel always older
    assert client.is_newer("0.0.0-dev", "0.1.0") is True
    assert client.is_newer("0.0.0-dev", "0.0.0-dev") is False
    # Tag with leading 'v' tolerated on either side
    assert client.is_newer("v0.1.0", "v0.2.0") is True


def main() -> int:
    test_is_newer()
    print("smoke_updater_client OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
