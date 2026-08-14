"""Editable non-appearance ("details") fields of a save-file cat.

Where :class:`~lifegen_editor.io.cat_data.CatData` owns *appearance*, this owns
*gameplay metadata* — status, life/death, age, names, personality, skills,
faith, flags. Kept deliberately separate so the appearance preview / pcm
round-trips stay untouched.

Both ``from_save_cat`` and ``apply_to_save_cat`` are :class:`GameVariant`-aware:
LifeGen-only keys (faith, courage, …) are never written onto a ClanGen cat, and
fields whose serialization differs between forks (``facets``, ``skill_dict``,
``gender_align``) are read and re-emitted in the exact shape/key they were found.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..saves.variant import GameVariant
from ..saves import catstatus as cs
from ..saves.catstatus import rank_of, with_rank

# --- field-write policy --------------------------------------------------------
# Universal fields: valid in both games; always written.
# Present-only: written only if the source cat already had the key (don't invent
#   on saves that predate the system). Life/death flags are present-only because
#   newer ClanGen represents death/exile via standing_history, not these bools —
#   inventing them on such a save would be ignored at best, harmful at worst.
# LifeGen-only: written if present OR the save is LifeGen.
_PRESENT_ONLY = {
    "facets", "skill_dict", "backstory",
    "dead", "dead_moons", "df", "outside", "exiled", "prevent_fading",
}
_LIFEGEN_ONLY = {
    "faith", "no_faith", "lock_faith",
    "courage", "compassion", "intelligence", "empathy",
}

# LifeGen lock_faith vocabulary.
LOCK_FAITH_VALUES = ["flexible", "starclan", "dark forest", "neutral"]


def _as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass
class CatDetails:
    """Editable gameplay metadata for one save-file cat."""

    # Identity
    name_prefix: str = ""
    name_suffix: str = ""
    gender: str = ""
    gender_align: str = ""
    backstory: Optional[str] = None

    # Status / rank
    status: str = "warrior"
    experience: int = 0

    # Life & death
    moons: int = 0
    dead: bool = False
    dead_moons: int = 0
    df: bool = False
    outside: bool = False
    exiled: bool = False
    prevent_fading: bool = False

    # Personality
    trait: str = ""
    facet_lawfulness: int = 8
    facet_sociability: int = 8
    facet_aggression: int = 8
    facet_stability: int = 8

    # Skills (LifeGen skill_dict shape: "PATH,points,interest_only")
    skill_primary_path: Optional[str] = None
    skill_primary_points: int = 0
    skill_secondary_path: Optional[str] = None
    skill_secondary_points: int = 0

    # Faith (LifeGen-only)
    faith: int = 0
    no_faith: bool = False
    lock_faith: str = "flexible"

    # Behaviour flags
    no_kits: bool = False
    no_mates: bool = False
    no_retire: bool = False
    favourite: bool = False

    # LifeGen player-cat stats
    courage: int = 0
    compassion: int = 0
    intelligence: int = 0
    empathy: int = 0

    # bookkeeping — which save keys actually existed in the source dict, plus
    # the original interest_only flag / hidden skill we must preserve verbatim.
    _present: set = field(default_factory=set, repr=False)
    _skill_primary_interest: str = field(default="False", repr=False)
    _skill_secondary_interest: str = field(default="False", repr=False)
    _skill_hidden: Optional[str] = field(default=None, repr=False)
    _gender_align_key: str = field(default="gender_align", repr=False)
    _favourite_int: bool = field(default=False, repr=False)
    _status_raw: object = field(default=None, repr=False)  # preserve dict-form status

    # --- read --------------------------------------------------------------------
    @classmethod
    def from_save_cat(cls, cat_dict: dict, variant: GameVariant) -> "CatDetails":
        d = cls()
        present = d._present
        for k in cat_dict:
            present.add(k)

        d.name_prefix = str(cat_dict.get("name_prefix") or cat_dict.get("prefix") or "")
        d.name_suffix = str(cat_dict.get("name_suffix") or cat_dict.get("suffix") or "")
        d.gender = str(cat_dict.get("gender") or "")
        if "gender_align" in cat_dict:
            d._gender_align_key = "gender_align"
            d.gender_align = str(cat_dict.get("gender_align") or "")
        elif "genderalign" in cat_dict:
            d._gender_align_key = "genderalign"
            d.gender_align = str(cat_dict.get("genderalign") or "")
        d.backstory = cat_dict.get("backstory")

        d._status_raw = cat_dict.get("status")
        d.status = rank_of(d._status_raw) or "warrior"
        d.experience = _as_int(cat_dict.get("experience"))

        d.moons = _as_int(cat_dict.get("moons"))
        if isinstance(d._status_raw, dict):
            # New schema (v0.13/v0.7.7+): life/death/outsider state lives in the
            # status histories, not in flag keys.
            d.dead = cs.is_dead(d._status_raw)
            d.dead_moons = cs.dead_moons_of(d._status_raw)
            d.df = cs.is_df(d._status_raw)
            d.outside = cs.is_outside(d._status_raw)
            d.exiled = cs.is_exiled(d._status_raw)
        else:
            d.dead = bool(cat_dict.get("dead", False))
            d.dead_moons = _as_int(cat_dict.get("dead_moons"))
            d.df = bool(cat_dict.get("df", False))
            d.outside = bool(cat_dict.get("outside", False))
            d.exiled = bool(cat_dict.get("exiled", False))
        d.prevent_fading = bool(cat_dict.get("prevent_fading", False))

        d.trait = str(cat_dict.get("trait") or "")
        _parse_facets(d, cat_dict.get("facets"))
        _parse_skill_dict(d, cat_dict.get("skill_dict"))

        d.faith = _as_int(cat_dict.get("faith"))
        d.no_faith = bool(cat_dict.get("no_faith", False))
        d.lock_faith = str(cat_dict.get("lock_faith") or "flexible")

        d.no_kits = bool(cat_dict.get("no_kits", False))
        d.no_mates = bool(cat_dict.get("no_mates", False))
        d.no_retire = bool(cat_dict.get("no_retire", False))
        fav = cat_dict.get("favourite", False)
        d._favourite_int = isinstance(fav, int) and not isinstance(fav, bool)
        d.favourite = bool(fav)

        d.courage = _as_int(cat_dict.get("courage"))
        d.compassion = _as_int(cat_dict.get("compassion"))
        d.intelligence = _as_int(cat_dict.get("intelligence"))
        d.empathy = _as_int(cat_dict.get("empathy"))
        return d

    # --- write -------------------------------------------------------------------
    def apply_to_save_cat(self, cat_dict: dict, variant: GameVariant) -> dict:
        """Merge gameplay fields into ``cat_dict`` in place. Returns it.

        Honours the field-write policy: universal fields always; present-only
        fields only if the source had them; LifeGen-only fields only on LifeGen
        saves (or if already present). Never invents a LifeGen key on ClanGen.
        """
        lifegen = variant is GameVariant.LIFEGEN

        def should(key: str) -> bool:
            if key in _LIFEGEN_ONLY:
                return lifegen or key in self._present
            if key in _PRESENT_ONLY:
                return key in self._present
            return True  # universal

        # Identity
        cat_dict["name_prefix"] = self.name_prefix
        cat_dict["name_suffix"] = self.name_suffix
        if self.gender:
            cat_dict["gender"] = self.gender
        if self.gender_align:
            cat_dict[self._gender_align_key] = self.gender_align
        if "backstory" in self._present:
            cat_dict["backstory"] = self.backstory or None

        # Status — preserve the original shape (string vs CatStatus dict),
        # only updating the current rank.
        status = with_rank(self._status_raw, self.status)

        # Dict-form saves keep life/death/outsider state in the status
        # histories: apply only the transforms whose flag actually changed,
        # in game order (kill/revive, afterlife flip, dead time, outside, exile).
        if isinstance(self._status_raw, dict):
            orig = self._status_raw
            if self.dead != cs.is_dead(orig):
                status = cs.kill(status, self.df) if self.dead else cs.revive(status)
            elif self.dead and self.df != cs.is_df(orig):
                status = cs.kill(status, self.df)  # move StarClan <-> Dark Forest
            if self.dead and self.dead_moons != cs.dead_moons_of(orig):
                status = cs.with_dead_moons(status, self.dead_moons)
            if not self.dead:
                if self.outside != cs.is_outside(orig):
                    status = cs.set_outside(status, self.outside, lifegen)
                if self.exiled != cs.is_exiled(orig):
                    status = cs.set_exiled(status, self.exiled)
        cat_dict["status"] = status
        cat_dict["experience"] = self.experience

        # Life & death. moons is universal; the flags are present-only (newer
        # saves have no dead/outside/exiled keys — see _PRESENT_ONLY).
        cat_dict["moons"] = self.moons
        if should("dead"):
            cat_dict["dead"] = self.dead
        if should("dead_moons"):
            cat_dict["dead_moons"] = self.dead_moons
        if should("df"):
            cat_dict["df"] = self.df
        if should("outside"):
            cat_dict["outside"] = self.outside
        if should("exiled"):
            cat_dict["exiled"] = self.exiled
        if should("prevent_fading"):
            cat_dict["prevent_fading"] = self.prevent_fading

        # Personality
        cat_dict["trait"] = self.trait
        if should("facets"):
            cat_dict["facets"] = self.facet_string()
        if should("skill_dict"):
            cat_dict["skill_dict"] = self.skill_dict()

        # Faith (LifeGen-only)
        if should("faith"):
            cat_dict["faith"] = self.faith
        if should("no_faith"):
            cat_dict["no_faith"] = self.no_faith
        if should("lock_faith"):
            cat_dict["lock_faith"] = self.lock_faith

        # Flags
        cat_dict["no_kits"] = self.no_kits
        cat_dict["no_mates"] = self.no_mates
        cat_dict["no_retire"] = self.no_retire
        cat_dict["favourite"] = int(self.favourite) if self._favourite_int or lifegen else self.favourite

        # LifeGen stats
        for key in ("courage", "compassion", "intelligence", "empathy"):
            if should(key):
                cat_dict[key] = getattr(self, key)
        return cat_dict

    # --- helpers -----------------------------------------------------------------
    def facet_string(self) -> str:
        return (
            f"{self.facet_lawfulness},{self.facet_sociability},"
            f"{self.facet_aggression},{self.facet_stability}"
        )

    def skill_dict(self) -> dict:
        def save_str(path: Optional[str], points: int, interest: str) -> Optional[str]:
            if not path:
                return None
            return f"{path},{points},{interest}"

        return {
            "primary": save_str(
                self.skill_primary_path, self.skill_primary_points,
                self._skill_primary_interest,
            ),
            "secondary": save_str(
                self.skill_secondary_path, self.skill_secondary_points,
                self._skill_secondary_interest,
            ),
            "hidden": self._skill_hidden,
        }

    def clear_death(self) -> None:
        """Resurrect: clear the cat's death flags (afterlife rosters handled
        separately by the caller, which has the clan.json)."""
        self.dead = False
        self.df = False
        self.dead_moons = 0


def _parse_facets(d: CatDetails, value) -> None:
    if not isinstance(value, str):
        return
    parts = value.split(",")
    if len(parts) != 4:
        return
    try:
        nums = [max(0, min(16, int(p))) for p in parts]
    except ValueError:
        return
    (d.facet_lawfulness, d.facet_sociability,
     d.facet_aggression, d.facet_stability) = nums


def _parse_skill_dict(d: CatDetails, value) -> None:
    if not isinstance(value, dict):
        return

    def parse(entry):
        # "PATH,points,interest_only" -> (path, points, interest_str)
        if not isinstance(entry, str) or not entry:
            return None, 0, "False"
        parts = entry.split(",")
        path = parts[0] or None
        points = _as_int(parts[1]) if len(parts) > 1 else 0
        interest = parts[2] if len(parts) > 2 else "False"
        return path, points, interest

    d.skill_primary_path, d.skill_primary_points, d._skill_primary_interest = parse(
        value.get("primary")
    )
    d.skill_secondary_path, d.skill_secondary_points, d._skill_secondary_interest = parse(
        value.get("secondary")
    )
    d._skill_hidden = value.get("hidden")
