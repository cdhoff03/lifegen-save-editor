"""High-level cat appearance model used by the UI.

A ``CatData`` is editable state. ``to_pelt()`` converts it into the lower-level
``Pelt`` consumed by :func:`lifegen_editor.sprites.draw_cat`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..sprites.compositor import Pelt, NAME_TO_SPRITESNAME


# Inverse of NAME_TO_SPRITESNAME for tortie round-tripping
SPRITESNAME_TO_NAME = {
    "single": "TwoColour",
    "tabby": "Tabby",
    "marbled": "Marbled",
    "rosette": "Rosette",
    "smoke": "Smoke",
    "ticked": "Ticked",
    "speckled": "Speckled",
    "bengal": "Bengal",
    "mackerel": "Mackerel",
    "classic": "Classic",
    "sokoke": "Sokoke",
    "agouti": "Agouti",
    "singlestripe": "Singlestripe",
    "masked": "Masked",
}


@dataclass
class CatData:
    """Editable representation of a single cat's appearance.

    Mirrors the ``CatData`` class from pixel-cat-maker but with snake_case fields
    and a list of accessories instead of a single one.
    """

    pelt_name: str = "SingleColour"
    colour: str = "CREAM"
    skin: str = "BLACK"
    eye_colour: str = "YELLOW"
    eye_colour2: Optional[str] = None

    tint: str = "none"
    white_patches_tint: str = "none"
    white_patches: Optional[str] = None
    points: Optional[str] = None
    vitiligo: Optional[str] = None
    accessories: list[str] = field(default_factory=list)
    scars: list[str] = field(default_factory=list)

    is_tortie: bool = False
    tortie_mask: Optional[str] = None      # pattern (e.g. "ONE")
    tortie_pattern: Optional[str] = None   # pelt-name of overlay (e.g. "Tabby")
    tortie_colour: Optional[str] = None

    sprite_number: int = 3                 # pose index 0..20
    reverse: bool = False
    shading: bool = False
    dead: bool = False
    dark_forest: bool = False
    april_fools: bool = False
    background_colour: str = "rgb(0 0 0 / 0)"

    @property
    def name(self) -> str:
        """Logical pelt name including tortie distinction."""
        return "Tortie" if self.is_tortie else self.pelt_name

    @property
    def accessory(self) -> Optional[str]:
        """First accessory or None. Convenience for pixel-cat-maker interop."""
        return self.accessories[0] if self.accessories else None

    def to_pelt(self) -> Pelt:
        """Convert to the lower-level :class:`Pelt` the compositor consumes."""
        tortie_base = NAME_TO_SPRITESNAME.get(self.pelt_name, "single")
        tortie_pattern_sprites_name = (
            NAME_TO_SPRITESNAME.get(self.tortie_pattern, "")
            if self.tortie_pattern
            else None
        )
        return Pelt(
            name=self.name,
            colour=self.colour,
            skin=self.skin,
            eye_colour=self.eye_colour,
            eye_colour2=self.eye_colour2,
            tint=self.tint,
            white_patches_tint=self.white_patches_tint,
            white_patches=self.white_patches,
            points=self.points,
            vitiligo=self.vitiligo,
            accessories=list(self.accessories),
            reverse=self.reverse,
            tortie_base=tortie_base if self.is_tortie else None,
            pattern=self.tortie_mask if self.is_tortie else None,
            tortie_pattern=tortie_pattern_sprites_name,
            tortie_colour=self.tortie_colour,
            scars=list(self.scars),
        )

    # --- Save-file dict integration -------------------------------------------------
    def apply_to_save_cat(self, cat_dict: dict) -> dict:
        """Merge appearance fields into a ClanGen/LifeGen save-file cat dict in place.

        Preserves every non-appearance field (ID, relationships, moons, etc.).
        Writes accessories in the schema the existing cat already uses so the
        target game reads them back correctly. Returns the same dict for chaining.

        Schema sniffing (in order):
            1. ``accessories`` (or ``inventory``) key present  → LifeGen
               (ManiiaKop fork). Writes ``accessories`` + merges into
               ``inventory``; clears legacy ``accessory``.
            2. ``accessory`` is already a list/tuple           → modern ClanGen.
               Writes ``accessory`` as a list.
            3. otherwise (string or missing)                    → legacy single.
               Writes ``accessory`` as a single string (first item or None).
        """
        cat_dict["pelt_name"] = self.name
        cat_dict["pelt_color"] = self.colour
        cat_dict["pelt_colour"] = self.colour  # both spellings seen in the wild
        cat_dict["eye_colour"] = self.eye_colour
        cat_dict["eye_color"] = self.eye_colour
        cat_dict["eye_colour2"] = self.eye_colour2
        cat_dict["eye_color2"] = self.eye_colour2
        cat_dict["reverse"] = self.reverse
        cat_dict["white_patches"] = self.white_patches
        cat_dict["vitiligo"] = self.vitiligo
        cat_dict["points"] = self.points
        cat_dict["white_patches_tint"] = self.white_patches_tint
        cat_dict["pattern"] = self.tortie_mask if self.is_tortie else None
        cat_dict["tortie_base"] = (
            NAME_TO_SPRITESNAME.get(self.pelt_name, "single") if self.is_tortie else None
        )
        cat_dict["tortie_pattern"] = (
            NAME_TO_SPRITESNAME.get(self.tortie_pattern, "")
            if self.is_tortie and self.tortie_pattern
            else None
        )
        cat_dict["tortie_color"] = self.tortie_colour if self.is_tortie else None
        cat_dict["tortie_colour"] = self.tortie_colour if self.is_tortie else None
        cat_dict["skin"] = self.skin
        cat_dict["tint"] = self.tint
        cat_dict["scars"] = list(self.scars)

        # Accessory schema sniff
        worn = list(self.accessories)
        if "accessories" in cat_dict or "inventory" in cat_dict:
            # LifeGen (ManiiaKop fork): separate worn and owned lists.
            cat_dict["accessories"] = worn
            existing_inv = cat_dict.get("inventory") or []
            if not isinstance(existing_inv, list):
                existing_inv = [existing_inv] if existing_inv else []
            # Inventory is a superset of worn; preserve any not-worn items.
            merged = list(existing_inv)
            for a in worn:
                if a not in merged:
                    merged.append(a)
            cat_dict["inventory"] = merged
            cat_dict["accessory"] = None  # legacy slot cleared per migration logic
        elif isinstance(cat_dict.get("accessory"), (list, tuple)):
            # Modern ClanGen: accessory IS the list.
            cat_dict["accessory"] = worn
        else:
            # Legacy single (older ClanGen, playboyazzy-LifeGen, fresh cat).
            cat_dict["accessory"] = worn[0] if worn else None
        return cat_dict

    @classmethod
    def from_save_cat(cls, cat_dict: dict) -> "CatData":
        """Build a CatData from a ClanGen/LifeGen save-file cat dict."""
        pelt_name = cat_dict.get("pelt_name") or "SingleColour"
        is_tortie = pelt_name in ("Tortie", "Calico")
        if is_tortie:
            base = cat_dict.get("tortie_base") or "single"
            actual_pelt = SPRITESNAME_TO_NAME.get(base, "TwoColour")
        else:
            actual_pelt = pelt_name

        tortie_pattern_raw = cat_dict.get("tortie_pattern")
        tortie_pattern = (
            SPRITESNAME_TO_NAME.get(tortie_pattern_raw) if tortie_pattern_raw else None
        )

        accessories = _read_accessories(cat_dict)

        return cls(
            pelt_name=actual_pelt,
            colour=cat_dict.get("pelt_color") or cat_dict.get("pelt_colour") or "CREAM",
            skin=cat_dict.get("skin") or "BLACK",
            eye_colour=cat_dict.get("eye_colour") or cat_dict.get("eye_color") or "YELLOW",
            eye_colour2=cat_dict.get("eye_colour2") or cat_dict.get("eye_color2"),
            tint=cat_dict.get("tint") or "none",
            white_patches_tint=cat_dict.get("white_patches_tint") or "none",
            white_patches=cat_dict.get("white_patches"),
            points=cat_dict.get("points"),
            vitiligo=cat_dict.get("vitiligo"),
            accessories=accessories,
            scars=list(cat_dict.get("scars") or []),
            is_tortie=is_tortie,
            tortie_mask=cat_dict.get("pattern") if is_tortie else None,
            tortie_pattern=tortie_pattern,
            tortie_colour=cat_dict.get("tortie_color") or cat_dict.get("tortie_colour"),
            reverse=bool(cat_dict.get("reverse", False)),
        )


def _read_accessories(cat_dict: dict) -> list[str]:
    """Pull the worn accessories out of a save-cat dict regardless of schema."""
    # LifeGen ManiiaKop: prefer accessories (worn). inventory is owned-but-maybe-unworn.
    worn = cat_dict.get("accessories")
    if isinstance(worn, list):
        return [a for a in worn if a]
    acc = cat_dict.get("accessory")
    if isinstance(acc, (list, tuple)):
        return [a for a in acc if a]
    if isinstance(acc, str) and acc:
        return [acc]
    return []
