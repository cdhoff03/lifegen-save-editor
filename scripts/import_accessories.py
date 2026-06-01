#!/usr/bin/env python3
"""One-shot: import a LifeGen build's accessory sprite sheets into the editor.

LifeGen lays out each accessory as a 3x7 block of pose tiles on a sheet, placed
by ``Sprites.make_group(sheet, (col, row), name)``: the block's top-left pixel
is ``(col * sprites_x * size, row * sprites_y * size)`` with the defaults
``sprites_x=3, sprites_y=7, size=50``. The editor's ``spritesIndex.json`` stores
exactly that top-left pixel as ``xOffset``/``yOffset`` and re-derives each pose
from ``spritesOffsetMap.json`` — so we can lift the game's layout verbatim.

The accessory layout in ``scripts/cat/sprites.py`` is read **statically with the
``ast`` module** (no code execution): we literal-eval the ``*_data`` name lists
and the inline ``enumerate([...])`` lists, then read each ``make_group`` call's
sheet / position / name to compute offsets. Two loop shapes are handled:

  A)  for a, i in enumerate([...]):           # col = a, row = constant
          self.make_group(sheet, (a, ROW), f'PREFIX{i}')
  B)  for row, r in enumerate(DATA):           # 2-D data list
          for col, x in enumerate(r):
              self.make_group(sheet, (col, row), f'PREFIX{x}')   # row may be const

This script:
  1. parses the accessory ``make_group`` calls and computes pixel offsets;
  2. writes/merges ``acc_*`` / ``collars*`` entries into
     ``assets/config/spritesIndex.json`` (non-accessory entries untouched);
  3. rebuilds the accessory category lists in ``assets/config/peltInfo.json``;
  4. copies each referenced sheet PNG into ``assets/sprites/``.

Usage:  python scripts/import_accessories.py /tmp/lifegen-official
"""
from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

TILE = 50  # px; LifeGen lineart is 3x7 of 50px tiles
SPRITES_X, SPRITES_Y = 3, 7

# accessory id prefix -> peltInfo.json category key
PREFIX_TO_CATEGORY = {
    "acc_herbs": "plant_accessories",
    "acc_wild": "wild_accessories",
    "collars": "collars",
    "acc_flower": "flower_accessories",
    "acc_plant2": "plant2_accessories",
    "acc_snake": "snake_accessories",
    "acc_smallAnimal": "smallAnimal_accessories",
    "acc_deadInsect": "deadInsect_accessories",
    "acc_aliveInsect": "aliveInsect_accessories",
    "acc_fruit": "fruit_accessories",
    "acc_crafted": "crafted_accessories",
    "acc_tail2": "tail2_accessories",
}
_PREFIXES = sorted(PREFIX_TO_CATEGORY, key=len, reverse=True)


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def _is_make_group(call) -> bool:
    return (
        isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "make_group"
    )


def _fstring(node):
    """(prefix, var_name) from an f-string like f'acc_flower{i}'."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value, None
    if not isinstance(node, ast.JoinedStr):
        return None, None
    prefix, var = "", None
    for part in node.values:
        if isinstance(part, ast.Constant):
            prefix += str(part.value)
        elif isinstance(part, ast.FormattedValue) and isinstance(part.value, ast.Name):
            var = part.value.id
    return prefix, var


def _coord(node, binding: dict):
    """Resolve a pos component: a bound loop-index name, or a constant int."""
    if isinstance(node, ast.Name) and node.id in binding:
        return binding[node.id]
    if isinstance(node, ast.Constant):
        return int(node.value)
    return None


def _enumerate_arg(call):
    """If ``call`` is ``enumerate(X)`` return X node, else None."""
    if (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "enumerate" and call.args):
        return call.args[0]
    return None


def _emit_call(call, idx_to_value, name_value, out):
    """Record one make_group with its loop bindings resolved to (sheet,col,row,name)."""
    if len(call.args) < 3:
        return
    sheet = call.args[0]
    if not (isinstance(sheet, ast.Constant) and isinstance(sheet.value, str)):
        return
    pos = call.args[1]
    if not (isinstance(pos, ast.Tuple) and len(pos.elts) == 2):
        return
    prefix, var = _fstring(call.args[2])
    if prefix is None:
        return
    col = _coord(pos.elts[0], idx_to_value)
    row = _coord(pos.elts[1], idx_to_value)
    if col is None or row is None:
        return
    name = prefix + (name_value if var else "")
    out.append((sheet.value, col, row, name))


def parse_accessories(sprites_py: Path):
    """Return list of (sheet, col, row, full_name) for every accessory make_group."""
    tree = ast.parse(sprites_py.read_text(encoding="utf-8"))

    # collect *_data name lists (1-D or 2-D literals)
    data_vars: dict[str, list] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            val = _literal(node.value)
            if isinstance(val, list):
                data_vars[node.targets[0].id] = val

    out: list[tuple] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue
        if not (isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2):
            continue
        idx_name = node.target.elts[0].id if isinstance(node.target.elts[0], ast.Name) else None
        elem_name = node.target.elts[1].id if isinstance(node.target.elts[1], ast.Name) else None
        src = _enumerate_arg(node.iter)
        if src is None or idx_name is None or elem_name is None:
            continue

        # Shape B: outer loop over a 2-D data list, with an inner enumerate(elem)
        inner_fors = [s for s in node.body if isinstance(s, ast.For)]
        data2d = data_vars.get(src.id) if isinstance(src, ast.Name) else _literal(src)
        if inner_fors and isinstance(data2d, list) and data2d and isinstance(data2d[0], list):
            for inner in inner_fors:
                if not (isinstance(inner.target, ast.Tuple) and len(inner.target.elts) == 2):
                    continue
                cidx = inner.target.elts[0].id if isinstance(inner.target.elts[0], ast.Name) else None
                inner_src = _enumerate_arg(inner.iter)
                if cidx is None or not (isinstance(inner_src, ast.Name) and inner_src.id == elem_name):
                    continue
                calls = [s.value for s in inner.body if isinstance(s, ast.Expr) and _is_make_group(s.value)]
                for r, rowlist in enumerate(data2d):
                    if not isinstance(rowlist, list):
                        continue
                    for c, element in enumerate(rowlist):
                        for call in calls:
                            _emit_call(call, {idx_name: r, cidx: c}, element, out)
            continue

        # Shape A: single loop over a 1-D literal list
        literal = _literal(src)
        if isinstance(literal, list) and literal and isinstance(literal[0], str):
            calls = [s.value for s in node.body if isinstance(s, ast.Expr) and _is_make_group(s.value)]
            for k, element in enumerate(literal):
                for call in calls:
                    _emit_call(call, {idx_name: k}, element, out)
    return out


def _split_prefix(name: str):
    for p in _PREFIXES:
        if name.startswith(p):
            return p, name[len(p):]
    return None, None


def main(argv) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    game = Path(argv[1])
    sprites_py = game / "scripts" / "cat" / "sprites.py"
    game_sprites = game / "sprites"
    if not sprites_py.is_file():
        print(f"ERR: {sprites_py} not found")
        return 1

    repo = Path(__file__).resolve().parent.parent
    cfg = repo / "assets" / "config"
    asset_sprites = repo / "assets" / "sprites"

    calls = parse_accessories(sprites_py)

    index = json.loads((cfg / "spritesIndex.json").read_text())
    categories: dict[str, list[str]] = {k: [] for k in PREFIX_TO_CATEGORY.values()}
    sheets_needed: set[str] = set()
    n_added = 0
    for sheet, col, row, name in calls:
        prefix, acc_id = _split_prefix(name)
        if prefix is None or not acc_id:
            continue
        index[name] = {
            "spritesheet": sheet,
            "xOffset": float(col * SPRITES_X * TILE),
            "yOffset": float(row * SPRITES_Y * TILE),
        }
        cat = PREFIX_TO_CATEGORY[prefix]
        if acc_id not in categories[cat]:
            categories[cat].append(acc_id)
        sheets_needed.add(sheet)
        n_added += 1

    copied, missing = 0, []
    asset_sprites.mkdir(parents=True, exist_ok=True)
    for sheet in sorted(sheets_needed):
        png = game_sprites / f"{sheet}.png"
        if png.is_file():
            shutil.copy2(png, asset_sprites / f"{sheet}.png")
            copied += 1
        else:
            missing.append(sheet)

    pelt_info = json.loads((cfg / "peltInfo.json").read_text())
    for key, vals in categories.items():
        pelt_info[key] = vals
    pelt_info.pop("tail_accessories", None)  # legacy/dead

    (cfg / "spritesIndex.json").write_text(json.dumps(index, indent=2) + "\n")
    (cfg / "peltInfo.json").write_text(json.dumps(pelt_info, indent=2) + "\n")

    print(f"parsed {len(calls)} accessory make_group calls; wrote {n_added} index entries")
    for key in PREFIX_TO_CATEGORY.values():
        print(f"  {key}: {len(categories[key])}")
    print(f"copied {copied} sheet PNGs into assets/sprites/")
    if missing:
        print(f"  MISSING sheets (accessories skipped): {missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
