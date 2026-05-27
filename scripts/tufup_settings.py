"""Shared constants used by tufup_init.py, sign_release.py, and tufup_client.py.

These are the cross-cutting facts about where things live and how the tufup
repositories are laid out. Editing this file changes behavior in three places,
so be deliberate.
"""
from __future__ import annotations

from pathlib import Path

APP_NAME = "lifegen-save-editor"
GITHUB_OWNER = "cdhoff03"
GITHUB_REPO  = "lifegen-save-editor"

# Filename keys for the four CI artifacts. Order matters only for human reading.
ASSET_KEYS = ("windows-x64", "macos-arm64", "macos-x64", "linux-x64")

# Local working directories (NOT under the repo). Created by tufup_init.py.
LOCAL_ROOT  = Path.home() / ".lifegen-release"
KEYSTORE    = LOCAL_ROOT / "keystore"      # subdir per asset_key
REPOSITORY  = LOCAL_ROOT / "repository"    # subdir per asset_key

# Local clone of gh-pages branch as a git worktree. Created by hand once.
GH_PAGES_WORKTREE = Path.home() / "lifegen-gh-pages"

# Public base URL the running app reads metadata + targets from.
PAGES_BASE_URL = f"https://{GITHUB_OWNER}.github.io/{GITHUB_REPO}"


def keystore_for(asset_key: str) -> Path:
    return KEYSTORE / asset_key


def repository_for(asset_key: str) -> Path:
    return REPOSITORY / asset_key


def gh_pages_subtree_for(asset_key: str) -> Path:
    return GH_PAGES_WORKTREE / asset_key
