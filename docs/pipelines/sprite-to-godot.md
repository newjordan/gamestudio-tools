# Sprite art to padded atlas to Godot

Pack loose sprite frames into an atlas, add padding (and optional bleed) between frames, then write
a Godot 4 SpriteFrames `.tres`. Godot itself is not opened; the `.tres` follows the documented
text-resource layout.

## Tools

palette-apply → sprite-recolor → sprite-rotate → sprite-scale → sprite-pad → sprite-unpad → sprite-reframe → sprite-align → sprite-stack → sprite-canvas → anim-from-folder (clips JSON) → atlas-pack → (optional atlas-merge / atlas-rename / atlas-sort, or atlas-unpack --untrim to verify a pack/unpack round-trip) → sheet-pad → atlas-to-godot (optional: anim-meta / anim-reverse / anim-pingpong / anim-hold / anim-rename for the clips JSON). `sprite-rotate` and `sprite-scale` also rewrite a packed atlas JSON when given one (90/180/270 only for rotate; `rotated: true` frames are refused).

## Commands

From the kit root, with the source-tree samples:

```bash
mkdir -p /tmp/pipe-sprite
# optional: gst sprite-rotate frames/ -o /tmp/pipe-sprite/rot --angle 90
# optional: gst sprite-scale frames/ -o /tmp/pipe-sprite/scaled --scale 2
# optional: gst sprite-pad frames/ -o /tmp/pipe-sprite/padded-frames --pad 2
# optional: gst sprite-unpad /tmp/pipe-sprite/padded-frames -o /tmp/pipe-sprite/unpadded --pad 2
# optional: gst sprite-reframe /tmp/pipe-sprite/unpadded -o /tmp/pipe-sprite/reframed --size 32x32 --anchor feet
# optional: gst sprite-align /tmp/pipe-sprite/reframed -o /tmp/pipe-sprite/aligned --anchor feet
# optional: gst atlas-rename atlas.json -o /tmp/pipe-sprite/renamed.json --pattern 'walk_(\d+)' --replace 'hero_\1'
# optional: gst atlas-sort /tmp/pipe-sprite/renamed.json -o /tmp/pipe-sprite/sorted.json --by name
# optional: gst atlas-merge hero.json fx.json -o /tmp/pipe-sprite/all --padding 1 --no-pot
# optional: gst palette-apply frames/ -o /tmp/pipe-sprite/pal --palette pico8
# packed sheets: gst sprite-rotate atlas.json -o /tmp/pipe-sprite/rot.png --angle 90 --atlas-out /tmp/pipe-sprite/rot.json
# optional: gst sprite-stack parts -o /tmp/pipe-sprite/stacked --layers shadow,body,outline
# optional: gst sprite-canvas /tmp/pipe-sprite/stacked -o /tmp/pipe-sprite/frames --size 32x32 --anchor feet
gst atlas-pack samples/pipelines/sprites -o /tmp/pipe-sprite/atlas --padding 0 --no-pot
gst sheet-pad /tmp/pipe-sprite/atlas.png /tmp/pipe-sprite/atlas.json \
    -o /tmp/pipe-sprite/padded.png --atlas-out /tmp/pipe-sprite/padded.json --pad 2
gst atlas-to-godot /tmp/pipe-sprite/padded.json -o /tmp/pipe-sprite/hero.tres \
    --clips samples/pipelines/clips.json --res res://art/padded.png
```

The `.tres` should name `walk` and `idle` animations and point at `res://art/padded.png`.

## Known gaps

The SpriteFrames resource was loaded in official Godot 4.7.2.stable.official.ed1daf0bf (optional `GODOT_BIN` test), including unpacked rotated frames (90° CW TexturePacker packing). `samples/` is not in the release tarball; `tests/test_pipelines.py` rebuilds the same
chain on temporary fixtures.
