"""Sign and publish a tufup release.

Run AFTER the CI workflow has published a GitHub Release for the same tag.
Pulls the four CI artifacts down, registers them into the per-OS tufup trees,
copies the signed metadata + targets into the gh-pages worktree, and pushes.

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
    """Use the gh CLI to pull every asset from the release into ``dest``."""
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["gh", "release", "download", tag, "-D", str(dest)],
        check=True,
    )
    return sorted(dest.iterdir())


def classify(archive_name: str) -> str | None:
    for key, pattern in _ASSET_PATTERNS.items():
        if pattern in archive_name:
            return key
    return None


def _extract_archive(archive: Path, dest: Path) -> Path:
    """Extract a .zip or .tar.gz archive into dest and return the dest dir."""
    dest.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(dest)
    elif name.endswith(".tar.gz") or name.endswith(".tgz"):
        with tarfile.open(archive, "r:gz") as tf:
            tf.extractall(dest)
    else:
        raise ValueError(f"Unsupported archive format: {archive.name}")
    return dest


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


def copy_subtree_to_worktree(asset_key: str) -> None:
    """Mirror the tufup repository state into the gh-pages worktree."""
    src = repository_for(asset_key)
    dst = gh_pages_subtree_for(asset_key)
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


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
            copy_subtree_to_worktree(key)

    push_gh_pages(args.tag)
    print(f"\nPublished {args.tag} to gh-pages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
