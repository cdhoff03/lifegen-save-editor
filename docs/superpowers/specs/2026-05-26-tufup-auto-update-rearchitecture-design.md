# Tufup Auto-Update Re-architecture — Design

**Status:** Design approved 2026-05-26. Supersedes `2026-05-26-github-actions-release-and-autoupdate-design.md` for the in-app update mechanism. The GitHub Actions release pipeline portion of that prior spec stays in effect.

## Why we're re-architecting

The custom updater in v0.1.0 / v0.2.0 hung indefinitely on Windows during the post-download phase (UI froze at "Launching updater…"), and the macOS path had its own failure mode. Two iterations on the same self-swap design (download → extract → spawn-helper → swap) didn't converge on a reliable solution. The root issue is that **self-replacing a PyInstaller `--onedir` install while it's running is inherently fragile** on Windows: AV interception, file locks on running binaries, no UAC elevation, and no useful feedback when the spawned helper exits silently.

Rather than continue debugging custom code, we adopt [`tufup`](https://github.com/dennisvang/tufup) — the actively-maintained successor to PyUpdater. Key advantages for our case:

- **Windows install via `robocopy` in a self-deleting batch script.** This is the standard Windows pattern for replacing a running install; far more robust than the Python-level approach we had.
- **macOS install via `shutil.copytree`.** Generic, but works correctly for our `.app` bundle since it's just a directory tree.
- **Signed metadata (TUF).** Trust is established by a single embedded `root.json`; subsequent metadata is verified against it.
- **Delta patches.** Updates after the first one are smaller.
- **Battle-tested.** It's not magic — tufup still does download → extract → swap → relaunch — but the swap step is the part that broke for us, and tufup's swap is the part most worth replacing.

## Goals

1. Replace our custom updater with `tufup` for the in-app update flow.
2. Keep our existing GitHub Actions release workflow as the durable artifact + backup distribution channel.
3. Host tufup metadata + bundles on **GitHub Pages** in this repo's `gh-pages` branch.
4. Keep all private signing keys on the developer machine. No keys in CI, no keys in GitHub Secrets.
5. Preserve the existing UI (banner + Help → Check for Updates… dialog).

## Non-goals (explicit YAGNI)

- Automating the signing step into CI. Manual local signing for v1.
- Code signing (SmartScreen, Gatekeeper, notarization). Still deferred.
- Migrating existing v0.1.0 / v0.2.0 installs. Those users do one manual install of the first tufup-based release, then they're back on auto-update.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Updater library | `tufup` | Active fork of PyUpdater; robocopy on Windows is the right answer. |
| Hosting | GitHub Pages (`gh-pages` branch of this repo) | Free, static, fits tufup's URL layout, no extra service. |
| Key storage | Local developer machine, backed up out-of-band (1Password etc.) | Personal project; CI signing is overkill and worse for security. |
| Signing trigger | Manual local script after each CI release | No keys in CI; ~30 s of friction per release. |
| First tufup-based version | `v1.0.0` (skip ahead) | Marks the architectural reset; signals to existing installs that they need a manual reinstall. |

## Architecture

```
   tag push v1.0.0
        │
        ▼
   GitHub Actions release.yml  (unchanged trigger; existing matrix)
        ├─ 4 builds: win/macos-arm64/macos-x64/linux
        └─ publishes GitHub Release with archives

   ──── manual step ────────────────────────────────────────────────
   developer runs locally:  python scripts/sign_release.py v1.0.0
        ├─ gh release download v1.0.0 -D /tmp/lg-1.0.0/
        ├─ tufup targets add 1.0.0 <archive> ~/.lifegen-release/keystore
        │    (creates patches from prior version where applicable;
        │     signs targets, snapshot, timestamp metadata)
        └─ git -C gh-pages-worktree commit && push

   GitHub Pages serves the gh-pages branch at:
        https://cdhoff03.github.io/lifegen-save-editor/
        └─ <asset_key>/   (one subtree per OS+arch: windows-x64,
            ├─ metadata/   macos-arm64, macos-x64, linux-x64)
            │   ├─ 1.root.json
            │   ├─ targets.json
            │   ├─ snapshot.json
            │   └─ timestamp.json
            └─ targets/
                ├─ lifegen-save-editor-1.0.0.tar.gz
                ├─ lifegen-save-editor-1.1.0.tar.gz
                └─ lifegen-save-editor-1.0.0-to-1.1.0.patch
   ──── ────────────────────────────────────────────────────────────

   Installed app
        ├─ launch → tufup.Client.check_for_updates() (background thread)
        │            └─ uses embedded root.json as the trust anchor;
        │               fetches signed metadata; compares versions
        ├─ banner / Help dialog shows the update
        └─ user clicks Update
              ├─ tufup downloads the patch (or full archive)
              ├─ verifies hashes against signed targets metadata
              ├─ extracts to a temp dir
              ├─ spawns the platform install script
              │    Windows: robocopy .bat (self-deletes when done)
              │    macOS:   shutil.copytree of the .app contents
              └─ current process exits; install script swaps + relaunches
```

## Components

### Removed

| Path | Reason |
|---|---|
| `lifegen_editor/updater/client.py` | Replaced by tufup wrapper. |
| `lifegen_editor/updater/swap.py` | Replaced by tufup's install scripts. |
| `--finish-update` dispatch in `lifegen_editor/__main__.py` | No longer needed; tufup spawns its own install script. |
| `scripts/make_release_manifest.py` | Replaced by tufup metadata. |
| `latest.json` step in `.github/workflows/release.yml` | Same. |

### Kept (with tweaks)

| Path | Tweak |
|---|---|
| `lifegen_editor/updater/ui.py` | Banner + dialog stay. `_DownloadExtractWorker` is deleted; the worker now just calls into the new tufup wrapper. |
| `lifegen_editor/_version.py` | Unchanged — still source of truth. CI still writes it from the tag. |
| `lifegen_editor/__main__.py` | Strip the `--finish-update` branch. |
| `.github/workflows/release.yml` | Remove the `release` job's "generate latest.json" step. Keep everything else. |
| `packaging/lifegen-save-editor.spec` | Add `assets/tufup/root.json` to `datas`. |
| `requirements.txt` | Add `tufup`. |

### New

| Path | Responsibility |
|---|---|
| `lifegen_editor/updater/tufup_client.py` | Thin wrapper around `tufup.client.Client`: factory, `check_for_update()`, `perform_update(progress_cb)`. ~70 lines. |
| `assets/tufup/root.json` | Public trust anchor metadata. Checked into the repo. Embedded into the frozen build. |
| `scripts/tufup_init.py` | One-time setup. Generates Ed25519 keys + initial metadata. Writes keystore to `~/.lifegen-release/keystore/` and repository to `~/.lifegen-release/repository/`. ~40 lines. |
| `scripts/sign_release.py` | Per-release. Downloads CI artifacts, runs `tufup targets add`, copies metadata + targets into the `gh-pages` worktree, commits + pushes. ~80 lines. |
| `scripts/tufup_settings.py` | Shared constants: APP_NAME, METADATA_BASE_URL, TARGET_BASE_URL, paths to local keystore + repository. |

## Key management

**One-time, on developer machine:**

```bash
# Install build deps
.venv/bin/pip install -r packaging/requirements-build.txt   # tufup is added here

# Generate keys + initial metadata
.venv/bin/python scripts/tufup_init.py
```

Outputs (per OS+arch — four trees total, see Hosting layout):
- `~/.lifegen-release/keystore/<asset_key>/` — 4 Ed25519 private keys per tree (root, targets, snapshot, timestamp). With 4 trees that's 16 keys total. **Never commit. Back up the entire `~/.lifegen-release/keystore/` directory out-of-band.**
- `~/.lifegen-release/repository-<asset_key>/metadata/1.root.json` — initial root metadata for that tree.

After init, copy the four public root files into the source tree:

```bash
for key in windows-x64 macos-arm64 macos-x64 linux-x64; do
    mkdir -p assets/tufup/$key
    cp ~/.lifegen-release/repository-$key/metadata/1.root.json assets/tufup/$key/1.root.json
done
git add assets/tufup/
git commit -m "feat(updater): embed initial tufup root metadata for all platforms"
```

Each `assets/tufup/<asset_key>/1.root.json` is the **trust anchor for that platform tree**: every running client verifies all other metadata against the bundled root for its own OS+arch. If you ever need to rotate root keys, the bootstrap requires manually distributing new `root.json` files (or a chain of root rotations the existing clients can verify). For v1, plan for no rotations.

**`.gitignore` additions:**

```
keystore/
```

## Hosting layout (GitHub Pages)

A new branch `gh-pages` is created once. Because we run **one tufup repo per OS+arch** (see Release flow), the branch holds four parallel tufup trees:

```
gh-pages/
├── windows-x64/
│   ├── metadata/    (1.root.json, targets.json, snapshot.json, timestamp.json)
│   └── targets/     (lifegen-save-editor-<ver>.tar.gz, patches)
├── macos-arm64/
│   ├── metadata/
│   └── targets/
├── macos-x64/
│   ├── metadata/
│   └── targets/
└── linux-x64/
    ├── metadata/
    └── targets/
```

GitHub Pages is enabled in repo Settings → Pages: Source = `gh-pages` branch, `/` (root). The site is served at `https://cdhoff03.github.io/lifegen-save-editor/`.

Developer setup (one time):

```bash
# In the main repo
git checkout --orphan gh-pages
git rm -rf .
echo "lifegen-save-editor TUF repository" > README.md
git add README.md
git commit -m "init gh-pages"
git push -u origin gh-pages
git checkout main

# Add a worktree for the publish workflow
git worktree add ../lifegen-gh-pages gh-pages
```

`scripts/sign_release.py` later writes into `../lifegen-gh-pages/` and pushes.

## Release flow

### CI half (unchanged trigger, slightly simplified)

`.github/workflows/release.yml` still fires on `v*` tags, still builds the 4-OS matrix, still publishes a GitHub Release with the archives. We **remove** the manifest-generation step and the `latest.json`/`checksums.txt` upload (tufup metadata is the source of truth now). Everything else stays.

### Manual sign half (new, ~30 seconds)

```bash
.venv/bin/python scripts/sign_release.py v1.1.0
```

The script:

1. `gh release download v1.1.0 -D /tmp/lg-1.1.0/`
2. For the **single archive** that matches the user's current platform expectation — actually no: tufup expects ONE archive per release, treated as the canonical bundle. We need to decide what tufup's `archive` is.

   **Resolution:** tufup is designed for one archive per release. But we ship four (per-OS). The cleanest mapping is **one tufup repo per OS+arch**, so we'd have four separate metadata trees. That's a lot. The alternative is **one tufup repo using a single canonical archive** and an OS-specific selector inside the install script.

   For v1 we go with: **tufup repo per OS+arch.** Four parallel trees under `gh-pages/<asset_key>/`. The client picks its tree at startup based on platform. This is simple and matches tufup's mental model exactly — each tree only ever cares about one bundle line.

3. The script iterates the 4 archives, for each one:
   - `tufup targets add 1.1.0 /tmp/lg-1.1.0/<archive> ~/.lifegen-release/keystore/<asset_key>` (per-tree keystore)
4. Copies `~/.lifegen-release/repository-<asset_key>/*` into `../lifegen-gh-pages/<asset_key>/`.
5. `git -C ../lifegen-gh-pages add -A && git commit -m "release v1.1.0" && git push`.

**Note on per-tree keystore:** Section B above implied a single keystore, but with one repo per OS+arch we need keys per repo. We'll generate four sub-keystores under `~/.lifegen-release/keystore/<asset_key>/` during init. The four `root.json` files (one per OS+arch) all get embedded; the client picks the right one at runtime.

This adds modest complexity to the init script but keeps each TUF repo self-contained and matches tufup's expectations.

## Client integration

### `lifegen_editor/updater/tufup_client.py`

```python
"""tufup-based auto-update client. Replaces the old client.py + swap.py."""
from __future__ import annotations

import importlib.resources
import platform
import sys
from pathlib import Path
from typing import Callable

from platformdirs import user_data_dir
from tufup.client import Client

APP_NAME = "lifegen-save-editor"
PAGES_BASE = "https://cdhoff03.github.io/lifegen-save-editor"

# OS+arch → asset_key matches the asset_key used in CI matrix and in
# the per-tree gh-pages layout.
def _asset_key() -> str | None:
    system, machine = platform.system(), platform.machine()
    if system == "Windows":              return "windows-x64"
    if system == "Darwin" and machine == "arm64":  return "macos-arm64"
    if system == "Darwin" and machine == "x86_64": return "macos-x64"
    if system == "Linux" and machine == "x86_64":  return "linux-x64"
    return None


def _install_dir() -> Path:
    exe = Path(sys.executable).resolve()
    if sys.platform == "darwin":
        for p in [exe, *exe.parents]:
            if p.suffix == ".app":
                return p
        raise RuntimeError(f"could not locate .app bundle from {exe}")
    return exe.parent


def _seed_root_if_missing(metadata_dir: Path, asset_key: str) -> None:
    root_dst = metadata_dir / "root.json"
    if root_dst.exists():
        return
    bundled_root = (
        importlib.resources.files("lifegen_editor")
        .joinpath(f"../assets/tufup/{asset_key}/1.root.json")
    )
    with bundled_root.open("rb") as src:
        root_dst.write_bytes(src.read())


def _make_client() -> Client | None:
    key = _asset_key()
    if key is None:
        return None
    data_dir = Path(user_data_dir(APP_NAME))
    metadata_dir = data_dir / "metadata"
    target_dir = data_dir / "downloads"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    _seed_root_if_missing(metadata_dir, key)

    from lifegen_editor import __version__

    return Client(
        app_name=APP_NAME,
        app_install_dir=_install_dir(),
        current_version=__version__,
        metadata_dir=metadata_dir,
        metadata_base_url=f"{PAGES_BASE}/{key}/metadata/",
        target_dir=target_dir,
        target_base_url=f"{PAGES_BASE}/{key}/targets/",
        refresh_required=False,
    )


def check_for_update():
    """Returns a tufup TargetMeta-equivalent if a newer version exists, else None.

    Raises RuntimeError on network / signature failure.
    """
    client = _make_client()
    if client is None:
        return None
    return client.check_for_updates()


def perform_update(progress_cb: Callable[[int, int], None]) -> None:
    """Downloads + verifies + applies the update.

    On success this spawns the install script and exits the current process.
    Does NOT return on the happy path.
    """
    client = _make_client()
    if client is None:
        raise RuntimeError("Auto-update unavailable on this platform")
    client.download_and_apply_update(progress_hook=progress_cb)
```

### `ui.py` updates

- `_CheckWorker.run()` calls `tufup_client.check_for_update()`. The "asset" concept disappears — tufup yields a single `TargetMeta` per platform tree.
- `_DownloadExtractWorker` is **deleted**.
- `run_download_and_swap(parent, manifest, asset)` becomes `run_update(parent, target_meta)`:
  - Shows the progress dialog
  - Spawns a small worker that calls `tufup_client.perform_update(progress_cb)`
  - Worker reports percentage via `progress_cb` → `QProgressBar`
  - Tufup spawns the install script and exits the process — the dialog disappears with everything else, the install script does its work, the new app launches
- The banner UI stays the same; only the data shape feeding it changes (`version: str` instead of a manifest dict).

### `__main__.py` simplification

The `--finish-update` branch is deleted. The Qt-imports stay lazy (the Task 11 improvement remains correct for selftest mode).

```python
def main() -> int:
    if os.environ.get("LIFEGEN_EDITOR_SELFTEST") == "1":
        return _selftest()
    from lifegen_editor.ui.main_window import run
    return run()
```

## Migration & failure modes

### Existing v0.1.0 / v0.2.0 installs

Those clients are pointed at `https://github.com/cdhoff03/lifegen-save-editor/releases/latest/download/latest.json`. After the cutover, the CI workflow no longer generates `latest.json` (we remove the step), so the URL returns 404. Existing clients will see "Could not check for updates" if they open `Help → Check for Updates…`, and the launch-time auto-check fails silently. Users have to manually download v1.0.0 from the GitHub release page (one time) and install. After that, tufup takes over.

A README note on this is added in the implementation plan.

### Failure handling

| Failure | Behavior |
|---|---|
| GitHub Pages temporarily unreachable | tufup raises; auto-check is silent; manual check shows error + Retry |
| Metadata tampered | TUF signature verification fails; client refuses update; logs to tufup's error stream |
| Robocopy (Windows) fails mid-swap | tufup's install script logs to `%TEMP%/tufup-install-*.log`; partial state means existing files are intact (robocopy overwrites per-file) and the app may need a manual reinstall to recover |
| `shutil.copytree` (macOS/Linux) fails | tufup keeps the old install intact unless `purge_dst_dir=True`. We will use `purge_dst_dir=False` for v1 to maximize safety, accepting that stale files from old versions may accumulate. |
| Local TUF metadata cache corrupt | Delete `~/.local/share/lifegen-save-editor/metadata/` → re-seeded from bundled root on next launch |
| Lost private keystore | No future signed releases. Recovery requires fresh key generation + a new embedded `root.json` + a manual install of the new client by every user. v1 plan: keep the keystore backed up and avoid this. |

### What we lose vs. our custom code

- No more `update-failed.log` next to the install dir on failure. Tufup logs to `%TEMP%` instead.
- No more silent rollback on failed swap. Tufup tries hard but doesn't promise full atomicity.

These are acceptable trade-offs for getting a working updater.

## Open questions / future work

- **Automate signing in CI** with secrets once the manual flow is proven stable. Requires careful key-role separation (snapshot/timestamp can be online; root/targets stay offline).
- **Code signing** (SmartScreen / Gatekeeper) — same future-work item as before.
- **Single canonical archive instead of per-OS trees.** Would require platform selection logic inside the install script. Defer.
- **Delta patch size.** First few releases will be full archives; tufup auto-generates patches between consecutive versions. Worth measuring after a few releases.
