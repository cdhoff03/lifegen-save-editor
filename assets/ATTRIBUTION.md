# Asset Attribution

## Sprites (`assets/sprites/`)
All sprite sheets are vendored from the official game repositories via
`scripts/import_from_game.py`:

- [LifeGen](https://github.com/sedgestripe/clangen) (v0.7.7.5) — the source of
  every bundled sheet; its shared base art comes from
  [ClanGen](https://github.com/ClanGenOfficial/clangen) (v0.13), and its
  expanded accessory sheets are the work of community artists (OHDAN, coffee,
  moipa, jay, superartsi, and others) for the ClanGen/LifeGen community.
- `acc_collars_baked.png` is generated at import time by applying the games'
  collar palette maps (`sprites/palettes/`) to the base collar sheet.

Licensed under **CC BY-NC 4.0** by the ClanGen Team and LifeGen contributors.
See `LICENSES/LICENSE-CCBYNC.md`. Non-commercial use only. Attribution required.

## Configuration JSON (`assets/config/`)
`spritesIndex.json`, `spritesOffsetMap.json`, and `peltInfo.json` are generated
by `scripts/import_from_game.py` from the games' `sprites/dicts/*.json`.
`tint.json`, `white_patches_tint.json`, and `conversion_dict.json` are copied
verbatim from the LifeGen repository.

Game data is MPL-2.0. See `LICENSES/LICENSE-MPL.md`.

## Compositor Logic
The Python `lifegen_editor.sprites.compositor` module is a port of
`drawCat.ts` from [pixel-cat-maker](https://github.com/cgen-tools/pixel-cat-maker),
which itself derives from `generate_sprite()` in ClanGen
(now `scripts/cat/sprites/display_sprites.py`).

Original code MPL-2.0 — the Python port remains MPL-2.0.
