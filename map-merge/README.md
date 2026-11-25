# map-merge

Merge layers and objects from several Tiled JSON maps (same tile size) into one. Each source can take a name prefix and a tile offset; the output grows to the bounding box of every shifted source. Tilesets with the same source, image or name are reused and GIDs remapped; new tilesets are appended with a fresh firstgid. Encoded tile data is decoded to arrays. Object and layer ids are made unique. Refuses to overwrite an input.

## Usage

```bash
python3 map-merge/map_merge.py rooms/a.json rooms/b.json -o campaign.json --offset 0,0 --offset 64,0 --pretty
python3 map-merge/map_merge.py a.json b.json -o out.json --prefix Town_ --prefix Docks_
```

Run `python3 map-merge/map_merge.py --help` (or `gst map-merge --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements map-stamp (one prefab into a target) and map-clean.

## Source and licence

Original code. Orthogonal maps only. Infinite chunk layers are flattened into a finite layer on the destination.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
