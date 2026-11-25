# channel-pack

Pack greyscale maps into RGBA channels (glTF/Godot/Unreal ORM, Unity mask map, or any custom r/g/b/a), with fills for missing maps, optional invert (roughness to smoothness) and unpacking.

## Usage

```bash
python3 channel-pack/channel_pack.py pack --preset orm --ao ao.png --roughness rough.png --metallic metal.png -o stone_orm.png
python3 channel-pack/channel_pack.py pack --r a.png --g b.png --invert g -o custom.png
python3 channel-pack/channel_pack.py unpack stone_orm.png --preset orm -o maps/
```

Run `python3 channel-pack/channel_pack.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Catalogue: texturing pipeline tools (Materialize, Ucupaint, normal-bake output feeds this).

## Source and licence

Original code. Channel conventions are public (glTF ORM, Unity HDRP mask map).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
