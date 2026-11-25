# anim-meta

Group frames named `walk_01, walk_02, idle-1...` (from an atlas JSON or a folder) into animation clips ordered by number, with per-clip fps and loop flags, a gap warning, and Phaser 3 animation JSON export.

## Usage

```bash
python3 anim-meta/anim_meta.py atlas.json --fps walk=10,idle=4 --once attack --clips clips.json --phaser anims.json --atlas-key hero
```

Run `python3 anim-meta/anim_meta.py --help` (or `gst anim-meta --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. The Phaser output follows the public Phaser 3 animation JSON format.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
