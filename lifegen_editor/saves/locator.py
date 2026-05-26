"""Locate ClanGen / LifeGen save directories across platforms.

Both games use ``platformdirs.user_data_dir(app_name)`` where ``app_name`` is
either ``"ClanGen"`` or ``"LifeGen"``. Saves live under ``<user_data>/saves/``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from platformdirs import user_data_dir


GameName = Literal["ClanGen", "LifeGen"]


@dataclass(frozen=True)
class GameInstall:
    name: GameName
    save_root: Path

    @property
    def exists(self) -> bool:
        return self.save_root.is_dir()


def save_root_for(game: GameName) -> Path:
    """Return the default cross-platform save root for ``game``.

    - macOS:   ``~/Library/Application Support/<game>/saves``
    - Linux:   ``~/.local/share/<game>/saves``
    - Windows: ``%LOCALAPPDATA%\\<game>\\<game>\\saves`` (note ClanGen stores
               under a doubled folder name on Windows via ``platformdirs``)
    """
    base = Path(user_data_dir(game, appauthor=game, roaming=False))
    return base / "saves"


def detect_installs() -> list[GameInstall]:
    """Return all standard save roots that actually exist on disk."""
    results = []
    for name in ("ClanGen", "LifeGen"):
        root = save_root_for(name)  # type: ignore[arg-type]
        results.append(GameInstall(name=name, save_root=root))  # type: ignore[arg-type]
    return [r for r in results if r.exists]


def candidate_roots() -> list[GameInstall]:
    """Return both standard save roots whether they exist or not (for the picker UI)."""
    return [GameInstall(name=n, save_root=save_root_for(n)) for n in ("ClanGen", "LifeGen")]  # type: ignore[arg-type]
