# GitHub Actions Release Pipeline & In-App Auto-Update — Design

**Status:** Design approved 2026-05-26. Awaiting implementation plan.

## Goals

1. Cut multi-platform releases by pushing a git tag — no manual build steps.
2. Let the running app notice newer releases and update itself with a single click, plus expose a manual "Check for Updates" entry point.
3. Stay simple enough that one developer can own it without dedicated release infrastructure.

## Non-goals (explicit YAGNI)

- Code signing (Windows EV cert, Apple Developer ID, notarization). Deferred; design accommodates adding it later without re-architecting.
- Delta / binary-diff updates. Always download the full archive.
- Release channels (stable / beta).
- Background download or scheduled checks beyond launch-time + manual.
- A persistent "skip this version" preference.
- Auto-update when running from source (`python -m lifegen_editor`).

## Decisions (recorded for plan stage)

| Decision | Choice | Rationale |
|---|---|---|
| Build targets | Windows x64, macOS arm64, macOS x64, Linux x64 | User wants all three OSes, with macOS split per arch. |
| Auto-update style | Download + relaunch | Smoother than notify-only, simpler than tufup. |
| Release trigger | Git tag push (`v*`) | Standard pattern; version derived from tag. |
| Code signing | Deferred (unsigned) | Cost / friction not justified for v1. SmartScreen / Gatekeeper warnings accepted. |
| Updater binary | The new build itself, re-executed with `--finish-update` | No second PyInstaller target; no shell scripts. |

## Architecture overview

```
   tag push v0.2.0
        │
        ▼
   GitHub Actions release.yml
        ├─ build (matrix: windows-latest, macos-13, macos-latest, ubuntu-latest)
        │     each: pip install → pyinstaller → package → upload artifact
        │
        └─ release (needs: build, on ubuntu-latest)
              download all artifacts → generate checksums.txt + latest.json
              → softprops/action-gh-release → publish Release v0.2.0

   GitHub Release v0.2.0
        ├─ lifegen-save-editor-windows-x64.zip
        ├─ lifegen-save-editor-macos-arm64.zip
        ├─ lifegen-save-editor-macos-x64.zip
        ├─ lifegen-save-editor-linux-x64.tar.gz
        ├─ checksums.txt
        └─ latest.json     ◄────── app fetches this

   Installed app
        ├─ launch  ─► UpdateClient.check() (QThread, 2 s after window shown)
        │              └─ newer? → UpdateBanner appears
        │
        ├─ Help → Check for Updates…  → CheckForUpdatesDialog
        │
        └─ user clicks "Update"
              ├─ stream-download asset to %TEMP%/lifegen-update/v0.2.0.zip
              ├─ verify sha256
              ├─ extract to %TEMP%/lifegen-update/new/
              ├─ spawn  <new exe>  --finish-update
              │                    --install-dir <current>
              │                    --staging-dir <new>
              │                    --parent-pid <pid>
              └─ sys.exit(0)

   New exe (running from %TEMP%, finish-update mode)
        1. wait for parent PID to exit (poll, max 30 s)
        2. rename install dir → install dir + ".old.<timestamp>"
        3. move staging → install dir
        4. spawn installed exe (no flag, normal startup)
        5. best-effort cleanup of .old and staging
        6. exit
```

## CI release pipeline

**File:** `.github/workflows/release.yml`

**Trigger:** `on: push: tags: ['v*']`

**Jobs:**

### `build` (matrix)

| matrix.runner | matrix.asset_key | matrix.archive_name |
|---|---|---|
| `windows-latest` | `windows-x64` | `lifegen-save-editor-windows-x64.zip` |
| `macos-13` | `macos-x64` | `lifegen-save-editor-macos-x64.zip` |
| `macos-latest` | `macos-arm64` | `lifegen-save-editor-macos-arm64.zip` |
| `ubuntu-latest` | `linux-x64` | `lifegen-save-editor-linux-x64.tar.gz` |

Steps (each):
1. `actions/checkout@v4`
2. `actions/setup-python@v5` with `python-version: '3.12'`
3. Write version into `lifegen_editor/_version.py` from the tag (`${GITHUB_REF_NAME#v}`).
4. `pip install -r requirements.txt -r packaging/requirements-build.txt`
5. `pyinstaller --clean --noconfirm packaging/lifegen-save-editor.spec`
6. Package output:
   - Windows / Linux: zip / tar.gz the `dist/lifegen-save-editor/` directory.
   - macOS: `ditto -c -k --keepParent dist/lifegen-save-editor.app <archive>` (preserves bundle metadata).
7. `actions/upload-artifact@v4` with the archive.

### `release` (depends on `build`)

Runs on `ubuntu-latest`. Steps:
1. `actions/download-artifact@v4` for all 4 artifacts.
2. Generate `checksums.txt` — `sha256sum <archive>` for each, one line each.
3. Generate `latest.json`:
   ```json
   {
     "version": "0.2.0",
     "released_at": "2026-05-26T18:00:00Z",
     "notes_url": "https://github.com/<owner>/<repo>/releases/tag/v0.2.0",
     "assets": {
       "windows-x64": {"url": "https://github.com/.../lifegen-save-editor-windows-x64.zip", "sha256": "..."},
       "macos-arm64": {"url": "...", "sha256": "..."},
       "macos-x64":   {"url": "...", "sha256": "..."},
       "linux-x64":   {"url": "...", "sha256": "..."}
     }
   }
   ```
4. `softprops/action-gh-release@v2` — body auto-generated from commits since prior tag; attaches all 6 files.

**Version source of truth:** the git tag (`v0.2.0` → version `0.2.0`). The CI writes it to `lifegen_editor/_version.py` before PyInstaller runs so the running app knows what it is.

## In-app update client

**New package:** `lifegen_editor/updater/`

```
lifegen_editor/updater/
  __init__.py
  client.py        # version compare, manifest fetch, asset pick, download + verify
  ui.py            # UpdateBanner widget, CheckForUpdatesDialog
  swap.py          # --finish-update entry point + per-OS swap logic
  _version.py      # written at CI time; defaults to "0.0.0-dev" in repo
```

### `client.UpdateClient` (no Qt dependency)

- `current_version() -> str` — reads `lifegen_editor._version.__version__`.
- `fetch_manifest() -> dict` — `GET https://github.com/<owner>/<repo>/releases/latest/download/latest.json` (the `/latest/` redirect always points at the newest release, so the URL is stable). 10-second timeout. Raises `UpdateCheckError` on any failure.
- `pick_asset(manifest) -> dict | None` — uses `platform.system()` + `platform.machine()`:
  - `Windows` + `AMD64` → `windows-x64`
  - `Darwin` + `arm64` → `macos-arm64`
  - `Darwin` + `x86_64` → `macos-x64`
  - `Linux` + `x86_64` → `linux-x64`
  - else → `None` (manual "Check for Updates" shows "Your platform isn't supported for auto-update.")
- `is_newer(remote: str) -> bool` — semver compare, treats current `0.0.0-dev` as always older.
- `download(asset, progress_cb) -> Path` — streams to a temp file under `%TEMP%/lifegen-update/`, computes sha256 as it goes, verifies against `asset["sha256"]`. Raises on mismatch.
- `extract(archive: Path, dest: Path) -> Path` — zip on Windows/macOS, tar.gz on Linux. Returns path to the staging directory (containing the new build).

### `ui.UpdateBanner`

Thin QWidget at the top of the main window. Hidden by default. When `UpdateClient.check()` (background `QThread`) reports a newer version, it appears with:

> v0.2.0 is available. **[Update]**  [Dismiss]

- **Update** → opens modal progress dialog → `download()` → `extract()` → `swap.spawn_updater()` → `QApplication.quit()`.
- **Dismiss** → hides the banner until next launch (no persistent suppress).

### `ui.CheckForUpdatesDialog`

Opened from a new `Help → Check for Updates…` menu item. Modal. States:

- *Checking* — spinner, "Checking for updates…"
- *Up to date* — "You're on the latest version (0.2.0)."
- *Update available* — version + truncated notes from `manifest.notes_url` link, **[Update]** / **[Cancel]**.
- *Error* — error text and **[Retry]**.
- *Unsupported platform* — "Auto-update isn't available for your platform — download manually from <notes_url>."

Shares the entire `UpdateClient` path with the banner; the dialog is purely presentational.

### When auto-check runs

- Once on app launch, 2 seconds after the main window has been shown. Background thread; failures are silent in this path.
- Manual "Check for Updates" path surfaces all failures.
- No polling, no checks during running session.

### Config & disable knobs

- Repo coordinates live in a single constant `UPDATE_REPO = "<owner>/<repo>"` in `client.py`. Set once.
- `LIFEGEN_DISABLE_UPDATE_CHECK=1` environment variable disables the launch-time auto-check (used in dev, by repackagers).
- Auto-update is disabled entirely when `getattr(sys, 'frozen', False)` is `False` — running from source never triggers a swap.

## Swap & relaunch mechanism

**File:** `lifegen_editor/updater/swap.py`

The running process can't reliably overwrite its own binaries (especially on Windows). The new build, already extracted to a temp staging directory after download, is re-executed with a `--finish-update` flag. Because that copy lives outside the install directory, it can swap the install directory once the parent exits.

### Command-line contract

```
<staging>/lifegen-save-editor[.exe]
    --finish-update
    --install-dir <absolute path to current install directory>
    --staging-dir <absolute path to extracted new build>
    --parent-pid <PID of old app>
```

`__main__.py` checks for `--finish-update` before constructing the Qt application and dispatches to `swap.run_finish_update(args)` instead.

### Steps in `run_finish_update`

1. Poll the parent PID until it exits or 30 seconds elapse. (`os.kill(pid, 0)` on POSIX; `OpenProcess` + `GetExitCodeProcess` on Windows. If the timeout is hit, abort and write `update-failed.log` next to the install dir.)
2. Rename install dir → `<install dir>.old.<timestamp>`. If this fails, abort with a logged error; the old install is still intact.
3. Move the staging dir to the install dir path.
4. If step 3 fails, attempt to rename `.old` back to original (rollback) and abort.
5. Spawn the installed exe (no flag) detached:
   - Windows: `subprocess.Popen([exe], close_fds=True, creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP)`.
   - macOS: `subprocess.Popen(["open", "-a", app_path])`.
   - Linux: `subprocess.Popen([exe], start_new_session=True)`.
6. Best-effort cleanup of the `.old` directory (`shutil.rmtree`). On Windows, if any files are still locked, fall back to `MoveFileEx(..., MOVEFILE_DELAY_UNTIL_REBOOT)` so they clear on next boot.
7. Exit.

### Locating the install directory at runtime

The old app passes `--install-dir` explicitly. It derives this from `sys.executable`:
- Windows / Linux: `Path(sys.executable).parent`
- macOS: walk up from `sys.executable` to find the `.app` bundle root (`*.app`).

`sys._MEIPASS` (the PyInstaller unpacked dir for `--onefile`) is **not** used; we're on `--onedir`/`COLLECT`, so `sys.executable` is the right anchor.

### Per-OS quick reference

| | Windows | macOS | Linux |
|---|---|---|---|
| Default install location | wherever user extracted the zip | `/Applications/lifegen-save-editor.app` (typical) | wherever user extracted the tarball |
| Archive layout | full PyInstaller dir | the `.app` bundle | full PyInstaller dir |
| Parent wait | `OpenProcess` poll | `kill -0 <pid>` poll | `kill -0 <pid>` poll |
| Atomic swap | `os.rename` on directory | `os.rename` on `.app` | `os.rename` on dir |
| Relaunch | `Popen([exe], DETACHED_PROCESS)` | `Popen(["open", "-a", app_path])` | `Popen([exe], start_new_session=True)` |
| `.old` cleanup | `shutil.rmtree`, fall back to `MoveFileEx DELAY_UNTIL_REBOOT` | `shutil.rmtree` | `shutil.rmtree` |

## Failure handling summary

| Failure | Result | User impact |
|---|---|---|
| Manifest fetch fails (auto-check) | Silent. Banner not shown. | None. |
| Manifest fetch fails (manual check) | Error dialog with Retry. | Visible, retryable. |
| Download fails / checksum mismatch | Temp deleted. Banner re-shown with error text. | Install untouched. |
| New exe fails to launch (spawn step) | Old app surfaces error, cleans staging. | Install untouched. |
| Swap fails before relaunch | `.old` renamed back if possible. `update-failed.log` written. New exe exits without relaunching. | Old install still works. |
| Swap fails partway (rare; e.g., process crash) | `.old` may persist. App still launches from new dir if the move completed. | At worst: leftover `.old.<timestamp>` dir; cosmetic. |
| No write permission to install dir | Rename fails; same path as "Swap fails before relaunch". | Old install still works; user informed. |

## Testing approach

**Unit-testable** (no real filesystem swap):
- `client.is_newer` — semver edge cases (pre-releases, dev versions).
- `client.pick_asset` — every OS/arch combination including unsupported ones.
- `client.download` — checksum verification (mock HTTP).
- Command-line construction for `--finish-update`.

**Integration-testable** (throwaway directory):
- Full swap path in a tmpdir on the host OS (CI matrix runs the same tests on each platform).
- Parent-PID wait with a spawned dummy process.

**Manual smoke (per release):**
- Cut a test tag, confirm CI publishes 6 assets.
- Install the previous version, run `--finish-update` against the new staging dir, confirm relaunch.

## Open questions / future work

- **Code signing.** When budget allows: add Apple Developer ID + notarization on the macOS jobs, and a Windows code-signing step (EV cert for SmartScreen removal). No design changes needed; only new CI steps and possibly stripping `com.apple.quarantine` after swap on macOS.
- **Universal2 macOS build.** Could collapse the two macOS jobs into one once `target_arch='universal2'` is set in the spec; defer until Intel Mac usage data justifies it.
- **Self-update of the updater itself.** Not a separate concern: because the new build *is* the updater, every release ships the latest swap logic.
- **Install paths on Linux.** First release ships a portable tarball; if users complain we can add a `.deb` / AppImage later.
