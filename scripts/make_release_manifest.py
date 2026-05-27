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
