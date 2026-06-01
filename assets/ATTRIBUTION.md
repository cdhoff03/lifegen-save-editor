# Asset Attribution

## Sprites (`assets/sprites/`)
Sprite sheets are taken from [ClanGen](https://github.com/ClanGenOfficial/clangen)
via [pixel-cat-maker](https://github.com/cgen-tools/pixel-cat-maker).

Licensed under **CC BY-NC 4.0** by the ClanGen Team. See `LICENSES/LICENSE-CCBYNC.md`.

Non-commercial use only. Attribution required.

### LifeGen accessory sheets
The expanded accessory sprite sheets (`flower_accessories`, `plant2_accessories`,
`snake_accessories`, `smallAnimal_accessories`, `deadInsect_accessories`,
`aliveInsect_accessories`, `fruit_accessories`, `crafted_accessories`,
`tail2_accessories`, `wildaccs_1`, `wildaccs_2`, `superartsi`, `coffee`,
`eragona`, `crowns`, `springwinter`, `raincoats`, `pocky1`, `misc_acc`,
`reign1`, `chimes`, `moipa`, `moipa2`, and the expanded `medcatherbs`/`wild`/
`collars`) are imported from
[LifeGen / lifegen-fullgen](https://github.com/ManiiaKop/lifegen-fullgen).
Per that project's `scripts/cat/sprites.py` credits, these are the work of
community artists (OHDAN, coffee, moipa, jay, superartsi, and others) for the
ClanGen/LifeGen community. **CC BY-NC 4.0**, non-commercial use only.

## Configuration JSON (`assets/config/`)
`spritesIndex.json`, `spritesOffsetMap.json`, `peltInfo.json`, `tint.json`,
`white_patches_tint.json` come from the pixel-cat-maker repository.

Licensed under **MPL-2.0**. See `LICENSES/LICENSE-MPL.md`.

## Compositor Logic
The Python `lifegen_editor.sprites.compositor` module is a port of
`drawCat.ts` from pixel-cat-maker, which itself derives from
`generate_sprite()` in ClanGen (`scripts/utility.py`).

Original code MPL-2.0 — the Python port remains MPL-2.0.
