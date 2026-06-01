"""Sign and publish a tufup release.

Run AFTER the CI workflow has published a GitHub Release for the same tag.
Pulls the four CI artifacts down, registers them into the per-OS tufup trees,
uploads the resulting signed bundles to the GitHub Release as additional
assets (with asset_key suffixes to disambiguate per-OS bundles), and copies
ONLY the metadata (no targets/) into the gh-pages worktree.

Why the split: GitHub's 100 MB per-file limit blocks the Linux bundle from
going on gh-pages directly. GitHub Releases allow up to 2 GB per asset, so
the .tar.gz bundles live there. Metadata is tiny (<1 MB total) and goes on
gh-pages where the client fetches it. The client's tufup wrapper (see
lifegen_editor/updater/tufup_client.py) overrides download_target to know
about this URL scheme.

Prerequisites:
  - ~/.lifegen-release/keystore/<asset_key>/ exists with valid keys
  - ~/lifegen-gh-pages/ is a worktree of the gh-pages branch
  - `gh` CLI is authenticated

Usage:
  python scripts/sign_release.py v1.1.0

API notes (tufup 0.10.0):
  - Repository.from_config() takes NO arguments; it reads the config file
    (.tufup-repo-config) from the current working directory.  We chdir into
    the repo_dir before calling it.
  - Repository.add_bundle(new_bundle_dir, new_version, ...) packages the
    *directory* at new_bundle_dir into a .tar.gz and registers it.  The CI
    archives are therefore extracted into a temp directory first.
  - Repository.publish_changes(private_key_dirs=[...]) signature is unchanged.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tufup.repo import Repository

from lifegen_editor.updater.tufup_client import APP_NAME, suffix_filename_with_asset_key
from scripts.tufup_settings import (
    ASSET_KEYS,
    GH_PAGES_WORKTREE,
    gh_pages_subtree_for,
    keystore_for,
    repository_for,
)

# Maps an asset_key to the substring it must contain in the archive filename.
# Archive filenames produced by CI: lifegen-save-editor-<asset_key>.{zip,tar.gz}
_ASSET_PATTERNS = {key: key for key in ASSET_KEYS}


def gh_download(tag: str, dest: Path) -> list[Path]:
    """Pull the four CI build artifacts for ``tag`` into ``dest``.

    These are workflow artifacts (uploaded by the build matrix in
    release.yml), NOT release assets — the Release itself is intentionally
    empty when CI publishes it, and this script attaches the signed bundles
    afterward.
    """
    dest.mkdir(parents=True, exist_ok=True)
    # Find the workflow run that produced this tag. `gh run list` is
    # filtered by event=push and the tag matches GITHUB_REF_NAME.
    out = subprocess.run(
        [
            "gh", "run", "list",
            "--workflow", "release.yml",
            "--event", "push",
            "--branch", tag,
            "--limit", "1",
            "--json", "databaseId,conclusion,headBranch",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    runs = json.loads(out.stdout)
    if not runs:
        raise SystemExit(f"no completed release.yml run found for tag {tag}")
    run_id = str(runs[0]["databaseId"])
    print(f"  downloading artifacts from run {run_id}")
    subprocess.run(
        ["gh", "run", "download", run_id, "-D", str(dest)],
        check=True,
    )
    # gh run download lays out artifacts under <dest>/<artifact_name>/<files>.
    # Flatten so the rest of the script sees a directory of archives.
    flat: list[Path] = []
    for path in dest.rglob("*"):
        if path.is_file() and path.suffix in {".zip", ".gz"}:
            flat.append(path)
    return sorted(flat)


def classify(archive_name: str) -> str | None:
    for key, pattern in _ASSET_PATTERNS.items():
        if pattern in archive_name:
            return key
    return None


def _extract_archive(archive: Path, dest: Path) -> Path:
    """Extract a .zip or .tar.gz archive into dest and return the dest dir.

    macOS .app bundles depend on symlinks (e.g.
    ``QtCore.framework/QtCore -> Versions/Current/QtCore``) and on the
    executable bit of their Mach-O binaries. Python's ``zipfile`` preserves
    neither: it rewrites every symlink as a small regular file containing the
    link-target text and drops POSIX permissions. That silently corrupts the
    bundle — dyld can no longer resolve the frameworks and the embedded code
    signatures stop validating — which is exactly why such builds open as
    "is damaged and can't be opened." ``ditto`` round-trips bundles
    faithfully, so we use it for .zip whenever it is available (it always is
    on macOS, where this script runs). ``tarfile`` already preserves symlinks
    and modes, so the .tar.gz path is unchanged.
    """
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        ditto = shutil.which("ditto")
        if ditto:
            subprocess.run([ditto, "-x", "-k", str(archive), str(dest)], check=True)
        else:
            # Non-macOS fallback. Safe for the Windows bundle (no symlinks);
            # a macOS bundle extracted this way is caught by
            # _verify_macos_bundle() before it can ship.
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(dest)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(dest)
    else:
        raise ValueError(f"Unsupported archive format: {archive.name}")
    return dest


def _verify_macos_bundle(bundle_dir: Path, app_name: str = APP_NAME) -> None:
    """Fail loudly if a macOS .app bundle was corrupted during extraction.

    Guards against the classic non-symlink-aware unzip damage: framework
    symlinks flattened into regular files and the main executable stripped of
    its exec bit. Either one ships an app that opens as "damaged", so this is
    a hard release gate rather than a warning.
    """
    app = bundle_dir / f"{app_name}.app"
    if not app.is_dir():
        raise SystemExit(f"verify: bundle is missing or not a directory: {app}")

    main_exe = app / "Contents" / "MacOS" / app_name
    if not main_exe.is_file():
        raise SystemExit(f"verify: main executable missing: {main_exe}")
    if not (main_exe.stat().st_mode & 0o111):
        raise SystemExit(f"verify: main executable is not executable: {main_exe}")

    if not any(p.is_symlink() for p in app.rglob("*")):
        raise SystemExit(
            f"verify: {app} contains zero symlinks — its framework symlinks "
            "were flattened (non-symlink-aware unzip). Extract with "
            "`ditto -x -k`."
        )


def sign_one(version: str, asset_key: str, archive: Path, extract_root: Path) -> None:
    """Register a single platform archive into its tufup repo.

    The tufup API (0.10.0):
      - Repository.from_config() reads .tufup-repo-config from CWD — we
        temporarily chdir into repo_dir.
      - Repository.add_bundle(new_bundle_dir, new_version) packages the
        directory into a .tar.gz and registers it, so we extract the CI
        archive first.
    """
    repo_dir = repository_for(asset_key)
    keystore = keystore_for(asset_key)
    if not repo_dir.exists() or not keystore.exists():
        raise SystemExit(
            f"Missing local tufup state for {asset_key} — "
            f"did you run tufup_init.py? (repo={repo_dir}, keys={keystore})"
        )

    # Extract the CI archive into a temporary directory so add_bundle can
    # package it using the correct tufup naming convention.
    bundle_dir = extract_root / asset_key
    _extract_archive(archive, bundle_dir)
    if asset_key.startswith("macos"):
        _verify_macos_bundle(bundle_dir)

    # from_config() uses CWD to locate .tufup-repo-config.
    prev_cwd = Path.cwd()
    try:
        os.chdir(repo_dir)
        repo = Repository.from_config()
        repo.add_bundle(
            new_bundle_dir=bundle_dir,
            new_version=version,
        )
        repo.publish_changes(private_key_dirs=[keystore])
    finally:
        os.chdir(prev_cwd)

    print(f"OK  signed {asset_key}: {archive.name}")


def copy_metadata_to_worktree(asset_key: str) -> None:
    """Mirror only the tufup repository's metadata/ subdir into gh-pages.

    The targets/ subdir is excluded — those .tar.gz bundles are uploaded as
    GitHub Release assets instead (see upload_targets_to_release()), because
    GitHub blocks single files over 100 MB on regular repo branches.
    """
    src = repository_for(asset_key) / "metadata"
    dst = gh_pages_subtree_for(asset_key) / "metadata"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def upload_targets_to_release(tag: str, asset_key: str) -> None:
    """Upload every target file in the tufup repo for this asset_key to the
    GitHub Release for ``tag``, renaming each to include the asset_key suffix.

    Uses ``gh release upload --clobber`` so re-running the script is idempotent.
    Files are copied to a temp dir with the renamed name before uploading,
    because ``gh release upload`` uses the on-disk filename as the asset name
    (there is no #displayname rename flag).
    """
    targets_dir = repository_for(asset_key) / "targets"
    with tempfile.TemporaryDirectory(prefix="lg-upload-") as staging:
        staged_paths: list[Path] = []
        for src in sorted(targets_dir.iterdir()):
            if not src.is_file():
                continue
            renamed = suffix_filename_with_asset_key(src.name, asset_key)
            dst = Path(staging) / renamed
            shutil.copy2(src, dst)
            staged_paths.append(dst)
        if not staged_paths:
            print(f"     (no targets to upload for {asset_key})")
            return
        subprocess.run(
            ["gh", "release", "upload", tag, *[str(p) for p in staged_paths], "--clobber"],
            check=True,
        )
        for p in staged_paths:
            print(f"     uploaded {p.name}")


def push_gh_pages(tag: str) -> None:
    subprocess.run(["git", "-C", str(GH_PAGES_WORKTREE), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(GH_PAGES_WORKTREE), "commit", "-m", f"release {tag}"],
        check=True,
    )
    subprocess.run(["git", "-C", str(GH_PAGES_WORKTREE), "push"], check=True)


def main() -> int:
    p = argparse.ArgumentParser(
        description="Download, sign, and publish a tufup release."
    )
    p.add_argument("tag", help="git tag of the release, e.g. v1.0.0")
    args = p.parse_args()

    version = args.tag.lstrip("v")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        download_dir = tmp_path / "release"
        extract_root = tmp_path / "extracted"
        archives = gh_download(args.tag, download_dir)

        classified: dict[str, Path] = {}
        for archive in archives:
            key = classify(archive.name)
            if key is None:
                print(f"skipping unrecognized artifact: {archive.name}")
                continue
            classified[key] = archive

        missing = [k for k in ASSET_KEYS if k not in classified]
        if missing:
            raise SystemExit(f"missing archives for: {', '.join(missing)}")

        for key, archive in classified.items():
            sign_one(version, key, archive, extract_root)
            upload_targets_to_release(args.tag, key)
            copy_metadata_to_worktree(key)

    push_gh_pages(args.tag)
    print(f"\nPublished {args.tag}: targets on GitHub Release, metadata on gh-pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
