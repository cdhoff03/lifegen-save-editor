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

# How many poses the offset map defines.
POSE_COUNT = 21


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
    # "eyes" prefix matches both eyes2 and the primary list; strip the "2*" entries.
    return sorted({c for c in _extract("eyes") if not c.startswith("2")})


def secondary_eye_colours() -> list[str]:
    # eye2 sprites use names like "eyes2YELLOW".
    return _extract("eyes2")


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


def statuses(variant: GameVariant) -> list[str]:
    core = list(_STATUS_CORE)
    if variant.is_lifegen:
        core += _STATUS_LIFEGEN_EXTRA
    return core + _STATUS_OUTSIDERS


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


def traits() -> list[str]:
    """All selectable traits (adult + kit), de-duplicated, alphabetised."""
    return sorted(set(NORMAL_TRAITS) | set(KIT_TRAITS))


FACET_NAMES = ["lawfulness", "sociability", "aggression", "stability"]
FACET_MIN, FACET_MAX = 0, 16


# --- skills ------------------------------------------------------------------
# Base ClanGen paths (modern ClanGen still includes DIGGER).
_SKILL_CLANGEN = [
    "TEACHER", "HUNTER", "FIGHTER", "RUNNER", "CLIMBER", "SWIMMER", "DIGGER",
    "SPEAKER", "MEDIATOR", "CLEVER", "INSIGHTFUL", "SENSE", "KIT", "STORY",
    "LORE", "CAMP", "HEALER", "STAR", "DARK", "OMEN", "DREAM", "CLAIRVOYANT",
    "PROPHET", "GHOST",
]
# Official LifeGen v0.7.6.4 SkillPath enum (drops DIGGER, adds these 20).
_SKILL_LIFEGEN_EXTRA = [
    "EXPLORER", "TRACKER", "ARTISTAN", "GUARDIAN", "TUNNELER", "NAVIGATOR",
    "SONG", "GRACE", "CLEAN", "INNOVATOR", "COMFORTER", "MATCHMAKER", "THINKER",
    "COOPERATIVE", "SCHOLAR", "TIME", "TREASURE", "FISHER", "LANGUAGE", "SLEEPER",
]
SKILL_POINTS_MIN, SKILL_POINTS_MAX = 0, 29
HIDDEN_SKILLS = ["ROGUE", "LONER", "KITTYPET"]


def skill_paths(variant: GameVariant) -> list[str]:
    if variant.is_lifegen:
        # LifeGen dropped DIGGER from the base set, then added its 20 paths.
        base = [p for p in _SKILL_CLANGEN if p != "DIGGER"]
        return base + _SKILL_LIFEGEN_EXTRA
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
# Condition IDs from official LifeGen v0.7.6.4 resources/dicts/conditions/*.json.
ILLNESSES = [
    "seizure", "diarrhea", "fleas", "greencough", "kittencough",
    "an infected wound", "carrionplace disease", "redcough", "running nose",
    "whitecough", "yellowcough", "a festering wound", "heat stroke",
    "heat exhaustion", "stomachache", "constant nightmares", "grief stricken",
    "malnourished", "starving", "heartbroken",
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
]
PERMANENT_CONDITIONS = [
    "crooked jaw", "lost a leg", "born without a leg", "weak leg", "twisted leg",
    "lost their tail", "born without a tail", "paralyzed", "raspy lungs",
    "wasting disease", "blind", "one bad eye", "failing eyesight",
    "partial hearing loss", "deaf", "constant joint pain", "seizure prone",
    "allergies", "constantly dizzy", "recurring shock", "lasting grief",
    "persistent headaches",
]
CONDITION_SEVERITIES = ["minor", "major", "severe"]


# --- variant-aware APPEARANCE filtering --------------------------------------
# Appearance values that exist only in LifeGen's expanded asset set. Hidden when
# editing a ClanGen save so the picker stays game-accurate in both directions.
LIFEGEN_ONLY_COLOURS = {"GHOST"}
LIFEGEN_ONLY_PELTS = {"Masked"}
LIFEGEN_ONLY_WHITE_PATCHES = {"BLAZEMASK", "TEARS", "DOUGIE"}
LIFEGEN_ONLY_TORTIE_MASKS = {"CRYPTIC", "BLUE-TIPPED"}

# The base-ClanGen accessory whitelist. peltInfo.json now holds LifeGen's full
# expanded plant/wild/collars lists, so ClanGen filtering can't just go by
# category — it goes by membership in this frozen base set (the editor's bundled
# accessories before LifeGen's sheets were imported, == base ClanGen).
CLANGEN_ACCESSORY_WHITELIST = frozenset({
    # plant / herbs
    "MAPLE LEAF", "HOLLY", "BLUE BERRIES", "FORGET ME NOTS", "RYE STALK", "CATTAIL",
    "POPPY", "ORANGE POPPY", "CYAN POPPY", "WHITE POPPY", "PINK POPPY", "BLUEBELLS",
    "LILY OF THE VALLEY", "SNAPDRAGON", "HERBS", "PETALS", "NETTLE", "HEATHER",
    "GORSE", "JUNIPER", "RASPBERRY", "LAVENDER", "OAK LEAVES", "CATMINT",
    "MAPLE SEED", "LAUREL", "BULB WHITE", "BULB YELLOW", "BULB ORANGE", "BULB PINK",
    "BULB BLUE", "CLOVER", "DAISY", "DRY HERBS", "DRY CATMINT", "DRY NETTLES",
    "DRY LAURELS",
    # wild
    "RED FEATHERS", "BLUE FEATHERS", "JAY FEATHERS", "GULL FEATHERS",
    "SPARROW FEATHERS", "MOTH WINGS", "ROSY MOTH WINGS", "MORPHO BUTTERFLY",
    "MONARCH BUTTERFLY", "CICADA WINGS", "BLACK CICADA",
    # collars: plain / bell / bow / nylon, all 15 colours each
    "CRIMSON", "BLUE", "YELLOW", "CYAN", "RED", "LIME", "GREEN", "RAINBOW", "BLACK",
    "SPIKES", "WHITE", "PINK", "PURPLE", "MULTI", "INDIGO",
    "CRIMSONBELL", "BLUEBELL", "YELLOWBELL", "CYANBELL", "REDBELL", "LIMEBELL",
    "GREENBELL", "RAINBOWBELL", "BLACKBELL", "SPIKESBELL", "WHITEBELL", "PINKBELL",
    "PURPLEBELL", "MULTIBELL", "INDIGOBELL",
    "CRIMSONBOW", "BLUEBOW", "YELLOWBOW", "CYANBOW", "REDBOW", "LIMEBOW", "GREENBOW",
    "RAINBOWBOW", "BLACKBOW", "SPIKESBOW", "WHITEBOW", "PINKBOW", "PURPLEBOW",
    "MULTIBOW", "INDIGOBOW",
    "CRIMSONNYLON", "BLUENYLON", "YELLOWNYLON", "CYANNYLON", "REDNYLON", "LIMENYLON",
    "GREENNYLON", "RAINBOWNYLON", "BLACKNYLON", "SPIKESNYLON", "WHITENYLON",
    "PINKNYLON", "PURPLENYLON", "MULTINYLON", "INDIGONYLON",
})

# Ordered (peltInfo key, display label) for every accessory category. New
# LifeGen categories are appended after the three base ones.
ACCESSORY_CATEGORIES: list[tuple[str, str]] = [
    ("plant_accessories", "Plant"),
    ("wild_accessories", "Wild"),
    ("collars", "Collar"),
    ("flower_accessories", "Flower"),
    ("plant2_accessories", "Plant"),
    ("snake_accessories", "Snake"),
    ("smallAnimal_accessories", "Animal"),
    ("deadInsect_accessories", "Dead insect"),
    ("aliveInsect_accessories", "Insect"),
    ("fruit_accessories", "Fruit"),
    ("crafted_accessories", "Crafted"),
    ("tail2_accessories", "Tail"),
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
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for key, label in ACCESSORY_CATEGORIES:
        for acc in info.get(key, []):
            if acc in seen:
                continue
            if not variant.is_lifegen and acc not in CLANGEN_ACCESSORY_WHITELIST:
                continue
            seen.add(acc)
            out.append((f"{label} — {acc.title()}", acc))
    return out
