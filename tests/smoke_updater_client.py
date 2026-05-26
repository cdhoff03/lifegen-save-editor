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


import hashlib
import http.server
import socketserver
import tempfile
import threading
from contextlib import contextmanager


@contextmanager
def serve_bytes(payload: bytes):
    """Serve ``payload`` from a localhost HTTP server. Yields the URL."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *a, **k) -> None:  # silence
            pass

    with socketserver.TCPServer(("127.0.0.1", 0), Handler) as httpd:
        host, port = httpd.server_address
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://{host}:{port}/asset.bin"
        finally:
            httpd.shutdown()


def test_download_verifies_sha256() -> None:
    payload = b"hello-update" * 100
    good_sha = hashlib.sha256(payload).hexdigest()
    bad_sha = "0" * 64

    with serve_bytes(payload) as url:
        # Good checksum: returns path to file containing the payload
        with tempfile.TemporaryDirectory() as td:
            out = client.download({"url": url, "sha256": good_sha}, Path(td) / "asset.bin")
            assert out.read_bytes() == payload

        # Bad checksum: raises ChecksumMismatch and removes the partial file
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "asset.bin"
            try:
                client.download({"url": url, "sha256": bad_sha}, dest)
            except client.ChecksumMismatch:
                pass
            else:
                raise AssertionError("expected ChecksumMismatch")
            assert not dest.exists()


import json
import tarfile
import zipfile


def test_fetch_manifest() -> None:
    manifest = {"version": "0.5.0", "assets": SAMPLE_MANIFEST["assets"]}
    with serve_bytes(json.dumps(manifest).encode("utf-8")) as url:
        got = client.fetch_manifest(url)
        assert got["version"] == "0.5.0"


def test_extract_zip(tmp: Path) -> None:
    src = tmp / "src.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("inner/hello.txt", "hi")
    out = client.extract(src, tmp / "staging")
    assert (out / "inner" / "hello.txt").read_text() == "hi"


def test_extract_tar_gz(tmp: Path) -> None:
    src = tmp / "src.tar.gz"
    payload_dir = tmp / "payload"
    (payload_dir / "inner").mkdir(parents=True)
    (payload_dir / "inner" / "hello.txt").write_text("hi")
    with tarfile.open(src, "w:gz") as tf:
        tf.add(payload_dir, arcname="root")
    out = client.extract(src, tmp / "staging")
    assert (out / "root" / "inner" / "hello.txt").read_text() == "hi"


def main() -> int:
    test_is_newer()
    test_pick_asset()
    test_download_verifies_sha256()
    test_fetch_manifest()
    with tempfile.TemporaryDirectory() as td:
        test_extract_zip(Path(td))
    with tempfile.TemporaryDirectory() as td:
        test_extract_tar_gz(Path(td))
    print("smoke_updater_client OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
