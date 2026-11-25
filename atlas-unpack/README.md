# atlas-unpack

Extract frames from an atlas PNG + JSON (the hash or array layout that atlas-pack writes) back to a folder of PNGs. `--untrim` restores each sprite onto its pre-pack `sourceSize` canvas using `spriteSourceSize`, so a pack → unpack --untrim round-trip matches the original untrimmed frames. Rotated frames are refused.

```
gst atlas-unpack atlas.json -o frames/
gst atlas-unpack atlas.json -o frames/ --untrim --image atlas.png
```

## Usage

```bash
python3 atlas-unpack/atlas_unpack.py atlas.json -o frames/
python3 atlas-unpack/atlas_unpack.py atlas.json -o frames/ --untrim --image atlas.png
```

Run `python3 atlas-unpack/atlas_unpack.py --help` (or `gst atlas-unpack --help`) for every option. Requires Python 3.10+ with Pillow.

## Known gaps

Rotated (`"rotated": true`) frames are not unpacked. Nine-slice / pivot metadata is not rewritten into sidecar files.

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests/test_batch19.py`
