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
        # status may be a plain string (older saves) or a CatStatus dict (newer
        # ClanGen) — pull just the current rank either way.
        from .catstatus import rank_of
        status = rank_of(self.raw.get("status"))
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


def atomic_write_json(
    path: Path, payload, *, backup_suffix: Optional[str] = None
) -> Optional[Path]:
    """Write ``payload`` to ``path`` as indent=2 JSON, atomically.

    If ``path`` already exists, a timestamped ``.bak-*`` copy is made first.
    Parent directories are created as needed. The write itself is atomic
    (temp file in the same directory, then ``replace``). Returns the backup
    path, or ``None`` if there was no prior file to back up.

    This is the single safety primitive every save-writer in the app reuses,
    so conditions/relationships/clan.json get the same guarantee as
    ``clan_cats.json``.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = backup_suffix or time.strftime(".bak-%Y%m%d-%H%M%S")
    backup: Optional[Path] = None
    if path.exists():
        backup = path.with_suffix(path.suffix + suffix)
        shutil.copy2(path, backup)

    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    tmp.replace(path)
    return backup


def write_clan_with_backup(clan: Clan, *, backup_suffix: Optional[str] = None) -> Optional[Path]:
    """Persist updated cat data atomically and create a timestamped backup of the
    previous ``clan_cats.json``. Returns the backup path (None if first write)."""
    payload = [c.raw for c in clan.cats]
    return atomic_write_json(clan.clan_cats_path, payload, backup_suffix=backup_suffix)
