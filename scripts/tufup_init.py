"""One-time setup: generate per-OS+arch TUF repositories.

Each OS+arch tree is an independent TUF repository. We generate four sets of
keys (root, targets, snapshot, timestamp) per tree, and write the initial
metadata that the client will pin via `1.root.json`.

Run once on the developer's machine. After this completes, copy each tree's
public `1.root.json` into `assets/tufup/<asset_key>/` and commit. Back up the
ENTIRE ~/.lifegen-release/keystore/ directory out-of-band — losing it means
no future signed releases.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tufup.repo import Repository
from scripts.tufup_settings import (
    APP_NAME,
    ASSET_KEYS,
    keystore_for,
    repository_for,
)


KEY_MAP = {
    "root":      ["root_key"],
    "targets":   ["targets_key"],
    "snapshot":  ["snapshot_key"],
    "timestamp": ["timestamp_key"],
}

EXPIRATION_DAYS = {
    "root":      365 * 10,
    "targets":   365,
    "snapshot":  30,
    "timestamp": 1,
}


def init_one_tree(asset_key: str) -> None:
    keystore = keystore_for(asset_key)
    repo_dir = repository_for(asset_key)
    keystore.mkdir(parents=True, exist_ok=True)
    repo_dir.mkdir(parents=True, exist_ok=True)

    repo = Repository(
        app_name=APP_NAME,
        app_version_attr="lifegen_editor.__version__",
        repo_dir=repo_dir,
        keys_dir=keystore,
        key_map=KEY_MAP,
        expiration_days=EXPIRATION_DAYS,
        encrypted_keys=[],
        thresholds={"root": 1, "targets": 1, "snapshot": 1, "timestamp": 1},
    )
    repo.save_config()
    repo.initialize()
    print(f"OK  initialized {asset_key} → {repo_dir}")


def main() -> int:
    for key in ASSET_KEYS:
        init_one_tree(key)
    print()
    print("Initialization complete.")
    print("Next steps:")
    print(f"  1. Back up {keystore_for('windows-x64').parent} to a safe place.")
    print("  2. Copy each tree's 1.root.json into assets/tufup/<asset_key>/")
    print("     and commit. (See README.)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
