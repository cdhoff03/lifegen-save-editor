"""Layered sprite compositor.

Port of ``drawCat.ts`` from cgen-tools/pixel-cat-maker (itself derived from
ClanGen's ``generate_sprite()`` in ``scripts/utility.py``).

Both upstream sources are MPL-2.0; this port remains MPL-2.0.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

from PIL import Image, ImageChops

from .loader import SpriteLoader, CELL_SIZE

# spritesName lookup: peltName -> sheet prefix used when building "<prefix><COLOUR>"
NAME_TO_SPRITESNAME = {
    "SingleColour": "single",
    "TwoColour": "single",
    "Tabby": "tabby",
    "Marbled": "marbled",
    "Rosette": "rosette",
    "Smoke": "smoke",
    "Ticked": "ticked",
    "Speckled": "speckled",
    "Bengal": "bengal",
    "Mackerel": "mackerel",
    "Classic": "classic",
    "Sokoke": "sokoke",
    "Agouti": "agouti",
    "Singlestripe": "singlestripe",
    "Masked": "masked",
    # Tortie/Calico don't have their own sheet — they layer over a base.
    "Tortie": "",
    "Calico": "",
}


@dataclass
class Pelt:
    """Resolved pelt config consumed by :func:`draw_cat`. Mirrors the ``Pelt``
    type from pixel-cat-maker."""

    name: str  # e.g. "Tabby" / "Tortie" / "Calico"
    colour: str  # e.g. "CREAM"
    skin: str  # e.g. "BLACK"
    eye_colour: str  # e.g. "YELLOW"
    tint: str = "none"
    white_patches_tint: str = "none"
    eye_colour2: Optional[str] = None
    white_patches: Optional[str] = None
    points: Optional[str] = None
    vitiligo: Optional[str] = None
    accessories: list[str] = field(default_factory=list)
    reverse: bool = False
    # Tortie-only
    tortie_base: Optional[str] = None  # sprites-name of base pelt (e.g. "tabby")
    pattern: Optional[str] = None  # tortie mask number/name
    tortie_pattern: Optional[str] = None  # sprites-name of overlay pattern
    tortie_colour: Optional[str] = None
    scars: list[str] = field(default_factory=list)


def _solid(size: tuple[int, int], rgb: Sequence[int]) -> Image.Image:
    return Image.new("RGB", size, (int(rgb[0]), int(rgb[1]), int(rgb[2])))


def _apply_tint(layer: Image.Image, rgb: Optional[Sequence[int]], mode: str) -> Image.Image:
    """Tint non-transparent pixels of ``layer`` with ``rgb`` using ``mode``.

    Modes:
        - ``multiply``: canvas ``multiply`` — darken
        - ``lighter``: canvas ``lighter`` — additive lighten
    """
    if rgb is None:
        return layer
    layer_rgb = layer.convert("RGB")
    solid = _solid(layer.size, rgb)
    if mode == "multiply":
        blended_rgb = ImageChops.multiply(layer_rgb, solid)
    elif mode == "lighter":
        blended_rgb = ImageChops.add(layer_rgb, solid)
    else:
        raise ValueError(f"unknown tint mode {mode!r}")
    out = Image.new("RGBA", layer.size, (0, 0, 0, 0))
    out.paste(blended_rgb, (0, 0))
    out.putalpha(layer.split()[3])
    return out


def _alpha_clip(rgba: Image.Image, mask_alpha: Image.Image) -> Image.Image:
    """Return a copy of ``rgba`` whose alpha is ``rgba.alpha * mask_alpha``.

    Equivalent to canvas ``source-in`` against the mask: pixels of source
    survive only where the mask has alpha.
    """
    src_alpha = rgba.split()[3]
    new_alpha = ImageChops.multiply(src_alpha, mask_alpha)
    out = rgba.copy()
    out.putalpha(new_alpha)
    return out


def _composite_on(base: Image.Image, overlay: Optional[Image.Image]) -> None:
    if overlay is not None:
        base.alpha_composite(overlay)


def _draw_masked(
    loader: SpriteLoader,
    sprite_name: str,
    mask_name: str,
    sprite_number: int,
) -> Optional[Image.Image]:
    """Equivalent of pixel-cat-maker's ``drawMaskedSprite``: clip ``sprite_name``
    to the alpha of ``mask_name``. Used to overlay tortie patterns through the
    tortie mask."""
    mask = loader.get_sprite_cached(mask_name, sprite_number)
    sprite = loader.get_sprite_cached(sprite_name, sprite_number)
    if mask is None or sprite is None:
        return None
    return _alpha_clip(sprite, mask.split()[3])


def _apply_shading(ctx: Image.Image, loader: SpriteLoader, sprite_number: int) -> Image.Image:
    """Multiply ctx by shader sprite (alpha-clipped to ctx), then composite lighting on top."""
    shaders = loader.get_sprite_cached("shaders", sprite_number)
    if shaders is None:
        return ctx
    # Clip shaders to ctx alpha
    clipped = _alpha_clip(shaders, ctx.split()[3])
    # Multiply ctx RGB by clipped shader RGB; preserve ctx alpha
    multiplied_rgb = ImageChops.multiply(ctx.convert("RGB"), clipped.convert("RGB"))
    out = Image.new("RGBA", ctx.size, (0, 0, 0, 0))
    out.paste(multiplied_rgb, (0, 0))
    out.putalpha(ctx.split()[3])
    lighting = loader.get_sprite_cached("lighting", sprite_number)
    _composite_on(out, lighting)
    return out


def _apply_missing_scar(
    ctx: Image.Image,
    loader: SpriteLoader,
    sprite_name: str,
    sprite_number: int,
) -> Image.Image:
    """Apply a "missing piece" scar (ear/tail/paw removal).

    Mirrors canvas operations from drawCat.ts: clip ctx alpha to scar mask,
    then multiply scar RGB into ctx (the white parts of the scar disappear,
    the dark outline lines stay).
    """
    scar = loader.get_sprite_cached(sprite_name, sprite_number)
    if scar is None:
        return ctx
    # destination-in: keep ctx only where scar has alpha
    clipped_ctx = ctx.copy()
    new_ctx_alpha = ImageChops.multiply(ctx.split()[3], scar.split()[3])
    clipped_ctx.putalpha(new_ctx_alpha)
    # offscreen: scar RGB clipped to new ctx alpha
    scar_clipped = _alpha_clip(scar, new_ctx_alpha)
    # multiply ctx RGB by scar_clipped RGB
    multiplied_rgb = ImageChops.multiply(clipped_ctx.convert("RGB"), scar_clipped.convert("RGB"))
    out = Image.new("RGBA", ctx.size, (0, 0, 0, 0))
    out.paste(multiplied_rgb, (0, 0))
    out.putalpha(new_ctx_alpha)
    return out


def draw_cat(
    pelt: Pelt,
    sprite_number: int,
    loader: SpriteLoader,
    *,
    dead: bool = False,
    dark_forest: bool = False,
    shading: bool = False,
    april_fools: bool = False,
) -> Image.Image:
    """Composite a cat sprite. Returns a 50x50 RGBA Pillow image.

    Layer order matches drawCat.ts:
      1. base pelt (or tortie base + masked tortie overlay)
      2. tint (multiply, then additive dilute)
      3. white patches (+ optional white-patches tint)
      4. points (white-patches sprites used for colorpoints; same tint)
      5. vitiligo (white-patches sprites again)
      6. eyes (primary + optional secondary heterochromia)
      7. scar group 1 + 3 (regular overlay scars)
      8. shading + lighting (optional)
      9. lineart (regular / dead / dark-forest / april-fools)
     10. skin (drawn AFTER lineart — sits inside the ears/nose)
     11. scar group 2 (missing pieces)
     12. accessory
    Finally, mirror horizontally if pelt.reverse.
    """
    ctx = Image.new("RGBA", (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    sprites_name = NAME_TO_SPRITESNAME.get(pelt.name, "")

    # 1. base pelt
    if pelt.name not in ("Tortie", "Calico"):
        base = loader.get_sprite_cached(f"{sprites_name}{pelt.colour}", sprite_number)
        _composite_on(ctx, base)
    else:
        base_name = pelt.tortie_base or sprites_name or "single"
        base = loader.get_sprite_cached(f"{base_name}{pelt.colour}", sprite_number)
        _composite_on(ctx, base)
        tortie_pat = pelt.tortie_pattern or "single"
        if tortie_pat == "Single":
            tortie_pat = "SingleColour"
        tortie_layer_name = f"{tortie_pat}{pelt.tortie_colour}"
        mask_name = f"tortiemask{pelt.pattern}"
        masked = _draw_masked(loader, tortie_layer_name, mask_name, sprite_number)
        _composite_on(ctx, masked)

    # 2. tint
    if pelt.tint != "none":
        tint_colours = loader.tints.get("tint_colours", {})
        dilute_colours = loader.tints.get("dilute_tint_colours", {})
        if pelt.tint in tint_colours:
            ctx = _apply_tint(ctx, tint_colours[pelt.tint], "multiply")
        if pelt.tint in dilute_colours:
            ctx = _apply_tint(ctx, dilute_colours[pelt.tint], "lighter")

    # 3. white patches
    if pelt.white_patches:
        wp = loader.get_sprite_cached(f"white{pelt.white_patches}", sprite_number)
        if wp is not None:
            wp = _maybe_tint_white(wp, pelt.white_patches_tint, loader)
            _composite_on(ctx, wp)

    # 4. points (use white-patch sheet)
    if pelt.points:
        pts = loader.get_sprite_cached(f"white{pelt.points}", sprite_number)
        if pts is not None:
            pts = _maybe_tint_white(pts, pelt.white_patches_tint, loader)
            _composite_on(ctx, pts)

    # 5. vitiligo
    if pelt.vitiligo:
        vit = loader.get_sprite_cached(f"white{pelt.vitiligo}", sprite_number)
        _composite_on(ctx, vit)

    # 6. eyes
    _composite_on(ctx, loader.get_sprite_cached(f"eyes{pelt.eye_colour}", sprite_number))
    if pelt.eye_colour2:
        _composite_on(ctx, loader.get_sprite_cached(f"eyes2{pelt.eye_colour2}", sprite_number))

    # 7. overlay scars (groups 1 and 3)
    scars1 = set(loader.pelt_info.get("scars1", []))
    scars3 = set(loader.pelt_info.get("scars3", []))
    for scar in pelt.scars:
        if scar in scars1 or scar in scars3:
            _composite_on(ctx, loader.get_sprite_cached(f"scars{scar}", sprite_number))

    # 8. shading + lighting
    if shading:
        ctx = _apply_shading(ctx, loader, sprite_number)

    # 9. lineart
    lineart_name = _lineart_name(dead=dead, dark_forest=dark_forest, april_fools=april_fools)
    _composite_on(ctx, loader.get_sprite_cached(lineart_name, sprite_number))

    # 10. skin (sits inside ears / nose, drawn over lineart)
    _composite_on(ctx, loader.get_sprite_cached(f"skin{pelt.skin}", sprite_number))

    # 11. missing-piece scars
    scars2 = set(loader.pelt_info.get("scars2", []))
    for scar in pelt.scars:
        if scar in scars2:
            ctx = _apply_missing_scar(ctx, loader, f"scars{scar}", sprite_number)

    # 12. accessories (stacked in list order — last one drawn on top)
    if pelt.accessories:
        plant = loader.pelt_info.get("plant_accessories", [])
        wild = loader.pelt_info.get("wild_accessories", [])
        collars = loader.pelt_info.get("collars", [])
        for acc in pelt.accessories:
            if acc in plant:
                _composite_on(ctx, loader.get_sprite_cached(f"acc_herbs{acc}", sprite_number))
            elif acc in wild:
                _composite_on(ctx, loader.get_sprite_cached(f"acc_wild{acc}", sprite_number))
            elif acc in collars:
                _composite_on(ctx, loader.get_sprite_cached(f"collars{acc}", sprite_number))

    if pelt.reverse:
        ctx = ctx.transpose(Image.FLIP_LEFT_RIGHT)
    return ctx


def _maybe_tint_white(layer: Image.Image, tint_name: str, loader: SpriteLoader) -> Image.Image:
    if tint_name == "none":
        return layer
    tint_colours = loader.white_tints.get("tint_colours", {})
    if tint_name not in tint_colours:
        return layer
    return _apply_tint(layer, tint_colours[tint_name], "multiply")


def _lineart_name(*, dead: bool, dark_forest: bool, april_fools: bool) -> str:
    if april_fools:
        if dead:
            return "aprilfoolslineartdf" if dark_forest else "aprilfoolslineartdead"
        return "aprilfoolslineart"
    if dead:
        return "lineartdf" if dark_forest else "lineartdead"
    return "lines"
