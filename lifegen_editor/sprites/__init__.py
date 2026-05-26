"""Sprite asset loading and compositing."""
from .loader import SpriteLoader, CELL_SIZE
from .compositor import draw_cat

__all__ = ["SpriteLoader", "CELL_SIZE", "draw_cat"]
