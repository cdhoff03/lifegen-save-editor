"""Round-trip CatData through JSON and URL formats; smoke-test save-cat merge."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lifegen_editor.io import (
    CatData,
    parse_pcm_json,
    parse_pcm_url,
    to_pcm_json,
    to_pcm_url,
)


def main() -> int:
    cases = [
        CatData(pelt_name="Tabby", colour="GINGER", eye_colour="GREEN"),
        CatData(
            pelt_name="Bengal", colour="BROWN", eye_colour="BLUE", eye_colour2="AMBER",
            white_patches="LITTLE", scars=["ONE"], accessories=["CRIMSONBELL"],
        ),
        CatData(
            pelt_name="Tabby", colour="GINGER", is_tortie=True,
            tortie_mask="ONE", tortie_pattern="Tabby", tortie_colour="BLACK",
        ),
        CatData(
            pelt_name="SingleColour", colour="WHITE", eye_colour="BLUE",
            accessories=["BLUE", "MAPLE LEAF"],  # multi: collar + plant on top
        ),
    ]

    for i, cat in enumerate(cases):
        # JSON round-trip
        j = to_pcm_json(cat)
        rt = parse_pcm_json(j)
        # URL round-trip
        u = to_pcm_url(cat)
        rt_u = parse_pcm_url(u)
        ok = (
            rt.name == cat.name
            and rt.colour == cat.colour
            and rt.eye_colour == cat.eye_colour
            and rt.is_tortie == cat.is_tortie
            and rt_u.name == cat.name
            and rt_u.colour == cat.colour
        )
        print(f"{'OK ' if ok else 'FAIL'} case {i} name={cat.name} colour={cat.colour}")
        if not ok:
            print(f"  json roundtrip -> {rt}")
            print(f"  url  roundtrip -> {rt_u}")
            return 1

    # Save-cat merge
    fake_save = {
        "ID": "12345",
        "name_prefix": "Bright",
        "name_suffix": "heart",
        "moons": 42,
        "pelt_name": "Tabby",
        "pelt_color": "BROWN",
        "skin": "BLACK",
        "eye_colour": "AMBER",
    }
    new_appearance = CatData(pelt_name="Smoke", colour="BLACK", eye_colour="BLUE", accessories=["CRIMSON"])
    merged = new_appearance.apply_to_save_cat(dict(fake_save))
    assert merged["ID"] == "12345" and merged["moons"] == 42, "non-appearance fields preserved"
    assert merged["pelt_name"] == "Smoke" and merged["pelt_color"] == "BLACK"
    # Legacy-single schema (no accessories key in source, no list either)
    assert merged["accessory"] == "CRIMSON", f"legacy single, got {merged['accessory']!r}"
    print("OK  save-cat merge preserves non-appearance fields (legacy schema)")

    # ClanGen modern: accessory IS a list already.
    cg_modern = dict(fake_save)
    cg_modern["accessory"] = ["OLD_ITEM"]
    new_multi = CatData(pelt_name="Smoke", colour="BLACK", accessories=["CRIMSON", "MAPLE LEAF"])
    out = new_multi.apply_to_save_cat(cg_modern)
    assert out["accessory"] == ["CRIMSON", "MAPLE LEAF"], f"modern ClanGen list, got {out['accessory']!r}"
    print("OK  modern ClanGen list schema: accessory written as list")

    # LifeGen ManiiaKop: separate accessories + inventory
    lg = dict(fake_save)
    lg["accessory"] = None
    lg["accessories"] = ["OLD_COLLAR"]
    lg["inventory"] = ["OLD_COLLAR", "STASHED_LEAF"]  # owned but not worn
    out = new_multi.apply_to_save_cat(lg)
    assert out["accessories"] == ["CRIMSON", "MAPLE LEAF"], out
    assert out["accessory"] is None, "legacy slot must be cleared"
    # Inventory keeps the previously-stashed item AND adds the newly worn ones.
    assert set(out["inventory"]) == {"STASHED_LEAF", "OLD_COLLAR", "CRIMSON", "MAPLE LEAF"}, out["inventory"]
    print("OK  LifeGen accessories + inventory schema: worn list set, inventory merged")

    # Round-trip from a save dict that has a list -> CatData -> save dict
    rt = CatData.from_save_cat({"accessory": ["A", "B"]})
    assert rt.accessories == ["A", "B"]
    rt2 = CatData.from_save_cat({"accessories": ["A", "B"]})
    assert rt2.accessories == ["A", "B"]
    rt3 = CatData.from_save_cat({"accessory": "SOLO"})
    assert rt3.accessories == ["SOLO"]
    print("OK  from_save_cat handles list, accessories key, and legacy string")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
