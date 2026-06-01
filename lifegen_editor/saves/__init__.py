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
from .save_io import atomic_write_json
from .variant import GameVariant, detect_variant
from .catstatus import rank_of, standing_of, with_rank
from .side_files import (
    CONDITION_KEYS,
    AFTERLIFE_ROSTERS,
    conditions_path,
    relationships_path,
    clan_json_path,
    load_conditions,
    load_relationships,
    load_clan_json,
    default_condition_entry,
    write_conditions,
    write_relationships,
    write_clan_json,
    remove_from_afterlife,
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
    "atomic_write_json",
    "GameVariant",
    "detect_variant",
    "rank_of",
    "standing_of",
    "with_rank",
    "CONDITION_KEYS",
    "AFTERLIFE_ROSTERS",
    "conditions_path",
    "relationships_path",
    "clan_json_path",
    "load_conditions",
    "load_relationships",
    "load_clan_json",
    "default_condition_entry",
    "write_conditions",
    "write_relationships",
    "write_clan_json",
    "remove_from_afterlife",
]
