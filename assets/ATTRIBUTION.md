# Asset Attribution

## Sprites (`assets/sprites/`)
Sprite sheets are taken from [ClanGen](https://github.com/ClanGenOfficial/clangen)
via [pixel-cat-maker](https://github.com/cgen-tools/pixel-cat-maker).

Licensed under **CC BY-NC 4.0** by the ClanGen Team. See `LICENSES/LICENSE-CCBYNC.md`.

Non-commercial use only. Attribution required.

## Configuration JSON (`assets/config/`)
`spritesIndex.json`, `spritesOffsetMap.json`, `peltInfo.json`, `tint.json`,
`white_patches_tint.json` come from the pixel-cat-maker repository.

Licensed under **MPL-2.0**. See `LICENSES/LICENSE-MPL.md`.

## Compositor Logic
The Python `lifegen_editor.sprites.compositor` module is a port of
`drawCat.ts` from pixel-cat-maker, which itself derives from
`generate_sprite()` in ClanGen (`scripts/utility.py`).

Original code MPL-2.0 — the Python port remains MPL-2.0.
