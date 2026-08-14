"""Enumerations for dropdown / multi-select UI controls.

Values extracted from the bundled asset configs at runtime, with a few
fixed sub-lists (points / vitiligo) that the underlying games hard-code.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Optional

from ..paths import CONFIG_DIR
from ..sprites.compositor import NAME_TO_SPRITESNAME
from ..saves.variant import GameVariant

# Patterns toggled separately via is_tortie — exclude from the main pelt dropdown.
PELT_NAMES: list[str] = [n for n in NAME_TO_SPRITESNAME if n not in ("Tortie", "Calico")]

POINT_MARKINGS: list[str] = ["COLOURPOINT", "RAGDOLL", "SEPIAPOINT", "MINKPOINT", "SEALPOINT"]
VITILIGO_MARKINGS: list[str] = [
    "VITILIGO", "VITILIGOTWO", "MOON", "PHANTOM", "KARPATI",
    "POWDER", "BLEACHED", "SMOKEY",
]
LINEART_STYLES: list[tuple[str, dict]] = [
    ("Normal", {"dead": False, "dark_forest": False, "april_fools": False}),
    ("Dead (StarClan)", {"dead": True, "dark_forest": False, "april_fools": False}),
    ("Dark Forest", {"dead": True, "dark_forest": True, "april_fools": False}),
    ("April Fools", {"dead": False, "dark_forest": False, "april_fools": True}),
]

# The 26 named poses of the v0.13/v0.7.7 sheet layout, in offset-map order.
# Saves store these names in their sprite_* fields; the editor uses the index.
POSE_NAMES: list[str] = [
    "newborn0", "newborn1", "newborn2",
    "kitten0", "kitten1", "kitten2",
    "adolescent_short0", "adolescent_short1", "adolescent_short2",
    "adolescent_long0", "adolescent_long1", "adolescent_long2",
    "adult_short0", "adult_short1", "adult_short2",
    "adult_long0", "adult_long1", "adult_long2",
    "senior0", "senior1", "senior2",
    "para_adult_short0", "para_adult_long0", "para_young0",
    "sick_adult0", "sick_young0",
]
POSE_COUNT = len(POSE_NAMES)


@lru_cache(maxsize=1)
def _index() -> dict:
    with (CONFIG_DIR / "spritesIndex.json").open() as f:
        return json.load(f)


def _extract(prefix: str) -> list[str]:
    pat = re.compile(rf"^{re.escape(prefix)}([A-Z0-9_-]+)$")
    out: set[str] = set()
    for key in _index():
        m = pat.match(key)
        if m:
            out.add(m.group(1))
    return sorted(out)


def colours() -> list[str]:
    return _extract("single")


def eye_colours() -> list[str]:
    return _extract("eyes")


def secondary_eye_colours() -> list[str]:
    # No separate eyes2 sheet since v0.13/v0.7.7 — heterochromia reuses the
    # primary eye sprites clipped through the shared mask.
    return eye_colours()


def skin_colours() -> list[str]:
    return _extract("skin")


def all_white_patches() -> list[str]:
    """Every white-patch / point / vitiligo sprite. Used as the dropdown values
    for `white_patches` since the underlying game treats markings as one big set."""
    return _extract("white")


def white_patches_only() -> list[str]:
    """All white sprites minus the ones reserved as points / vitiligo."""
    reserved = set(POINT_MARKINGS) | set(VITILIGO_MARKINGS)
    return [w for w in all_white_patches() if w not in reserved]


def tortie_masks() -> list[str]:
    return _extract("tortiemask")


def tortie_pattern_names() -> list[str]:
    # Single-colour mask works as a tortie overlay too; "Single" is special-cased
    # by the compositor.
    return [n for n in PELT_NAMES if n not in ("Tortie", "Calico")]


@lru_cache(maxsize=1)
def _pelt_info() -> dict:
    with (CONFIG_DIR / "peltInfo.json").open() as f:
        return json.load(f)


def plant_accessories() -> list[str]:
    return sorted(set(_pelt_info()["plant_accessories"]))


def wild_accessories() -> list[str]:
    return sorted(set(_pelt_info()["wild_accessories"]))


def collars() -> list[str]:
    return list(_pelt_info()["collars"])  # preserve original order


def all_scars() -> list[str]:
    info = _pelt_info()
    return sorted(set(info["scars1"]) | set(info["scars2"]) | set(info["scars3"]))


@lru_cache(maxsize=1)
def tints() -> dict:
    with (CONFIG_DIR / "tint.json").open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def white_tints() -> dict:
    with (CONFIG_DIR / "white_patches_tint.json").open() as f:
        return json.load(f)


def tint_names() -> list[str]:
    t = tints()
    names = ["none"]
    names += sorted(t.get("tint_colours", {}).keys())
    names += sorted(t.get("dilute_tint_colours", {}).keys())
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def white_tint_names() -> list[str]:
    t = white_tints()
    names = ["none"]
    names += sorted(t.get("tint_colours", {}).keys())
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


# =============================================================================
# Variant-aware option lists (ClanGen vs LifeGen)
#
# The UI passes the detected GameVariant so the user only ever sees values valid
# for their game — hidden in BOTH directions (e.g. ClanGen shows "medicine cat"
# and hides "healer"/"queen"/LifeGen-only accessories; LifeGen the reverse).
# =============================================================================

# --- status / rank -----------------------------------------------------------
# Both ClanGen and official LifeGen use "medicine cat"; LifeGen adds the queen
# career track. (The ManiiaKop fork's "healer" naming is NOT used by either.)
_STATUS_CORE = [
    "newborn", "kitten", "apprentice", "warrior",
    "medicine cat apprentice", "medicine cat",
    "mediator apprentice", "mediator",
    "elder", "deputy", "leader",
]
_STATUS_LIFEGEN_EXTRA = ["queen's apprentice", "queen"]
_STATUS_OUTSIDERS = ["loner", "rogue", "kittypet", "exiled", "former Clancat"]
# In the dict-status schema (v0.13/v0.7.7+) rank must be a valid CatRank enum
# value; "exiled"/"former Clancat" are standings there, not ranks, and writing
# them as a rank crashes the game on load.
_LEGACY_ONLY_OUTSIDERS = {"exiled", "former Clancat"}


def statuses(variant: GameVariant, legacy_status: bool = True) -> list[str]:
    core = list(_STATUS_CORE)
    if variant.is_lifegen:
        core += _STATUS_LIFEGEN_EXTRA
    outsiders = _STATUS_OUTSIDERS if legacy_status else [
        s for s in _STATUS_OUTSIDERS if s not in _LEGACY_ONLY_OUTSIDERS
    ]
    return core + outsiders


# --- gender / identity -------------------------------------------------------
# Official LifeGen and ClanGen share the same vocabulary (female/male, plus
# trans/nonbinary identities). The variant arg is kept for API symmetry.
def genders(variant: GameVariant) -> list[str]:
    return ["female", "male"]


def gender_aligns(variant: GameVariant) -> list[str]:
    return ["female", "male", "trans female", "trans male", "nonbinary"]


# --- personality -------------------------------------------------------------
# Trait pools are shared between the two games.
NORMAL_TRAITS = [
    "troublesome", "lonesome", "fierce", "bloodthirsty", "cold", "childish",
    "playful", "charismatic", "bold", "daring", "nervous", "righteous",
    "insecure", "strict", "compassionate", "thoughtful", "ambitious", "confident",
    "adventurous", "calm", "careful", "faithful", "loving", "loyal", "responsible",
    "shameless", "sneaky", "strange", "vengeful", "wise", "arrogant", "competitive",
    "grumpy", "cunning", "oblivious", "gloomy", "sincere", "flamboyant", "rebellious",
    "stoic", "aloof", "reserved", "mellow", "flexible", "witty", "methodical",
    "justified", "meek", "cowardly", "emotional", "spontaneous", "energetic",
    "bouncy", "trusting", "disciplined", "patient", "humble", "obsessive",
]
KIT_TRAITS = [
    "unruly", "shy", "impulsive", "bullying", "attention-seeker", "daydreamer",
    "charming", "fearless", "skittish", "quiet", "self-conscious", "know-it-all",
    "sweet", "polite", "bossy", "noisy", "smug", "secretive", "grumpy",
    "manipulative", "leader-like", "passionate", "disciplined", "patient",
    "rebellious", "honest",
]


# ClanGen v0.13.3 uses a strict subset of LifeGen's trait pool
# (resources/dicts/traits/trait_ranges.json: 39 normal + 16 kit).
CLANGEN_TRAITS = frozenset({
    "adventurous", "ambitious", "arrogant", "bloodthirsty", "bold", "calm",
    "careful", "charismatic", "childish", "cold", "compassionate", "competitive",
    "confident", "cunning", "daring", "faithful", "fierce", "flamboyant",
    "gloomy", "grumpy", "insecure", "lonesome", "loving", "loyal", "nervous",
    "oblivious", "playful", "rebellious", "responsible", "righteous",
    "shameless", "sincere", "sneaky", "strange", "strict", "thoughtful",
    "troublesome", "vengeful", "wise",
    # kit traits
    "attention-seeker", "bossy", "bullying", "charming", "daydreamer",
    "fearless", "impulsive", "know-it-all", "noisy", "polite", "quiet",
    "self-conscious", "shy", "skittish", "sweet", "unruly",
})


def traits(variant: Optional[GameVariant] = None) -> list[str]:
    """All selectable traits (adult + kit), de-duplicated, alphabetised."""
    out = sorted(set(NORMAL_TRAITS) | set(KIT_TRAITS))
    if variant is not None and not variant.is_lifegen:
        out = [t for t in out if t in CLANGEN_TRAITS]
    return out


FACET_NAMES = ["lawfulness", "sociability", "aggression", "stability"]
FACET_MIN, FACET_MAX = 0, 16


# --- skills ------------------------------------------------------------------
# ClanGen v0.13.3 SkillPath enum (23 paths; DIGGER no longer exists).
_SKILL_CLANGEN = [
    "TEACHER", "HUNTER", "FIGHTER", "RUNNER", "CLIMBER", "SWIMMER",
    "SPEAKER", "MEDIATOR", "CLEVER", "INSIGHTFUL", "SENSE", "KIT", "STORY",
    "LORE", "CAMP", "HEALER", "STAR", "OMEN", "DREAM", "CLAIRVOYANT",
    "PROPHET", "GHOST", "DARK",
]
# Official LifeGen v0.7.7.5 SkillPath extras (the v0.7.6.4 twenty plus ten new).
_SKILL_LIFEGEN_EXTRA = [
    "EXPLORER", "TRACKER", "ARTISTAN", "GUARDIAN", "TUNNELER", "NAVIGATOR",
    "SONG", "GRACE", "CLEAN", "INNOVATOR", "COMFORTER", "MATCHMAKER", "THINKER",
    "COOPERATIVE", "SCHOLAR", "TIME", "TREASURE", "FISHER", "LANGUAGE", "SLEEPER",
    "GARDENER", "TWOLEGCARE", "CHARMER", "SHOWCAT", "WANDERER", "SCAVENGER",
    "SURVIVOR", "BRAWLER", "INTIMIDATOR", "AMBUSHER",
]
SKILL_POINTS_MIN, SKILL_POINTS_MAX = 0, 29
HIDDEN_SKILLS = ["ROGUE", "LONER", "KITTYPET"]


def skill_paths(variant: GameVariant) -> list[str]:
    if variant.is_lifegen:
        return _SKILL_CLANGEN + _SKILL_LIFEGEN_EXTRA
    return list(_SKILL_CLANGEN)


# --- faith (LifeGen) ---------------------------------------------------------
LOCK_FAITH_VALUES = ["flexible", "starclan", "dark forest", "neutral"]
FAITH_MIN, FAITH_MAX = -9, 9


# --- clan --------------------------------------------------------------------
BIOMES = ["Forest", "Plains", "Mountainous", "Beach"]


# --- age ---------------------------------------------------------------------
# moons -> life-stage label (boundaries from game_config.json age_ranges)
_AGE_BOUNDS = [
    (0, 0, "newborn"), (1, 5, "kitten"), (6, 11, "adolescent"),
    (12, 47, "young adult"), (48, 95, "adult"), (96, 119, "senior adult"),
]


def age_stage(moons: int) -> str:
    for lo, hi, label in _AGE_BOUNDS:
        if lo <= moons <= hi:
            return label
    return "senior"  # 120+


# --- conditions (hardcoded from game resources/dicts/conditions) -------------
# Condition IDs from official LifeGen v0.7.7.5 resources/dicts/conditions/*.json
# (a superset of ClanGen v0.13.3 — the difference is LIFEGEN_ONLY_CONDITIONS).
ILLNESSES = [
    "seizure", "diarrhea", "fleas", "greencough", "kittencough",
    "an infected wound", "carrionplace disease", "redcough", "running nose",
    "whitecough", "yellowcough", "a festering wound", "heat stroke",
    "heat exhaustion", "stomachache", "constant nightmares", "grief stricken",
    "malnourished", "starving", "heartbroken", "breathless fit", "tick fever",
]
INJURIES = [
    "claw-wound", "bite-wound", "cat bite", "beak bite", "snake bite", "rat bite",
    "tick bites", "blood loss", "broken jaw", "broken bone", "mangled leg",
    "dislocated joint", "joint pain", "sprain", "mangled tail", "bruises",
    "cracked pads", "sore", "phantom pain", "scrapes", "small cut", "torn pelt",
    "torn ear", "frostbite", "recovering from birth", "water in their lungs",
    "burn", "severe burn", "shock", "lingering shock", "shivering", "dehydrated",
    "head damage", "damaged eyes", "quilled by a porcupine", "broken back",
    "poisoned", "bee sting", "headache", "severe headache", "pregnant", "guilt",
    "sore throat",
]
PERMANENT_CONDITIONS = [
    "crooked jaw", "lost a leg", "born without a leg", "weak leg", "twisted leg",
    "lost their tail", "born without a tail", "paralyzed", "raspy lungs",
    "wasting disease", "blind", "one bad eye", "failing eyesight",
    "partial hearing loss", "deaf", "constant joint pain", "seizure prone",
    "allergies", "constantly dizzy", "recurring shock", "lasting grief",
    "persistent headaches", "absent", "damaged throat", "selective mutism",
    "strange lump",
]
LIFEGEN_ONLY_CONDITIONS = {"heartbroken", "guilt"}
CONDITION_SEVERITIES = ["minor", "major", "severe"]


def conditions_for(bucket: list[str], variant: GameVariant) -> list[str]:
    if variant.is_lifegen:
        return list(bucket)
    return [c for c in bucket if c not in LIFEGEN_ONLY_CONDITIONS]


# --- variant-aware APPEARANCE filtering --------------------------------------
# Since the v0.13 merge both games share the full base appearance vocabulary
# (colours, pelts, patches, masks) — only accessories still differ. The empty
# sets are kept so the filter functions stay stable.
LIFEGEN_ONLY_COLOURS: frozenset[str] = frozenset()
LIFEGEN_ONLY_PELTS: frozenset[str] = frozenset()
LIFEGEN_ONLY_WHITE_PATCHES: frozenset[str] = frozenset()
LIFEGEN_ONLY_TORTIE_MASKS: frozenset[str] = frozenset()


@lru_cache(maxsize=1)
def clangen_accessories() -> frozenset[str]:
    """Base-ClanGen accessory set: plant + wild + collars (mirrors upstream
    ``Pelt.all_clangen_accessories``). Everything else is LifeGen-only."""
    info = _pelt_info()
    return (frozenset(info["plant_accessories"])
            | frozenset(info["wild_accessories"])
            | frozenset(info["collars"]))


# Ordered (peltInfo key, display label) for every accessory category, matching
# the compositor's render-priority order.
ACCESSORY_CATEGORIES: list[tuple[str, str]] = [
    ("plant_accessories", "Plant"),
    ("wild_accessories", "Wild"),
    ("wild2_accessories", "Wild"),
    ("collars", "Collar"),
    ("aliveInsect_accessories", "Insect"),
    ("deadInsect_accessories", "Dead insect"),
    ("plant2_accessories", "Plant"),
    ("sophisticated_accessories", "Crafted"),
    ("fruit_accessories", "Fruit"),
    ("flowercrown_accessories", "Flower crown"),
    ("misc_accessories", "Misc"),
    ("misc2_accessories", "Misc"),
    ("harness_accessories", "Harness"),
    ("smallanimals_accessories", "Animal"),
]


def pelt_names(variant: GameVariant) -> list[str]:
    if variant.is_lifegen:
        return list(PELT_NAMES)
    return [n for n in PELT_NAMES if n not in LIFEGEN_ONLY_PELTS]


def colours_for(variant: GameVariant) -> list[str]:
    out = colours()
    if not variant.is_lifegen:
        out = [c for c in out if c not in LIFEGEN_ONLY_COLOURS]
    return out


def white_patches_for(variant: GameVariant) -> list[str]:
    out = white_patches_only()
    if not variant.is_lifegen:
        out = [w for w in out if w not in LIFEGEN_ONLY_WHITE_PATCHES]
    return out


def tortie_masks_for(variant: GameVariant) -> list[str]:
    out = tortie_masks()
    if not variant.is_lifegen:
        out = [m for m in out if m not in LIFEGEN_ONLY_TORTIE_MASKS]
    return out


def _accessory_category(acc: str) -> Optional[str]:
    info = _pelt_info()
    for key, _label in ACCESSORY_CATEGORIES:
        if acc in info.get(key, []):
            return key
    return None


def all_accessories(variant: GameVariant) -> list[tuple[str, str]]:
    """Return ``(label, value)`` accessory pairs valid for the variant.

    LifeGen → every category; ClanGen → only the base plant/wild/collars
    whitelist. Duplicates (same id in two categories) are de-duped by value.
    """
    info = _pelt_info()
    base = clangen_accessories()
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, label in ACCESSORY_CATEGORIES:
        for acc in info.get(key, []):
            if acc in seen:
                continue
            if not variant.is_lifegen and acc not in base:
                continue
            seen.add(acc)
            out.append((f"{label} — {acc.title()}", acc))
    return out
