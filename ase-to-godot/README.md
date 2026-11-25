# ase-to-godot

Write a Godot 4 SpriteFrames `.tres` from a binary Aseprite `.ase` / `.aseprite` file (no Aseprite app). Frames are exported as PNGs; tags become animations (or a single `default` clip when there are no tags).

Tag direction and repeat are expanded into the frame list, so Godot plays what Aseprite plays:

| Aseprite direction | frames for a tag over 0..3 | loop |
| --- | --- | --- |
| forward | 0 1 2 3 | yes |
| reverse | 3 2 1 0 | yes |
| ping-pong | 0 1 2 3 2 1 (the ends are not doubled, so the loop is seamless) | yes |
| ping-pong reverse | 3 2 1 0 1 2 | yes |

A tag with a repeat count of N (Aseprite 1.3) plays N cycles and then stops (`loop` off); a finite ping-pong returns to its start frame. Durations follow the expanded frames. Unrolled clips are clamped to 2048 frames.

## Usage

```bash
python3 ase-to-godot/ase_to_godot.py hero.ase -o hero_frames.tres --frames-dir ./hero_frames --res res://hero/

# play every tag forward and looping, as before 2.1.0
python3 ase-to-godot/ase_to_godot.py hero.ase -o hero_frames.tres --ignore-direction
```

Without `--res`, the frame textures' `res://` folder is derived from the nearest `project.godot` above the frames folder (2.4.0; older versions wrote a bare `res://frame_NNNN.png`). With no project above it, `res://<frames folder name>/` is used and a note is printed.

Run `python3 ase-to-godot/ase_to_godot.py --help` (or `gst ase-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Tag colours and user data are ignored. Ping-pong of a finite repeat count ends on its start frame (as Aseprite's timeline does), not one frame short. 16-bit grayscale and tilemap cels are reported by ase-decode but not composited. Does not write PNG `.import` sidecars.

## Tests

`python3 -m pytest -q tests/test_batch32.py tests/test_v21.py`
