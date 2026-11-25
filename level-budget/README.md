# level-budget

Sum objects (and optional tile ids) in Tiled JSON maps against a budget JSON, and flag maps that go over or under. Objects are keyed by type/class, name, or a custom property; tilesets can contribute counts by gid. Per-map overrides and ignores; text, Markdown and JSON; CI exit codes.

## Usage

```bash
python3 level-budget/level_budget.py maps/*.json --budget budget.json --md review.md
python3 level-budget/level_budget.py maps/boss.json --budget budget.json --fail-on-under
```

Run `python3 level-budget/level_budget.py --help` (or `gst level-budget --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

None (new). Complements tilemap-stats (what is in the map) and map-reach (whether the player can get to it).

## Source and licence

Original code. Reads Tiled's documented JSON map format. A budget of 0 means the key must not appear. Encoded (base64 zlib/gzip or csv) tile data is decoded; zstd is decoded by a native decoder when one is importable (Python 3.14+ `compression.zstd`, `pyzstd`, `zstd`) and otherwise by the kit's own pure-Python decoder (`lib/zstd_pure.py`: raw, RLE and compressed blocks, content checksum verified, no dictionaries, 32 MiB output cap).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
