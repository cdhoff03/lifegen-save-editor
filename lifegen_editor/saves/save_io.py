"""Read / write ClanGen / LifeGen clan save files.

Each clan lives in ``<save_root>/<clanname>/`` with at least
``clan_cats.json``. Cats are stored as a JSON list of dicts; we never touch
non-appearance fields when writing.
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

CLAN_CATS_FILENAME = "clan_cats.json"


@dataclass
class SaveCat:
    """Lightweight reference to a cat inside a clan_cats.json file."""

    index: int
    raw: dict

    @property
    def cat_id(self) -> str:
        return str(self.raw.get("ID") or self.raw.get("id") or f"#{self.index}")

    @property
    def display_name(self) -> str:
        prefix = self.raw.get("name_prefix") or self.raw.get("prefix") or ""
        suffix = self.raw.get("name_suffix") or self.raw.get("suffix") or ""
        full = (str(prefix) + str(suffix)).strip()
        if not full:
            full = self.raw.get("name") or self.cat_id
        status = self.raw.get("status") or ""
        if status:
            return f"{full} ({status})"
        return full


@dataclass
class Clan:
    name: str
    path: Path
    cats: list[SaveCat]

    @property
    def clan_cats_path(self) -> Path:
        return self.path / CLAN_CATS_FILENAME


def list_clans(save_root: Path) -> list[Path]:
    """Return clan-directory paths under ``save_root`` (anything with a clan_cats.json)."""
    if not save_root.is_dir():
        return []
    out = []
    for child in sorted(save_root.iterdir()):
        if child.is_dir() and (child / CLAN_CATS_FILENAME).is_file():
            out.append(child)
    return out


def load_clan(clan_path: Path) -> Clan:
    """Load a clan from its directory."""
    cats_file = clan_path / CLAN_CATS_FILENAME
    with cats_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"{cats_file}: expected a JSON list of cats, got {type(data).__name__}")
    cats = [SaveCat(index=i, raw=raw) for i, raw in enumerate(data)]
    return Clan(name=clan_path.name, path=clan_path, cats=cats)


def write_clan_with_backup(clan: Clan, *, backup_suffix: Optional[str] = None) -> Path:
    """Persist updated cat data atomically and create a timestamped backup of the
    previous ``clan_cats.json``. Returns the backup path."""
    cats_file = clan.clan_cats_path
    suffix = backup_suffix or time.strftime(".bak-%Y%m%d-%H%M%S")
    backup = cats_file.with_suffix(cats_file.suffix + suffix)
    if cats_file.exists():
        shutil.copy2(cats_file, backup)

    payload = [c.raw for c in clan.cats]
    tmp = cats_file.with_suffix(cats_file.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(cats_file)
    return backup
