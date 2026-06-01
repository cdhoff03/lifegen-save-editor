"""Read/write a cat's rank across both save-format generations.

Older ClanGen and the lifegen-fullgen fork store ``status`` as a plain string
(``"warrior"``). Newer ClanGen stores it as a ``CatStatus`` dict::

    {"group_history": [{"group": "1", "rank": "warrior", "moons_as": 0},
                       {"group": "1", "rank": "leader",  "moons_as": 0}],
     "standing_history": [{"group": "1", "standing": ["member"], "near": true}]}

The *current* rank is the last ``group_history`` entry's ``rank``; the current
standing is the last ``standing_history`` entry's ``standing``. These helpers
let the rest of the app treat rank as a simple string while preserving the dict
shape on write (so editing a rank never clobbers the history a save relies on).
"""
from __future__ import annotations

import copy
from typing import Any


def rank_of(status: Any) -> str:
    """Current rank string from a status that may be a dict or a plain string."""
    if isinstance(status, dict):
        gh = status.get("group_history") or []
        if gh and isinstance(gh[-1], dict):
            return gh[-1].get("rank") or ""
        return ""
    if isinstance(status, str):
        return status
    return ""


def standing_of(status: Any) -> str:
    """Current standing (member/known/exiled/lost/…) for dict-form status, else ''."""
    if isinstance(status, dict):
        sh = status.get("standing_history") or []
        if sh and isinstance(sh[-1], dict):
            st = sh[-1].get("standing")
            if isinstance(st, list):
                return st[-1] if st else ""
            return st or ""
    return ""


def with_rank(status: Any, rank: str) -> Any:
    """Return a status value with the current rank set to ``rank``.

    Dict-form status is deep-copied and its last ``group_history`` rank updated
    (history otherwise preserved). String/absent status returns the plain string.
    """
    if isinstance(status, dict):
        new = copy.deepcopy(status)
        gh = new.get("group_history")
        if isinstance(gh, list) and gh and isinstance(gh[-1], dict):
            gh[-1]["rank"] = rank
        else:
            new["group_history"] = [{"group": "1", "rank": rank, "moons_as": 0}]
        return new
    return rank
