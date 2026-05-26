"""Loads sprite sheets and resolves logical sprite names + pose numbers to 50x50 crops."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

from PIL import Image

from ..paths import SPRITES_DIR, CONFIG_DIR

CELL_SIZE = 50


class SpriteLoader:
    """Caches loaded sprite sheets and serves 50x50 crops by logical name + pose number.

    Maps logical sprite name (e.g. ``eyesYELLOW``) to a spritesheet + (x, y) offset
    via ``spritesIndex.json``, and translates ``spriteNumber`` 0..20 to a grid cell
    via ``spritesOffsetMap.json``.
    """

    def __init__(self, sprites_dir: Path = SPRITES_DIR, config_dir: Path = CONFIG_DIR):
        self.sprites_dir = sprites_dir
        with (config_dir / "spritesIndex.json").open() as f:
            self.sprites_index: dict = json.load(f)
        with (config_dir / "spritesOffsetMap.json").open() as f:
            self.pose_offsets: list = json.load(f)
        with (config_dir / "peltInfo.json").open() as f:
            self.pelt_info: dict = json.load(f)
        with (config_dir / "tint.json").open() as f:
            self.tints: dict = json.load(f)
        with (config_dir / "white_patches_tint.json").open() as f:
            self.white_tints: dict = json.load(f)
        self._sheet_cache: dict[str, Image.Image] = {}

    def _sheet(self, name: str) -> Image.Image:
        cached = self._sheet_cache.get(name)
        if cached is not None:
            return cached
        path = self.sprites_dir / f"{name}.png"
        img = Image.open(path).convert("RGBA")
        self._sheet_cache[name] = img
        return img

    def has_sprite(self, sprite_name: str) -> bool:
        return sprite_name in self.sprites_index

    def get_sprite(self, sprite_name: str, sprite_number: int) -> Optional[Image.Image]:
        """Return a 50x50 RGBA crop for ``sprite_name`` at the given pose index.

        Returns ``None`` if the sprite is unknown (caller may skip silently — pelt
        configs sometimes reference layers that don't exist for a given combo).
        """
        info = self.sprites_index.get(sprite_name)
        if info is None:
            return None
        sheet = self._sheet(info["spritesheet"])
        pose = self.pose_offsets[sprite_number]
        x = int(info["xOffset"] + CELL_SIZE * pose["x"])
        y = int(info["yOffset"] + CELL_SIZE * pose["y"])
        return sheet.crop((x, y, x + CELL_SIZE, y + CELL_SIZE)).copy()

    @lru_cache(maxsize=2048)
    def _cached(self, sprite_name: str, sprite_number: int) -> Optional[Image.Image]:
        # Pillow images aren't truly hashable in a way that helps caching, but the
        # lookup itself (json + crop) is what we want to cache.
        return self.get_sprite(sprite_name, sprite_number)

    def get_sprite_cached(self, sprite_name: str, sprite_number: int) -> Optional[Image.Image]:
        result = self._cached(sprite_name, sprite_number)
        return result.copy() if result is not None else None
