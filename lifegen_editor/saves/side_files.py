"""Read / write the per-cat and per-clan sidecar files that live alongside
``clan_cats.json``.

A saved clan looks like::

    <save_root>/<ClanName>/clan_cats.json
    <save_root>/<ClanName>/conditions/<catID>_conditions.json
    <save_root>/<ClanName>/relationships/<catID>_relations.json
    <save_root>/<ClanName>clan.json          # NB: sibling, beside the folder

Every writer routes through :func:`atomic_write_json` so each gets the same
timestamped-backup + atomic-rename safety as the main save.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .save_io import Clan, atomic_write_json

CONDITION_KEYS = ("illnesses", "injuries", "permanent conditions")


# --- paths --------------------------------------------------------------------
def conditions_path(clan: Clan, cat_id: str) -> Path:
    return clan.path / "conditions" / f"{cat_id}_conditions.json"


def relationships_path(clan: Clan, cat_id: str) -> Path:
    return clan.path / "relationships" / f"{cat_id}_relations.json"


def clan_json_path(clan: Clan) -> Path:
    """The clan-level file sits *beside* the clan folder, named ``<Name>clan.json``."""
    return clan.path.parent / f"{clan.name}clan.json"


# --- readers (tolerant of missing files) -------------------------------------
def load_conditions(clan: Clan, cat_id: str) -> dict:
    path = conditions_path(clan, cat_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                # normalise: ensure all three buckets exist
                for k in CONDITION_KEYS:
                    data.setdefault(k, {})
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {k: {} for k in CONDITION_KEYS}


def load_relationships(clan: Clan, cat_id: str) -> list[dict]:
    path = relationships_path(clan, cat_id)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return []


def load_clan_json(clan: Clan) -> dict:
    path = clan_json_path(clan)
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return {}


# --- writers (backup + atomic) -----------------------------------------------
def write_conditions(clan: Clan, cat_id: str, data: dict) -> Optional[Path]:
    return atomic_write_json(conditions_path(clan, cat_id), data)


def write_relationships(clan: Clan, cat_id: str, records: list[dict]) -> Optional[Path]:
    return atomic_write_json(relationships_path(clan, cat_id), records)


def write_clan_json(clan: Clan, data: dict) -> Optional[Path]:
    return atomic_write_json(clan_json_path(clan), data)


# --- resurrect support --------------------------------------------------------
# condition-bucket key -> a complete default entry so a newly-added condition
# carries every field the game's condition logic expects (it reads these with
# .get(), but we populate them to be safe and game-accurate).
def default_condition_entry(bucket: str) -> dict:
    if bucket == "injuries":
        return {
            "severity": "minor", "mortality": 0, "duration": 5, "moon_start": 0,
            "illness_infectiousness": 0, "risks": [], "complication": None,
            "cause_permanent": False, "event_triggered": False,
        }
    if bucket == "permanent conditions":
        return {
            "severity": "minor", "born_with": False, "moons_until": -2,
            "moon_start": 0, "mortality": 0, "illness_infectiousness": None,
            "risks": [], "complication": None, "event_triggered": False,
        }
    # illnesses
    return {
        "severity": "minor", "mortality": 0, "infectiousness": 0, "duration": 5,
        "moon_start": 0, "risks": [], "event_triggered": False,
    }


AFTERLIFE_ROSTERS = ("starclan_cats", "darkforest_cats", "unknown_cats")


def remove_from_afterlife(clan_json: dict, cat_id: str) -> dict:
    """Return a copy of ``clan_json`` with ``cat_id`` removed from every
    afterlife roster. Rosters may be stored as a list of IDs or as a
    comma-joined string (both shapes are seen); the original shape is kept.
    """
    out = dict(clan_json)
    for key in AFTERLIFE_ROSTERS:
        roster = out.get(key)
        if isinstance(roster, list):
            out[key] = [c for c in roster if str(c) != str(cat_id)]
        elif isinstance(roster, str) and roster:
            ids = [c for c in roster.split(",") if c and c != str(cat_id)]
            out[key] = ",".join(ids)
    return out
