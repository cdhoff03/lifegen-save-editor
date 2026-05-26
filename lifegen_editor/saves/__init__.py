"""Save file location, loading, and writing for ClanGen and LifeGen."""
from .locator import (
    GameInstall,
    detect_installs,
    save_root_for,
)
from .save_io import (
    Clan,
    SaveCat,
    load_clan,
    list_clans,
    write_clan_with_backup,
)

__all__ = [
    "GameInstall",
    "detect_installs",
    "save_root_for",
    "Clan",
    "SaveCat",
    "load_clan",
    "list_clans",
    "write_clan_with_backup",
]
