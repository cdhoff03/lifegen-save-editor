# GitHub Actions Release & Auto-Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions tag-triggered multi-OS release pipeline and an in-app auto-update flow (download + relaunch) to `lifegen-save-editor`.

**Architecture:** A `.github/workflows/release.yml` workflow builds Windows-x64, macOS-arm64, macOS-x64, and Linux-x64 artifacts in parallel via PyInstaller, then publishes a GitHub Release with the archives plus a `latest.json` manifest and `checksums.txt`. A new `lifegen_editor/updater/` package fetches the manifest at launch, surfaces a banner / `Help → Check for Updates…` dialog, and on user confirmation downloads the platform-appropriate asset, verifies its SHA-256, and re-executes the new build with a `--finish-update` flag that handles the atomic swap and relaunch.

**Tech Stack:** Python 3.12, PySide6 (Qt6), PyInstaller 6.x, `urllib.request` (stdlib, no new deps), GitHub Actions, `softprops/action-gh-release@v2`.

**Spec:** `docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md`

---

## Prerequisites (manual, before Task 1)

The project is not yet a git repo. The user must do these before plan execution starts:

1. `cd /Users/cdhoff/claude/lifegen-save-editor && git init && git add -A && git commit -m "chore: initial commit"`
2. Create a public GitHub repo (e.g., `https://github.com/<owner>/lifegen-save-editor`).
3. `git remote add origin git@github.com:<owner>/lifegen-save-editor.git && git push -u origin main`
4. Record `<owner>` value — Task 13 hard-codes it into `client.py`.

These steps are out of scope for the agent worker but are required for CI to run.

## File structure

| Path | Action | Responsibility |
|---|---|---|
| `lifegen_editor/_version.py` | create | Single source of truth for app version at runtime. Overwritten by CI from the git tag. |
| `lifegen_editor/__init__.py` | modify | Re-export `__version__` from `_version.py` instead of hard-coding it. |
| `lifegen_editor/__main__.py` | modify | Detect `--finish-update` in argv before constructing QApplication; route to `swap.run_finish_update`. |
| `lifegen_editor/updater/__init__.py` | create | Package marker. |
| `lifegen_editor/updater/client.py` | create | Pure-logic: version compare, OS/arch asset pick, manifest fetch, download + SHA-256 verify, extract. No Qt. |
| `lifegen_editor/updater/ui.py` | create | `UpdateBanner` widget and `CheckForUpdatesDialog`. Drives `client` from Qt side. |
| `lifegen_editor/updater/swap.py` | create | `run_finish_update` entry point + per-OS swap + relaunch logic. |
| `lifegen_editor/ui/main_window.py` | modify | Embed `UpdateBanner` at top, add `Help → Check for Updates…`, kick off launch-time auto-check. |
| `.github/workflows/release.yml` | create | Tag-triggered 4-OS build matrix + release-publish job. |
| `scripts/make_release_manifest.py` | create | Generates `latest.json` and `checksums.txt` from downloaded artifacts in the release job. |
| `tests/smoke_updater_client.py` | create | Unit-style tests for version compare, asset pick, manifest parsing, download + checksum. |
| `tests/smoke_updater_swap.py` | create | Integration test for the swap + relaunch logic in a tmpdir using dummy executables. |
| `README.md` | modify | Add a "Releasing" section with `git tag v0.2.0 && git push --tags` and a manual smoke checklist. |

---

## Task 1: Add `_version.py` and refactor `__init__.py`

**Files:**
- Create: `lifegen_editor/_version.py`
- Modify: `lifegen_editor/__init__.py`

- [ ] **Step 1: Create `_version.py`**

Write `lifegen_editor/_version.py`:

```python
"""Single source of truth for the app version.

This file is overwritten by CI (see .github/workflows/release.yml) when
building from a tag. In the source tree it stays at the dev sentinel below.
"""
__version__ = "0.0.0-dev"
```

- [ ] **Step 2: Update `__init__.py` to re-export**

Replace the contents of `lifegen_editor/__init__.py` with:

```python
"""LifeGen / ClanGen save editor with built-in pixel cat maker."""
from ._version import __version__

__all__ = ["__version__"]
```

- [ ] **Step 3: Verify nothing else hard-codes the version**

Run: `grep -rn '"0.1.0"\|version.*=.*"0\.' lifegen_editor/ packaging/ pyproject.toml`
Expected: only `pyproject.toml` (`version = "0.1.0"`) and `packaging/lifegen-save-editor.spec` (`"CFBundleShortVersionString": "0.1.0"`) match. Both are static metadata that CI doesn't need to override for v1 — leave them.

- [ ] **Step 4: Smoke-test the import**

Run: `python -c "import lifegen_editor; print(lifegen_editor.__version__)"`
Expected output: `0.0.0-dev`

- [ ] **Step 5: Commit**

```bash
git add lifegen_editor/_version.py lifegen_editor/__init__.py
git commit -m "feat(updater): move version into _version.py for CI to overwrite"
```

---

## Task 2: Create the updater package skeleton

**Files:**
- Create: `lifegen_editor/updater/__init__.py`

- [ ] **Step 1: Create the package marker**

Write `lifegen_editor/updater/__init__.py`:

```python
"""In-app auto-update client.

See docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md
for the design.
"""
```

- [ ] **Step 2: Commit**

```bash
git add lifegen_editor/updater/__init__.py
git commit -m "feat(updater): add updater package skeleton"
```

---

## Task 3: TDD `is_newer` version comparison

**Files:**
- Create: `tests/smoke_updater_client.py`
- Create: `lifegen_editor/updater/client.py`

- [ ] **Step 1: Write the failing test**

Write `tests/smoke_updater_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/smoke_updater_client.py`
Expected: `ModuleNotFoundError` or `AttributeError` on `client.is_newer` — module/function doesn't exist yet.

- [ ] **Step 3: Implement `is_newer` in `client.py`**

Create `lifegen_editor/updater/client.py`:

```python
"""Auto-update client. Pure logic, no Qt dependencies.

See docs/superpowers/specs/2026-05-26-github-actions-release-and-autoupdate-design.md.
"""
from __future__ import annotations

from typing import Iterable


def _parse(version: str) -> tuple[int, int, int, int]:
    """Parse a version string into a 4-tuple suitable for ordering.

    Returns ``(major, minor, patch, dev_flag)`` where ``dev_flag`` is 0 for
    a normal release and -1 for a ``-dev`` sentinel (so it sorts before
    any released version with the same major.minor.patch).
    """
    v = version.lstrip("v")
    dev_flag = 0
    if v.endswith("-dev"):
        v = v[: -len("-dev")]
        dev_flag = -1
    parts: list[str] = v.split(".")
    while len(parts) < 3:
        parts.append("0")
    major, minor, patch = (int(p) for p in parts[:3])
    return (major, minor, patch, dev_flag)


def is_newer(current: str, remote: str) -> bool:
    """Return True if ``remote`` is strictly newer than ``current``."""
    return _parse(remote) > _parse(current)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/smoke_updater_client.py`
Expected: `smoke_updater_client OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_updater_client.py lifegen_editor/updater/client.py
git commit -m "feat(updater): semver-style version compare with -dev sentinel"
```

---

## Task 4: TDD `pick_asset` for all supported platforms

**Files:**
- Modify: `tests/smoke_updater_client.py`
- Modify: `lifegen_editor/updater/client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/smoke_updater_client.py` (above the existing `def main`):

```python
SAMPLE_MANIFEST = {
    "version": "0.2.0",
    "assets": {
        "windows-x64": {"url": "https://example/win.zip", "sha256": "a" * 64},
        "macos-arm64": {"url": "https://example/mac-arm64.zip", "sha256": "b" * 64},
        "macos-x64":   {"url": "https://example/mac-x64.zip", "sha256": "c" * 64},
        "linux-x64":   {"url": "https://example/linux.tar.gz", "sha256": "d" * 64},
    },
}


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
```

And add a call to `main()`:

```python
def main() -> int:
    test_is_newer()
    test_pick_asset()
    print("smoke_updater_client OK")
    return 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/smoke_updater_client.py`
Expected: `AttributeError: module 'lifegen_editor.updater.client' has no attribute 'pick_asset'`

- [ ] **Step 3: Implement `pick_asset` in `client.py`**

Append to `lifegen_editor/updater/client.py`:

```python
# OS+arch (as returned by platform.system() / platform.machine()) → manifest key.
_ASSET_TABLE: dict[tuple[str, str], str] = {
    ("Windows", "AMD64"):  "windows-x64",
    ("Windows", "x86_64"): "windows-x64",
    ("Darwin",  "arm64"):  "macos-arm64",
    ("Darwin",  "x86_64"): "macos-x64",
    ("Linux",   "x86_64"): "linux-x64",
}


def pick_asset(manifest: dict, system: str, machine: str) -> dict | None:
    """Return the manifest asset entry for this OS+arch, or None."""
    key = _ASSET_TABLE.get((system, machine))
    if key is None:
        return None
    return manifest.get("assets", {}).get(key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/smoke_updater_client.py`
Expected: `smoke_updater_client OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_updater_client.py lifegen_editor/updater/client.py
git commit -m "feat(updater): pick_asset for windows/macos-arm64/macos-x64/linux"
```

---

## Task 5: TDD download + SHA-256 verification

**Files:**
- Modify: `tests/smoke_updater_client.py`
- Modify: `lifegen_editor/updater/client.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/smoke_updater_client.py` (above `def main`):

```python
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
```

And add the call:

```python
def main() -> int:
    test_is_newer()
    test_pick_asset()
    test_download_verifies_sha256()
    print("smoke_updater_client OK")
    return 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/smoke_updater_client.py`
Expected: `AttributeError: module 'lifegen_editor.updater.client' has no attribute 'download'`

- [ ] **Step 3: Implement `download` in `client.py`**

Append to `lifegen_editor/updater/client.py`:

```python
import hashlib
import urllib.request
from pathlib import Path
from typing import Callable


class UpdateError(Exception):
    """Base class for all updater errors."""


class UpdateCheckError(UpdateError):
    """Failed to fetch or parse the release manifest."""


class ChecksumMismatch(UpdateError):
    """Downloaded asset did not match the expected SHA-256."""


def download(
    asset: dict,
    dest: Path,
    progress_cb: Callable[[int, int | None], None] | None = None,
    chunk_size: int = 64 * 1024,
) -> Path:
    """Stream ``asset['url']`` to ``dest``, verifying ``asset['sha256']``.

    ``progress_cb(bytes_so_far, total_or_None)`` is called after each chunk.
    Raises ``ChecksumMismatch`` if the SHA-256 doesn't match (and deletes
    the partial file).
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    expected = asset["sha256"].lower()
    hasher = hashlib.sha256()
    bytes_so_far = 0

    req = urllib.request.Request(asset["url"], headers={"User-Agent": "lifegen-save-editor-updater/1"})
    with urllib.request.urlopen(req, timeout=30) as resp, open(dest, "wb") as f:
        total_header = resp.headers.get("Content-Length")
        total = int(total_header) if total_header else None
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            f.write(chunk)
            hasher.update(chunk)
            bytes_so_far += len(chunk)
            if progress_cb:
                progress_cb(bytes_so_far, total)

    if hasher.hexdigest().lower() != expected:
        dest.unlink(missing_ok=True)
        raise ChecksumMismatch(
            f"sha256 mismatch: expected {expected}, got {hasher.hexdigest()}"
        )
    return dest
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/smoke_updater_client.py`
Expected: `smoke_updater_client OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_updater_client.py lifegen_editor/updater/client.py
git commit -m "feat(updater): stream download with sha256 verification"
```

---

## Task 6: Add manifest fetch, extract, and a `Manifest` typed wrapper

**Files:**
- Modify: `lifegen_editor/updater/client.py`
- Modify: `tests/smoke_updater_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/smoke_updater_client.py` (above `def main`):

```python
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
```

And add the calls:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python tests/smoke_updater_client.py`
Expected: `AttributeError` on `fetch_manifest` or `extract`.

- [ ] **Step 3: Implement `fetch_manifest` and `extract`**

Append to `lifegen_editor/updater/client.py`:

```python
import json
import tarfile
import zipfile


def fetch_manifest(url: str, timeout: float = 10.0) -> dict:
    """GET ``url`` and parse the response as JSON. Raises UpdateCheckError."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "lifegen-save-editor-updater/1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        return json.loads(data.decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        raise UpdateCheckError(f"failed to fetch manifest: {e}") from e


def extract(archive: Path, dest_parent: Path) -> Path:
    """Extract ``archive`` into ``dest_parent`` and return the staging dir.

    Always extracts into a fresh subdirectory ``dest_parent / 'staging'`` so
    callers know exactly where to find the unpacked tree.
    """
    staging = dest_parent / "staging"
    if staging.exists():
        import shutil
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    suffix = "".join(archive.suffixes[-2:]) if archive.name.endswith(".tar.gz") else archive.suffix
    if suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(staging)
    elif suffix == ".tar.gz":
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(staging)
    else:
        raise UpdateError(f"unsupported archive type: {archive.name}")
    return staging
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python tests/smoke_updater_client.py`
Expected: `smoke_updater_client OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_updater_client.py lifegen_editor/updater/client.py
git commit -m "feat(updater): manifest fetch + zip/tar.gz extraction"
```

---

## Task 7: Add high-level `check_for_update` helper and module constants

**Files:**
- Modify: `lifegen_editor/updater/client.py`

- [ ] **Step 1: Append the module constants and helper**

Append to `lifegen_editor/updater/client.py`:

```python
import os
import platform
import sys


# TODO(user): set this to your GitHub <owner>/<repo> before first release.
UPDATE_REPO = "<owner>/lifegen-save-editor"


def manifest_url() -> str:
    return f"https://github.com/{UPDATE_REPO}/releases/latest/download/latest.json"


def auto_check_enabled() -> bool:
    """Auto-check runs only for frozen builds, and can be disabled by env var."""
    if os.environ.get("LIFEGEN_DISABLE_UPDATE_CHECK") == "1":
        return False
    return bool(getattr(sys, "frozen", False))


def check_for_update() -> tuple[dict, dict] | None:
    """Single-call helper: fetch manifest, compare versions, pick asset.

    Returns ``(manifest, asset)`` if an update is available for this platform,
    or ``None`` if up to date / platform unsupported. Raises ``UpdateCheckError``
    on network or parse failure.
    """
    from lifegen_editor import __version__ as current

    manifest = fetch_manifest(manifest_url())
    remote = manifest.get("version", "0.0.0")
    if not is_newer(current, remote):
        return None
    asset = pick_asset(manifest, platform.system(), platform.machine())
    if asset is None:
        return None
    return manifest, asset
```

- [ ] **Step 2: Smoke-test that the module still imports**

Run: `python -c "from lifegen_editor.updater import client; print(client.manifest_url())"`
Expected: `https://github.com/<owner>/lifegen-save-editor/releases/latest/download/latest.json`

- [ ] **Step 3: Commit**

```bash
git add lifegen_editor/updater/client.py
git commit -m "feat(updater): check_for_update helper + UPDATE_REPO constant"
```

---

## Task 8: Implement `current_install_dir` / `current_executable` helpers

**Files:**
- Create: `lifegen_editor/updater/swap.py`

- [ ] **Step 1: Create `swap.py` with locator helpers**

Write `lifegen_editor/updater/swap.py`:

```python
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
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


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
```

- [ ] **Step 2: Smoke-test the imports**

Run: `python -c "from lifegen_editor.updater import swap; print(swap.current_executable())"`
Expected: prints the path to your active Python interpreter (e.g., `/Users/.../python3.12`).

- [ ] **Step 3: Commit**

```bash
git add lifegen_editor/updater/swap.py
git commit -m "feat(updater): current_executable / current_install_dir helpers"
```

---

## Task 9: TDD the directory-swap helper

**Files:**
- Create: `tests/smoke_updater_swap.py`
- Modify: `lifegen_editor/updater/swap.py`

- [ ] **Step 1: Write the failing test**

Write `tests/smoke_updater_swap.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python tests/smoke_updater_swap.py`
Expected: `AttributeError: module 'lifegen_editor.updater.swap' has no attribute '_swap_directories'`

- [ ] **Step 3: Implement `_swap_directories`**

Append to `lifegen_editor/updater/swap.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python tests/smoke_updater_swap.py`
Expected: `smoke_updater_swap OK`

- [ ] **Step 5: Commit**

```bash
git add tests/smoke_updater_swap.py lifegen_editor/updater/swap.py
git commit -m "feat(updater): atomic directory swap with rollback on failure"
```

---

## Task 10: Implement `run_finish_update` end-to-end

**Files:**
- Modify: `lifegen_editor/updater/swap.py`

- [ ] **Step 1: Append parent-wait, relaunch, and entry point**

Append to `lifegen_editor/updater/swap.py`:

```python
import logging

log = logging.getLogger(__name__)


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
```

- [ ] **Step 2: Smoke-test it imports and exposes the entry point**

Run: `python -c "from lifegen_editor.updater.swap import run_finish_update; print(run_finish_update.__doc__ or 'ok')"`
Expected: prints `ok` (no traceback).

- [ ] **Step 3: Verify existing swap tests still pass**

Run: `python tests/smoke_updater_swap.py`
Expected: `smoke_updater_swap OK`

- [ ] **Step 4: Commit**

```bash
git add lifegen_editor/updater/swap.py
git commit -m "feat(updater): parent-PID wait, relaunch, cleanup, finish-update entry point"
```

---

## Task 11: Wire `--finish-update` dispatch into `__main__.py`

**Files:**
- Modify: `lifegen_editor/__main__.py`

- [ ] **Step 1: Replace `__main__.py` with the dispatch-aware version**

Replace the contents of `lifegen_editor/__main__.py` with:

```python
"""Entry point. Run with ``python -m lifegen_editor`` or via the installed
``lifegen-save-editor`` script.

Modes:
- Normal: launch the GUI.
- ``LIFEGEN_EDITOR_SELFTEST=1``: render the preview once, print OK, exit.
- ``--finish-update ...``: run the post-update swap-and-relaunch logic and
  exit without ever constructing a Qt application.
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
    # Handle the post-update mode before importing any Qt.
    if "--finish-update" in sys.argv:
        from lifegen_editor.updater.swap import run_finish_update

        rest = [a for a in sys.argv[1:] if a != "--finish-update"]
        return run_finish_update(rest)

    if os.environ.get("LIFEGEN_EDITOR_SELFTEST") == "1":
        return _selftest()
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test the new dispatch (no-op finish-update with bogus args)**

Run: `python -m lifegen_editor --finish-update --install-dir /tmp/nope --staging-dir /tmp/nope --parent-pid 1`
Expected: exits non-zero (2 or 3 depending on whether pid 1 happens to be alive — it usually is on Unix as init). No traceback, no Qt window opens. Confirms the dispatch is wired and Qt is never imported.

- [ ] **Step 3: Smoke-test that normal mode still works**

Run: `LIFEGEN_EDITOR_SELFTEST=1 python -m lifegen_editor` (or set the env var on Windows).
Expected: prints `LIFEGEN_EDITOR_SELFTEST OK cat=...` and exits 0.

- [ ] **Step 4: Commit**

```bash
git add lifegen_editor/__main__.py
git commit -m "feat(updater): dispatch --finish-update before importing Qt"
```

---

## Task 12: Build the `UpdateBanner` widget

**Files:**
- Create: `lifegen_editor/updater/ui.py`

- [ ] **Step 1: Write `ui.py` with the banner**

Write `lifegen_editor/updater/ui.py`:

```python
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
        self.setStyleSheet("background-color: #fff7d6;")
        self.hide()

    def show_for(self, manifest: dict, asset: dict) -> None:
        self._manifest = manifest
        self._asset = asset
        self.label.setText(f"v{manifest['version']} is available.")
        self.show()

    def _on_update_clicked(self) -> None:
        if self._manifest and self._asset:
            self.update_requested.emit(self._manifest, self._asset)
```

- [ ] **Step 2: Smoke-test the import path**

Run: `python -c "from lifegen_editor.updater.ui import UpdateBanner; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add lifegen_editor/updater/ui.py
git commit -m "feat(updater): UpdateBanner widget + background check worker"
```

---

## Task 13: Add `CheckForUpdatesDialog` and download-progress dialog

**Files:**
- Modify: `lifegen_editor/updater/ui.py`

- [ ] **Step 1: Append the dialog + download helper**

Append to `lifegen_editor/updater/ui.py`:

```python
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

class _DownloadWorker(QObject):
    progress = Signal(int, int)  # bytes_so_far, total (or -1)
    finished = Signal(object, object)  # (Path or None, error or None)

    def __init__(self, asset: dict, dest: Path) -> None:
        super().__init__()
        self._asset = asset
        self._dest = dest

    def run(self) -> None:
        try:
            def cb(done: int, total: int | None) -> None:
                self.progress.emit(done, total if total is not None else -1)
            out = client.download(self._asset, self._dest, progress_cb=cb)
            self.finished.emit(out, None)
        except Exception as e:  # noqa: BLE001
            self.finished.emit(None, e)


def run_download_and_swap(parent: QWidget, manifest: dict, asset: dict) -> None:
    """Show a modal progress dialog, download, extract, spawn updater, quit."""
    # Use a temp directory per update attempt; updater cleans it up later.
    temp_root = Path(tempfile.mkdtemp(prefix="lifegen-update-"))
    archive_path = temp_root / Path(asset["url"]).name

    dlg = QDialog(parent)
    dlg.setWindowTitle("Downloading update")
    dlg.setMinimumWidth(360)
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
    worker = _DownloadWorker(asset, archive_path)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)

    def on_progress(done: int, total: int) -> None:
        if total > 0:
            if bar.maximum() != total:
                bar.setRange(0, total)
            bar.setValue(done)

    def on_finished(out_path, error) -> None:
        thread.quit()
        if error is not None:
            dlg.reject()
            QMessageBox.critical(parent, "Update failed", str(error))
            return
        try:
            staging = client.extract(out_path, temp_root)
        except Exception as e:  # noqa: BLE001
            dlg.reject()
            QMessageBox.critical(parent, "Update failed", f"Could not extract: {e}")
            return

        # macOS staging contains a *.app; the install dir is the existing .app.
        # Windows/Linux staging contains a single subdir matching the install layout.
        install_dir = swap.current_install_dir()
        new_root = _resolve_new_root(staging, install_dir)
        new_exe = _resolve_new_exe(new_root)

        import subprocess
        subprocess.Popen([
            str(new_exe),
            "--finish-update",
            "--install-dir", str(install_dir),
            "--staging-dir", str(new_root),
            "--parent-pid", str(os.getpid()),
        ], close_fds=True)
        dlg.accept()
        # Give the OS a moment to register the child, then quit.
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        QTimer.singleShot(200, QApplication.instance().quit)

    worker.progress.connect(on_progress)
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
```

- [ ] **Step 2: Set the `UPDATE_REPO` constant**

Edit `lifegen_editor/updater/client.py` and replace the `UPDATE_REPO` line with the user's actual GitHub `<owner>/<repo>`:

```python
UPDATE_REPO = "<owner>/lifegen-save-editor"  # <-- replace <owner>
```

- [ ] **Step 3: Smoke-test imports**

Run: `python -c "from lifegen_editor.updater.ui import CheckForUpdatesDialog, UpdateBanner, run_download_and_swap; print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add lifegen_editor/updater/ui.py lifegen_editor/updater/client.py
git commit -m "feat(updater): Check for Updates dialog + download/extract/spawn helper"
```

---

## Task 14: Wire the banner, menu item, and launch-time check into `MainWindow`

**Files:**
- Modify: `lifegen_editor/ui/main_window.py`

- [ ] **Step 1: Import the updater pieces**

In `lifegen_editor/ui/main_window.py`, add these imports near the top (alongside the existing `from PySide6...` blocks):

```python
import sys

from PySide6.QtCore import QObject, QThread, QTimer
from PySide6.QtWidgets import QVBoxLayout

from ..updater import client as updater_client
from ..updater.ui import (
    CheckForUpdatesDialog,
    UpdateBanner,
    _CheckWorker,
    run_download_and_swap,
)
```

Note: keep the existing `from PySide6.QtCore import Qt` and `from PySide6.QtGui import QAction, QGuiApplication` lines as-is — just add the new symbols.

- [ ] **Step 2: Rework the central widget so the banner sits above the splitter**

In `MainWindow.__init__`, replace the block that calls `self.setCentralWidget(splitter)`:

```python
        splitter.setSizes([320, 640, 320])
        self.setCentralWidget(splitter)
```

with:

```python
        splitter.setSizes([320, 640, 320])

        self.update_banner = UpdateBanner()
        self.update_banner.update_requested.connect(self._begin_update)

        central = QWidget()
        v = QVBoxLayout(central)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        v.addWidget(self.update_banner)
        v.addWidget(splitter, 1)
        self.setCentralWidget(central)
```

- [ ] **Step 3: Add the Help menu entry**

In `_build_menu`, after the existing `help_menu.addAction(about)` line, add:

```python
        check_updates = QAction("&Check for Updates…", self)
        check_updates.triggered.connect(self._show_check_for_updates)
        help_menu.addAction(check_updates)
```

- [ ] **Step 4: Add the methods to `MainWindow`**

After the existing menu and action methods (anywhere before the closing of the class), add:

```python
    # ---- updater ----
    def _show_check_for_updates(self) -> None:
        dlg = CheckForUpdatesDialog(self)
        dlg.update_requested.connect(self._begin_update)
        dlg.exec()

    def _begin_update(self, manifest: dict, asset: dict) -> None:
        if not getattr(sys, "frozen", False):
            QMessageBox.information(
                self,
                "Updates not available",
                "Auto-update is only available in installed builds. "
                "Pull the latest source and reinstall to update.",
            )
            return
        run_download_and_swap(self, manifest, asset)

    def schedule_auto_check(self) -> None:
        """Run an auto-check 2 seconds after the window is shown."""
        if not updater_client.auto_check_enabled():
            return
        QTimer.singleShot(2000, self._start_auto_check)

    def _start_auto_check(self) -> None:
        self._auto_thread = QThread(self)
        self._auto_worker = _CheckWorker()
        self._auto_worker.moveToThread(self._auto_thread)
        self._auto_thread.started.connect(self._auto_worker.run)
        self._auto_worker.finished.connect(self._on_auto_check_done)
        self._auto_worker.finished.connect(self._auto_thread.quit)
        self._auto_thread.start()

    def _on_auto_check_done(self, manifest, asset, error) -> None:
        # Silent on failure for the auto path; banner only shown if update found.
        if error is None and manifest is not None and asset is not None:
            self.update_banner.show_for(manifest, asset)
```

- [ ] **Step 5: Kick the auto-check off from `run`**

In `lifegen_editor/ui/main_window.py`, replace the existing `run` function with:

```python
def run() -> int:
    app = QApplication.instance() or QApplication([])
    win = MainWindow()
    win.show()
    win.schedule_auto_check()
    return app.exec()
```

- [ ] **Step 6: Smoke-test the integration (uses the existing self-test)**

Run: `LIFEGEN_EDITOR_SELFTEST=1 python -m lifegen_editor`
Expected: prints `LIFEGEN_EDITOR_SELFTEST OK cat=...` and exits 0. The self-test doesn't call `schedule_auto_check`, so no network traffic.

- [ ] **Step 7: Manual visual smoke (optional but recommended)**

Run: `LIFEGEN_DISABLE_UPDATE_CHECK=1 python -m lifegen_editor`
Open `Help → Check for Updates…` — confirm the dialog appears, shows an error (manifest URL still has `<owner>` placeholder unless you replaced it), and a Retry button works.

- [ ] **Step 8: Commit**

```bash
git add lifegen_editor/ui/main_window.py
git commit -m "feat(updater): wire banner, Help menu item, and launch-time auto-check"
```

---

## Task 15: Create the release manifest generator script

**Files:**
- Create: `scripts/make_release_manifest.py`

- [ ] **Step 1: Create the script**

Write `scripts/make_release_manifest.py`:

```python
"""Generate latest.json + checksums.txt from a directory of release assets.

Used by .github/workflows/release.yml after all platform artifacts are
downloaded. Outputs both files into ``--out`` directory.

Usage:
  python scripts/make_release_manifest.py \\
    --assets-dir release-assets \\
    --version 0.2.0 \\
    --repo owner/lifegen-save-editor \\
    --out release-manifest
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


# Maps a substring of the archive filename to the manifest's asset key.
_KEY_PATTERNS = {
    "windows-x64": "windows-x64",
    "macos-arm64": "macos-arm64",
    "macos-x64":   "macos-x64",
    "linux-x64":   "linux-x64",
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(64 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _classify(name: str) -> str | None:
    for pattern, key in _KEY_PATTERNS.items():
        if pattern in name:
            return key
    return None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--assets-dir", required=True, type=Path)
    p.add_argument("--version", required=True)
    p.add_argument("--repo", required=True, help="owner/repo on GitHub")
    p.add_argument("--out", required=True, type=Path)
    args = p.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    archives = sorted(
        path for path in args.assets_dir.rglob("*")
        if path.is_file() and path.suffix in {".zip", ".gz"}
    )
    if not archives:
        raise SystemExit(f"no archives found in {args.assets_dir}")

    assets: dict[str, dict] = {}
    checksums_lines: list[str] = []
    for archive in archives:
        key = _classify(archive.name)
        if key is None:
            print(f"skipping unrecognized artifact: {archive.name}")
            continue
        digest = _sha256(archive)
        download_url = (
            f"https://github.com/{args.repo}/releases/download/"
            f"v{args.version}/{archive.name}"
        )
        assets[key] = {"url": download_url, "sha256": digest}
        checksums_lines.append(f"{digest}  {archive.name}")

    manifest = {
        "version": args.version,
        "released_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "notes_url": f"https://github.com/{args.repo}/releases/tag/v{args.version}",
        "assets": assets,
    }

    (args.out / "latest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.out / "checksums.txt").write_text("\n".join(sorted(checksums_lines)) + "\n")
    print(f"wrote {args.out / 'latest.json'}")
    print(f"wrote {args.out / 'checksums.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test it locally on a dummy directory**

```bash
mkdir -p /tmp/relsmoke/assets /tmp/relsmoke/out
echo "demo" > /tmp/relsmoke/assets/lifegen-save-editor-windows-x64.zip
echo "demo" > /tmp/relsmoke/assets/lifegen-save-editor-macos-arm64.zip
echo "demo" > /tmp/relsmoke/assets/lifegen-save-editor-macos-x64.zip
echo "demo" > /tmp/relsmoke/assets/lifegen-save-editor-linux-x64.tar.gz
python scripts/make_release_manifest.py --assets-dir /tmp/relsmoke/assets --version 9.9.9 --repo demo/demo --out /tmp/relsmoke/out
cat /tmp/relsmoke/out/latest.json
```
Expected: a JSON manifest with 4 asset entries, each pointing at `https://github.com/demo/demo/releases/download/v9.9.9/...`.

- [ ] **Step 3: Commit**

```bash
git add scripts/make_release_manifest.py
git commit -m "feat(release): script to build latest.json + checksums.txt from artifacts"
```

---

## Task 16: Create the GitHub Actions release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write the workflow**

Write `.github/workflows/release.yml`:

```yaml
name: release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write   # required to publish the GitHub Release

jobs:
  build:
    name: build (${{ matrix.asset_key }})
    runs-on: ${{ matrix.runner }}
    strategy:
      fail-fast: false
      matrix:
        include:
          - { runner: windows-latest, asset_key: windows-x64,  archive: lifegen-save-editor-windows-x64.zip,     archive_type: zip }
          - { runner: macos-13,       asset_key: macos-x64,    archive: lifegen-save-editor-macos-x64.zip,       archive_type: app-zip }
          - { runner: macos-latest,   asset_key: macos-arm64,  archive: lifegen-save-editor-macos-arm64.zip,     archive_type: app-zip }
          - { runner: ubuntu-latest,  asset_key: linux-x64,    archive: lifegen-save-editor-linux-x64.tar.gz,    archive_type: tar-gz }

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: pip

      - name: Extract version from tag
        id: ver
        shell: bash
        run: |
          tag="${GITHUB_REF_NAME}"
          version="${tag#v}"
          echo "version=$version" >> "$GITHUB_OUTPUT"

      - name: Write version into source
        shell: bash
        run: |
          printf '"""Single source of truth for the app version. Overwritten by CI from the tag."""\n__version__ = "%s"\n' "${{ steps.ver.outputs.version }}" > lifegen_editor/_version.py
          cat lifegen_editor/_version.py

      - name: Install dependencies
        shell: bash
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r packaging/requirements-build.txt

      - name: Build with PyInstaller
        shell: bash
        run: pyinstaller --clean --noconfirm packaging/lifegen-save-editor.spec

      - name: Package (Windows zip)
        if: matrix.archive_type == 'zip'
        shell: pwsh
        run: |
          $src = "dist/lifegen-save-editor"
          $dst = "${{ matrix.archive }}"
          Compress-Archive -Path "$src" -DestinationPath "$dst" -Force

      - name: Package (macOS .app via ditto)
        if: matrix.archive_type == 'app-zip'
        shell: bash
        run: |
          ditto -c -k --sequesterRsrc --keepParent \
            "dist/lifegen-save-editor.app" \
            "${{ matrix.archive }}"

      - name: Package (Linux tar.gz)
        if: matrix.archive_type == 'tar-gz'
        shell: bash
        run: |
          tar -czf "${{ matrix.archive }}" -C dist lifegen-save-editor

      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.asset_key }}
          path: ${{ matrix.archive }}
          if-no-files-found: error
          retention-days: 7

  release:
    name: publish release
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Extract version from tag
        id: ver
        shell: bash
        run: |
          tag="${GITHUB_REF_NAME}"
          echo "version=${tag#v}" >> "$GITHUB_OUTPUT"

      - name: Download all build artifacts
        uses: actions/download-artifact@v4
        with:
          path: release-assets

      - name: Generate manifest + checksums
        run: |
          python scripts/make_release_manifest.py \
            --assets-dir release-assets \
            --version "${{ steps.ver.outputs.version }}" \
            --repo "${{ github.repository }}" \
            --out release-manifest

      - name: Gather release files
        run: |
          mkdir release-files
          find release-assets -type f \( -name '*.zip' -o -name '*.tar.gz' \) -exec cp {} release-files/ \;
          cp release-manifest/latest.json release-files/
          cp release-manifest/checksums.txt release-files/
          ls -la release-files/

      - name: Publish GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          tag_name: ${{ github.ref_name }}
          generate_release_notes: true
          files: release-files/*
          fail_on_unmatched_files: true
```

- [ ] **Step 2: Validate the YAML locally**

Run: `python -c "import yaml, sys; yaml.safe_load(open('.github/workflows/release.yml')); print('yaml ok')"`
Expected: `yaml ok` (install PyYAML if needed: `pip install pyyaml`).

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: tag-triggered 4-OS release pipeline with latest.json manifest"
```

---

## Task 17: Update the README with a "Releasing" section and the auto-update behavior

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add the Releasing section**

Append to `README.md` (or insert before any pre-existing "License" / "Credits" section if one exists):

```markdown
## Auto-update

Installed builds check GitHub for a newer release on launch (and via
**Help → Check for Updates…**). Clicking *Update* downloads the
platform-appropriate archive, verifies its SHA-256, and relaunches the
new build. Set `LIFEGEN_DISABLE_UPDATE_CHECK=1` to disable the launch
check. Updates are silently skipped when running from source.

## Releasing

Releases are cut by pushing a `vX.Y.Z` tag. GitHub Actions builds for
Windows x64, macOS arm64, macOS x64, and Linux x64 in parallel and
publishes a Release with the archives, `checksums.txt`, and `latest.json`.

```bash
git tag v0.2.0
git push origin v0.2.0
```

After the workflow finishes:
1. Open the new Release and confirm 6 assets are attached (4 archives +
   `checksums.txt` + `latest.json`).
2. Install the previous version locally, launch it, open **Help → Check
   for Updates…**, and confirm the update flow downloads, swaps, and
   relaunches.
3. If the swap fails, look for `update-failed.log` next to the install
   directory.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document auto-update behavior and tag-driven release flow"
```

---

## Task 18: Final integration smoke

**Files:** (none modified)

- [ ] **Step 1: Confirm all unit tests pass**

Run: `python tests/smoke_updater_client.py && python tests/smoke_updater_swap.py`
Expected:
```
smoke_updater_client OK
smoke_updater_swap OK
```

- [ ] **Step 2: Confirm the existing smoke suite still passes**

Run: `python tests/smoke_io.py && python tests/smoke_saves.py && LIFEGEN_EDITOR_SELFTEST=1 python -m lifegen_editor`
Expected: all three succeed (the third prints `LIFEGEN_EDITOR_SELFTEST OK ...`).

- [ ] **Step 3: Build a local frozen binary**

```bash
.venv/bin/pip install -r requirements.txt -r packaging/requirements-build.txt
bash packaging/build.sh
ls -la dist/
```
Expected: `dist/lifegen-save-editor` (+ `dist/lifegen-save-editor.app` on macOS) exists.

- [ ] **Step 4: Run the frozen binary's self-test**

macOS:
```bash
LIFEGEN_EDITOR_SELFTEST=1 dist/lifegen-save-editor.app/Contents/MacOS/lifegen-save-editor
```
Linux:
```bash
LIFEGEN_EDITOR_SELFTEST=1 dist/lifegen-save-editor/lifegen-save-editor
```
Windows:
```bat
set LIFEGEN_EDITOR_SELFTEST=1
dist\lifegen-save-editor\lifegen-save-editor.exe
```
Expected: `LIFEGEN_EDITOR_SELFTEST OK cat=...`.

- [ ] **Step 5: Cut a test release**

After the user sets `UPDATE_REPO` correctly in `client.py` and has pushed the branch to GitHub:
```bash
git tag v0.1.0
git push origin v0.1.0
```
Open the Actions tab on GitHub and confirm the `release` workflow runs all 4 build matrix jobs to completion and publishes a Release with 6 attached files.

- [ ] **Step 6: End-to-end update smoke (manual)**

1. Install the v0.1.0 build on the local machine.
2. Bump `pyproject.toml` version to `0.2.0` (cosmetic), then `git tag v0.2.0 && git push origin v0.2.0`.
3. Once the v0.2.0 release is published, launch the installed v0.1.0 build.
4. Wait ~2 seconds — the update banner should appear. Click *Update*.
5. Confirm the progress dialog shows, the app exits, and a new v0.2.0 launches automatically.
6. In the new app, **Help → Check for Updates…** should report "You're on the latest version (0.2.0)."

- [ ] **Step 7: Final commit (if any cleanup was needed)**

```bash
git status
# If clean, no commit needed. Otherwise commit the small fix and push.
```

---

## Self-review notes

**Spec coverage check (run before handoff):**

| Spec requirement | Implemented by |
|---|---|
| Tag-triggered 4-OS build | Task 16 |
| PyInstaller-driven build via existing `.spec` | Task 16 (no `.spec` changes needed) |
| `_version.py` written from tag at CI time | Tasks 1, 16 |
| `latest.json` + `checksums.txt` published with release | Tasks 15, 16 |
| GitHub Release with `softprops/action-gh-release@v2` | Task 16 |
| In-app `UpdateClient` with version compare, asset pick, manifest fetch, download, extract | Tasks 3–7 |
| Help → Check for Updates… dialog | Task 13 |
| Banner on launch with auto-check after 2 s | Tasks 12, 14 |
| `--finish-update` entry point that skips Qt | Task 11 |
| Per-OS swap + parent-PID wait + relaunch + cleanup | Tasks 8–10 |
| `LIFEGEN_DISABLE_UPDATE_CHECK=1` honored | Task 7 (`auto_check_enabled`) |
| Disabled in non-frozen builds | Task 7 |
| Documentation of release flow | Task 17 |
| Manual end-to-end smoke checklist | Task 18 |

**No placeholders in the plan body** — every code block is complete; only `<owner>` appears as a one-time user-supplied value, called out explicitly in Task 13 Step 2 and the Prerequisites.

**Type consistency:** `UpdateClient` was originally described as a class in the spec; the implementation uses module-level functions instead (no state to carry across calls). This is a deliberate simplification — `client.is_newer`, `client.pick_asset`, `client.download`, `client.fetch_manifest`, `client.check_for_update` are all module functions, and `ui.py` / `swap.py` import them by name. There are no class-vs-function references that disagree.
