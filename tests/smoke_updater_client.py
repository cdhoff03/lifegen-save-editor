"""Tests for lifegen_editor.updater.client (pure logic, no Qt)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.updater import client

SAMPLE_MANIFEST = {
    "version": "0.2.0",
    "assets": {
        "windows-x64": {"url": "https://example/win.zip", "sha256": "a" * 64},
        "macos-arm64": {"url": "https://example/mac-arm64.zip", "sha256": "b" * 64},
        "macos-x64":   {"url": "https://example/mac-x64.zip", "sha256": "c" * 64},
        "linux-x64":   {"url": "https://example/linux.tar.gz", "sha256": "d" * 64},
    },
}


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


def test_pick_asset() -> None:
    assert client.pick_asset(SAMPLE_MANIFEST, "Windows", "AMD64")["url"].endswith("win.zip")
    assert client.pick_asset(SAMPLE_MANIFEST, "Windows", "x86_64")["url"].endswith("win.zip")
    assert client.pick_asset(SAMPLE_MANIFEST, "Darwin", "arm64")["url"].endswith("mac-arm64.zip")
    assert client.pick_asset(SAMPLE_MANIFEST, "Darwin", "x86_64")["url"].endswith("mac-x64.zip")
    assert client.pick_asset(SAMPLE_MANIFEST, "Linux", "x86_64")["url"].endswith("linux.tar.gz")
    # Unsupported combinations return None
    assert client.pick_asset(SAMPLE_MANIFEST, "Linux", "aarch64") is None
    assert client.pick_asset(SAMPLE_MANIFEST, "FreeBSD", "amd64") is None
    assert client.pick_asset(SAMPLE_MANIFEST, "Darwin", "ppc") is None


def main() -> int:
    test_is_newer()
    test_pick_asset()
    print("smoke_updater_client OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
