# hitbox-to-godot

Write a Godot 4 Area2D scene from hitbox-gen JSON. Each frame becomes an Area2D with one CollisionShape2D; `--shape` selects aabb, circle or capsule.

## Usage

```bash
python3 hitbox-to-godot/hitbox_to_godot.py hero.hitbox.json -o hero_hitbox.tscn --shape capsule
```

Run `python3 hitbox-to-godot/hitbox-to-godot.py --help` (or `gst hitbox-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Normalized hitbox JSON is refused. Capsule height is shaft length plus twice the radius, matching Godot 4 CapsuleShape2D. Empty frames are skipped.

## Tests

`python3 -m pytest -q tests/test_batch32.py`
