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


def _unwrap_standing(entry: Any) -> str:
    """A standing entry is usually a string; LifeGen stores shunned as a
    nested ``["shunned", moon]`` list."""
    if isinstance(entry, list):
        return str(entry[0]) if entry else ""
    return str(entry or "")


def standing_of(status: Any) -> str:
    """Current standing (member/known/exiled/lost/…) for dict-form status, else ''."""
    if isinstance(status, dict):
        sh = status.get("standing_history") or []
        if sh and isinstance(sh[-1], dict):
            st = sh[-1].get("standing")
            if isinstance(st, list):
                return _unwrap_standing(st[-1]) if st else ""
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
            new["group_history"] = [{"group": PLAYER_CLAN, "rank": rank, "moons_as": 0}]
        return new
    return rank


# =============================================================================
# Dict-form life/death/outsider state (ClanGen v0.13 / LifeGen v0.7.7+).
#
# In the new schema the cat dict has no dead/df/outside/exiled keys — all of it
# is derived from group_history / standing_history. The readers below derive
# those flags; the writers return a NEW status dict using the same append-only
# transforms as the game's ``Status._modify_group``/``add_to_group`` (history
# is never rewritten, so the game's own bookkeeping stays consistent).
# =============================================================================

# Fixed group IDs shared by both games (scripts/cat/enums.py CatGroup).
PLAYER_CLAN = "1"
STARCLAN = "2"
UNKNOWN_RESIDENCE = "3"
DARK_FOREST = "4"
LONER_GROUP = "6"  # LifeGen-only outsider group
AFTERLIFE_GROUPS = frozenset({STARCLAN, UNKNOWN_RESIDENCE, DARK_FOREST})
_OUTSIDER_RANKS = {"loner", "rogue", "kittypet"}


def _group_history(status: Any) -> list:
    if isinstance(status, dict):
        gh = status.get("group_history")
        if isinstance(gh, list):
            return [e for e in gh if isinstance(e, dict)]
    return []


def current_group(status: Any) -> Any:
    """Current group id string, or None (ClanGen outsiders / no history)."""
    gh = _group_history(status)
    return gh[-1].get("group") if gh else None


def is_dead(status: Any) -> bool:
    return current_group(status) in AFTERLIFE_GROUPS


def is_df(status: Any) -> bool:
    return current_group(status) == DARK_FOREST


def dead_moons_of(status: Any) -> int:
    """Total moons spent dead — sum of moons_as over afterlife entries
    (mirrors the game's ``Cat.dead_for``)."""
    return sum(
        int(e.get("moons_as") or 0)
        for e in _group_history(status)
        if e.get("group") in AFTERLIFE_GROUPS
    )


def is_outside(status: Any) -> bool:
    """Alive but not in the player clan (ClanGen: group None; LifeGen: groups 5-7)."""
    group = current_group(status)
    return group != PLAYER_CLAN and group not in AFTERLIFE_GROUPS


def _standing_record(status: Any, group: str) -> Any:
    if isinstance(status, dict):
        for record in status.get("standing_history") or []:
            if isinstance(record, dict) and record.get("group") == group:
                return record
    return None


def is_exiled(status: Any) -> bool:
    """Exiled from the player clan: the group-1 standing record ends 'exiled'."""
    record = _standing_record(status, PLAYER_CLAN)
    if record and isinstance(record.get("standing"), list) and record["standing"]:
        return _unwrap_standing(record["standing"][-1]) == "exiled"
    return False


def _append_standing(status: dict, group: str, standing: str) -> None:
    """In-place mirror of the game's ``Status.change_standing``."""
    record = _standing_record(status, group)
    if record is not None:
        standings = record.setdefault("standing", [])
        if standings.count(standing) > 1:
            standings.remove(standing)
        standings.append(standing)
        return
    status.setdefault("standing_history", []).append(
        {"group": group, "standing": [standing], "near": True}
    )


def _move_to_group(status: Any, new_group, new_rank: str = None,
                   past_standing: str = "known") -> dict:
    """Return a new status dict with the cat moved to ``new_group``.

    Mirrors ``Status._modify_group``: append ``past_standing`` to the old
    group's record, append the new group_history entry (rank preserved unless
    overridden), append 'member' standing for the new group.
    """
    new = copy.deepcopy(status) if isinstance(status, dict) else {}
    gh = new.setdefault("group_history", [])
    old_group = gh[-1].get("group") if gh else None
    rank = new_rank or (gh[-1].get("rank") if gh else "") or "warrior"
    if old_group is not None and past_standing:
        _append_standing(new, old_group, past_standing)
    gh.append({"group": new_group, "rank": rank, "moons_as": 0})
    if new_group is not None:
        _append_standing(new, new_group, "member")
    return new


def kill(status: Any, df: bool = False) -> dict:
    """Send the cat to the appropriate afterlife (game default: Dark Forest if
    flagged, unknown residence for outsiders, else StarClan)."""
    if df:
        target = DARK_FOREST
    elif is_outside(status):
        target = UNKNOWN_RESIDENCE
    else:
        target = STARCLAN
    return _move_to_group(status, target)


def revive(status: Any) -> dict:
    """Bring a dead cat back to its last living group (player clan if none),
    keeping its rank — mirrors the game's ``Cat.revive``."""
    last_living = None
    for entry in reversed(_group_history(status)):
        if entry.get("group") not in AFTERLIFE_GROUPS:
            last_living = entry.get("group")
            break
    return _move_to_group(status, last_living or PLAYER_CLAN)


def with_dead_moons(status: Any, moons: int) -> dict:
    """Return a status dict whose afterlife time sums to ``moons`` (adjusts the
    last afterlife entry, leaving earlier history untouched)."""
    new = copy.deepcopy(status) if isinstance(status, dict) else {}
    gh = [e for e in new.get("group_history") or [] if isinstance(e, dict)]
    afterlife = [e for e in gh if e.get("group") in AFTERLIFE_GROUPS]
    if afterlife:
        others = sum(int(e.get("moons_as") or 0) for e in afterlife[:-1])
        afterlife[-1]["moons_as"] = max(0, int(moons) - others)
    return new


def set_exiled(status: Any, exiled: bool) -> dict:
    """Exile mirrors the game's ``exile_from_group``: the cat leaves the player
    clan (group None, rank loner) with 'exiled' standing. Un-exile returns the
    cat to the player clan keeping its rank."""
    if exiled:
        return _move_to_group(status, None, new_rank="loner", past_standing="exiled")
    return _move_to_group(status, PLAYER_CLAN)


def set_outside(status: Any, outside: bool, lifegen: bool) -> dict:
    """Move the cat out of (or back into) the player clan.

    ponytail: outgoing cats always become loners; the game re-derives fancier
    social ranks itself when it next touches the cat.
    """
    if outside:
        rank = rank_of(status)
        new_rank = rank if rank in _OUTSIDER_RANKS else "loner"
        return _move_to_group(status, LONER_GROUP if lifegen else None, new_rank)
    return _move_to_group(status, PLAYER_CLAN)
