"""Detect whether a loaded clan is a ClanGen or LifeGen save.

The two games share most of the ``clan_cats.json`` schema but diverge in ways
that matter for editing: LifeGen renames ``medicine cat`` → ``healer``, adds a
``queen`` career track, and stores LifeGen-only fields (``faith``, ``courage``,
the worn/owned ``accessories``/``inventory`` split, Dark-Forest training, …).

We sniff the loaded cats once and adapt the UI's option lists so the user only
ever sees values valid for their game (see :mod:`lifegen_editor.ui.options`).
"""
from __future__ import annotations

from enum import Enum

from .catstatus import rank_of


class GameVariant(Enum):
    """Which game produced a save."""

    CLANGEN = "clangen"
    LIFEGEN = "lifegen"

    @property
    def is_lifegen(self) -> bool:
        return self is GameVariant.LIFEGEN


# Top-level cat keys that only LifeGen ever writes. Presence of any one of these
# on any cat is a strong signal the whole save is LifeGen. ``get_save_dict`` in
# LifeGen always emits these, so even a single living cat reveals the variant.
_LIFEGEN_KEYS = (
    "faith",
    "no_faith",
    "lock_faith",
    "courage",
    "compassion",
    "intelligence",
    "empathy",
    "df_mentor",
    "df_apprentices",
    "revives",
    "accessories",
    "inventory",
    "connected_dialogue",
    "did_activity",
    "backstory_str",
)

# Ranks that exist only in LifeGen's vocabulary (the queen career track).
# Both games use "medicine cat"; detection leans mainly on the keys above.
_LIFEGEN_STATUSES = {
    "queen",
    "queen's apprentice",
}


def detect_variant(clan) -> GameVariant:
    """Return the :class:`GameVariant` of a loaded ``Clan``.

    Votes across every cat: any LifeGen-only key or status → LIFEGEN. An empty
    or all-ClanGen clan defaults to CLANGEN. Tolerant of malformed cats.
    """
    cats = getattr(clan, "cats", None) or []
    for cat in cats:
        raw = getattr(cat, "raw", None)
        if not isinstance(raw, dict):
            continue
        if any(k in raw for k in _LIFEGEN_KEYS):
            return GameVariant.LIFEGEN
        if rank_of(raw.get("status")).strip().lower() in _LIFEGEN_STATUSES:
            return GameVariant.LIFEGEN
    return GameVariant.CLANGEN
