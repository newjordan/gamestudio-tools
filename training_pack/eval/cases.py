"""Eval cases for gamestudio-tools, written from `gst help <tool>` / `gst info <tool>` and observed CLI behaviour only
(no tool source was read). Each case: a user prompt, the expected command, and observable checks. Fixture files are
described in fixtures.py: frames/{walk_0..3,idle_0..1}.png (16x16, 8x8 opaque box), sprite.png, sheet.png (64x16, 4
frames), tiles.png (2 tiles), tiles_dup.png (3 tiles, 0==2), grad.png 32x32, odd.png 20x12, height.png, ao/rough/metal.png,
anim.gif (3 frames), tone.wav (0.5 s 440 Hz mono, peak -6.02 dBFS), tone_stereo.wav, padded.wav (0.25 s silence each
side), quiet.wav (peak -26 dBFS), map.json (10x8 Tiled: ground all gid 1, walls border gid 2, objects spawn@2,2 goal@7,5),
map.tmx (4x3 CSV), cube.obj (6 quads), loc.csv / loc_bad.csv / loc_b.csv, pico8.hex, enemies.csv, proj/ (Godot project
with main.tscn -> art/hero.png and an unreferenced art/orphan.png), proj_broken/ (missing res:// ref), font.ttf (kit
DejaVu Sans), chars.txt."""
SAMPLE = "$GST_ROOT/examples/sample-topdown"
CASES = []


def C(id, tool, prompt, cmd, checks, pre=None):
    CASES.append({"id": id, "tool": tool, "prompt": prompt, "cmd": cmd, "checks": checks, **({"pre": pre} if pre else {})})


PACK = "gst atlas-pack frames -o atlas"
CLIPS = "gst anim-from-folder frames -o clips.json --pattern '{clip}_{frame}.png'"
SPLIT = "gst map-fill map.json -o split.json --layer walls --gid 2 --rect 5,0,1,8"   # wall column across the map

# ---------------------------------------------------------------- sprites / images
C("sprite_scale_x2", "sprite-scale", "Scale my 16x16 sprite up 2x with nearest neighbour into out/.",
  "gst sprite-scale sprite.png -o out --scale 2", [["exit", 0], ["png", "out/sprite.png", 32, 32], ["unchanged", "sprite.png"]])
C("sprite_scale_size", "sprite-scale", "Resize sprite.png to exactly 48x48 pixels.",
  "gst sprite-scale sprite.png -o out --size 48x48", [["exit", 0], ["png", "out/sprite.png", 48, 48]])
C("sprite_canvas_center", "sprite-canvas", "Put sprite.png centred on a 32x24 transparent canvas.",
  "gst sprite-canvas sprite.png -o out --size 32x24 --anchor center",
  [["exit", 0], ["png", "out/sprite.png", 32, 24], ["img_pixel", "out/sprite.png", 0, 0, [0, 0, 0, 0]], ["img_pixel", "out/sprite.png", 16, 12, [255, 0, 77, 255]]])
C("sprite_pad_uniform", "sprite-pad", "Add 2 px of transparent padding on every side of sprite.png.",
  "gst sprite-pad sprite.png -o out --pad 2", [["exit", 0], ["png", "out/sprite.png|out", 20, 20]])
C("sprite_pad_ltrb", "sprite-pad", "Pad sprite.png by left 1, top 2, right 3, bottom 4.",
  "gst sprite-pad sprite.png -o out --pad 1,2,3,4", [["exit", 0], ["png", "out/sprite.png|out", 20, 22]])
C("sprite_trim", "sprite-trim", "Trim the empty border off frames/walk_0.png.",
  "gst sprite-trim frames/walk_0.png -o out", [["exit", 0], ["png", "out/walk_0.png", 8, 8]])
C("sprite_trim_padding", "sprite-trim", "Trim walk_0 but keep 1 px of padding.",
  "gst sprite-trim frames/walk_0.png -o out --padding 1", [["exit", 0], ["png", "out/walk_0.png", 10, 10]])
C("outline_outer_keep", "sprite-outline-gen", "Give sprite.png a 1 px outer outline in #1d2b53 without changing its size.",
  "gst sprite-outline-gen sprite.png -o out --mode outer --width 1 --color '#1d2b53' --keep-size",
  [["exit", 0], ["png", "out/*.png", 16, 16], ["img_opaque_more", "out/*.png", "sprite.png"], ["img_pixel", "out/*.png", 3, 8, [0x1d, 0x2b, 0x53, 255]]])
C("shadow_drop_keep", "sprite-shadow", "Add a drop shadow under sprite.png, keep the canvas size.",
  "gst sprite-shadow sprite.png -o out --mode drop --keep-size", [["exit", 0], ["png", "out/*.png", 16, 16], ["img_differs", "out/*.png", "sprite.png"]])
C("palette_apply_builtin", "palette-apply", "Force sprite.png and grad.png onto the PICO-8 palette.",
  "gst palette-apply sprite.png grad.png -o out --palette pico8",
  [["exit", 0], ["glob", "out/*.png", 2], ["img_colors_in", "out/grad*.png", "pico8.hex"], ["img_colors_in", "out/sprite*.png", "pico8.hex"]])
C("palette_apply_hexfile", "palette-apply", "Quantise grad.png to the colours listed in pico8.hex.",
  "gst palette-apply grad.png -o out --palette pico8.hex", [["exit", 0], ["img_colors_in", "out/*.png", "pico8.hex"], ["png", "out/*.png", 32, 32]])
C("palette_swap_hue", "palette-swap", "Make a hue-shifted (180 degrees) variant of sprite.png.",
  "gst palette-swap sprite.png -o out --hue 180",
  [["exit", 0], ["png", "out/*.png", 16, 16], ["img_differs", "out/*.png", "sprite.png"], ["img_alpha_equal", "out/*.png", "sprite.png"]])
C("palette_extract", "palette-extract", "Extract a 4-colour palette swatch from grad.png.",
  "gst palette-extract grad.png -o pal -n 4", [["exit", 0], ["png", "pal_swatch.png"], ["exists", "pal.gpl"], ["count", "pal.hex", "\n", 4]])
C("team_outline", "team-outline", "Make a blue team variant of sprite.png, where #ff004d is the team-colour key.",
  "gst team-outline sprite.png -o out --team blue=#29adff --key '#ff004d'", [["exit", 0], ["glob_min", "out/*.png", 1]])
C("alpha_bleed", "alpha-bleed", "Bleed sprite colours into the transparent pixels so filtering does not make dark fringes.",
  "gst alpha-bleed sprite.png -o out",
  [["exit", 0], ["img_alpha_equal", "out/sprite.png|out", "sprite.png"], ["img_differs", "out/sprite.png|out", "sprite.png"]])
C("pixel_lint_clean", "pixel-lint", "Lint pixel.png as pixel art (max 4 colours), fail on problems.",
  "gst pixel-lint pixel.png --max-colors 4 --strict", [["exit", 0]])
C("pixel_lint_upscaled_warns", "pixel-lint", "sprite.png is a 4x-blocky image; strict lint should flag it.",
  "gst pixel-lint sprite.png --strict", [["exit_nonzero"], ["stdout_contains", "upscaled"]])
C("pixel_lint_too_many_colours", "pixel-lint", "Lint grad.png with a 4-colour limit; it should fail.",
  "gst pixel-lint grad.png --max-colors 4 --strict", [["exit_nonzero"]])
C("image_diff_same", "image-diff", "Diff sprite.png against itself.", "gst image-diff sprite.png sprite.png --max-changed 0", [["exit", 0]])
C("image_diff_changed", "image-diff", "Diff walk_0 against walk_1 and fail on any change.",
  "gst image-diff frames/walk_0.png frames/walk_1.png --max-changed 0", [["exit_nonzero"]])
C("texture_resize_max", "texture-resize", "Shrink odd.png (20x12) so its longest edge is 10 px.",
  "gst texture-resize odd.png -o out --max 10", [["exit", 0], ["png", "out/odd.png", 10, 6]])
C("texture_resize_pot", "texture-resize", "Make odd.png power-of-two sized.",
  "gst texture-resize odd.png -o out --pot", [["exit", 0], ["img_pot", "out/odd.png"]])
C("lut_identity_roundtrip", "lut-tool", "Make an identity LUT and apply it to grad.png; the image should not change.",
  "gst lut-tool identity --size 16 -o id.png && gst lut-tool apply grad.png --lut id.png -o same.png",
  [["exit", 0], ["img_close", "same.png", "grad.png", 2]])
C("lut_make_darker", "lut-tool", "Make a LUT that darkens by 0.2 and apply it to grad.png.",
  "gst lut-tool make --size 16 --brightness -0.2 -o dark.png && gst lut-tool apply grad.png --lut dark.png -o out.png",
  [["exit", 0], ["png", "out.png", 32, 32], ["img_mean_lt", "out.png", "grad.png"]])
C("colorblind_sim", "colorblind-sim", "Preview grad.png as seen with deuteranopia.",
  "gst colorblind-sim sim grad.png -o cb --type deutan", [["exit", 0], ["glob_min", "cb/*.png", 1]])
C("channel_pack_orm", "channel-pack", "Pack ao.png, rough.png and metal.png into one ORM texture.",
  "gst channel-pack pack -o orm.png --preset orm --ao ao.png --roughness rough.png --metallic metal.png",
  [["exit", 0], ["png", "orm.png", 16, 16], ["img_pixel", "orm.png", 5, 5, [200, 100, 0], 1]])
C("normal_bake", "normal-bake", "Bake a normal map from height.png.",
  "gst normal-bake height.png -o nb", [["exit", 0], ["png", "nb/*normal*.png", 32, 32]])
C("tex_gen_bricks", "tex-gen", "Generate a 32 px tileable brick texture with seed 1.",
  "gst tex-gen bricks -o b.png --size 32 --seed 1", [["exit", 0], ["png", "b.png", 32, 32]])
C("tex_gen_deterministic", "tex-gen", "Generating noise twice with the same seed must give identical files.",
  "gst tex-gen noise -o a.png --size 16 --seed 4 && gst tex-gen noise -o b.png --size 16 --seed 4",
  [["exit", 0], ["files_identical", "a.png", "b.png"], ["png", "a.png", 16, 16]])
C("tileset_gen_blob", "tileset-gen", "Build a 47-tile blob autotile sheet from two 16 px terrain fills.",
  "gst tileset-gen -o blob --tile 16 --inner in.png --outer outr.png",
  [["exit", 0], ["png", "blob.png"], ["img_size_multiple", "blob.png", 16], ["json", "blob.json"]],
  pre=["gst tex-gen bricks -o in.png --size 16 --seed 1", "gst tex-gen noise -o outr.png --size 16 --seed 2"])
C("tile_dedupe", "tile-dedupe", "Remove duplicate tiles from tiles_dup.png (16 px tiles, 2 columns).",
  "gst tile-dedupe tiles_dup.png --tile 16 -o dd --columns 2", [["exit", 0], ["png", "dd.png", 32, 16], ["json", "dd.json"]])
C("nine_slice_bake", "nine-slice", "Bake sprite.png as a 9-slice at 64x32 with 4 px insets.",
  "gst nine-slice sprite.png --insets 4,4,4,4 --size 64x32 -o ns.png", [["exit", 0], ["png", "ns.png", 64, 32]])
C("nine_slice_to_godot", "nine-slice-to-godot", "Make a Godot StyleBoxTexture from sprite.png with 4 px insets.",
  "gst nine-slice-to-godot sprite.png -o ns.tres --insets 4,4,4,4",
  [["exit", 0], ["starts", "ns.tres", "[gd_resource"], ["contains", "ns.tres", "StyleBoxTexture"], ["regex", "ns.tres", r"texture_margin_left = 4(\.0)?\b"]])
C("icon_gen", "icon-gen", "Generate an app icon set from a 1024 px master.",
  "gst icon-gen big/sprite.png -o icons --bg '#1d2b53'",
  [["exit", 0], ["png", "icons/web/icon-192.png", 192, 192]], pre=["gst sprite-scale sprite.png -o big --size 1024x1024"])
C("contact_sheet", "contact-sheet", "Make a contact sheet of all frames, 3 columns, 24x24 cells.",
  "gst contact-sheet frames/*.png -o cs.png --cell 24x24 --columns 3", [["exit", 0], ["png", "cs.png"]])
C("onion_skin", "onion-skin", "Make an onion-skin review of the walk frames.",
  "gst onion-skin walk -o onion.png --loop", [["exit", 0], ["png", "onion.png"]], pre=["mkdir walk && cp frames/walk_*.png walk/"])

# ---------------------------------------------------------------- sheets / atlases / animation
C("frames_to_sheet", "frames-to-sheet", "Turn the frames folder into a 4-column sheet without cropping.",
  "gst frames-to-sheet frames -o sh --columns 4 --no-crop", [["exit", 0], ["png", "sh.png", 64, 32], ["json", "sh.json"]])
C("sprite_slice_grid", "sprite-slice", "Slice sheet.png into 16x16 frames.",
  "gst sprite-slice sheet.png --grid 16x16 -o sl", [["exit", 0], ["glob", "sl/*.png", 4], ["all_png_size", "sl/*.png", 16, 16]])
C("gif_to_frames", "gif-to-frames", "Split anim.gif into PNG frames.",
  "gst gif-to-frames anim.gif -o gf", [["exit", 0], ["glob", "gf/*.png", 3]])
C("gif_optimize", "gif-optimize", "Shrink anim.gif to 8 colours.",
  "gst gif-optimize anim.gif -o small.gif --colors 8", [["exit", 0], ["img_frames", "small.gif", 3]])
C("atlas_pack", "atlas-pack", "Pack every frame in frames/ into one atlas.",
  PACK, [["exit", 0], ["png", "atlas.png"], ["img_pot", "atlas.png"], ["json_len", "atlas.json", "frames", 6]])
C("atlas_pack_notrim", "atlas-pack", "Pack frames/ without trimming and without power-of-two padding.",
  "gst atlas-pack frames -o atlas --no-trim --no-pot", [["exit", 0], ["json_len", "atlas.json", "frames", 6], ["json_eq", "atlas.json", "frames.walk_0.frame.w", 16]])
C("atlas_validate", "atlas-validate", "Validate the packed atlas against its PNG.", "gst atlas-validate atlas.json", [["exit", 0]], pre=[PACK])
C("atlas_unpack_untrim", "atlas-unpack", "Unpack the atlas back to full-size (untrimmed) frames.",
  "gst atlas-unpack atlas.json -o un --untrim", [["exit", 0], ["glob", "un/*.png", 6], ["all_png_size", "un/*.png", 16, 16]], pre=[PACK])
C("atlas_roundtrip_pixels", "atlas-unpack", "Pack then unpack untrimmed: walk_2 must come back pixel-identical.",
  "gst atlas-unpack atlas.json -o un --untrim", [["exit", 0], ["img_equal", "un/walk_2*.png", "frames/walk_2.png"]], pre=[PACK])
C("atlas_merge", "atlas-merge", "Merge two atlases into one.",
  "gst atlas-merge a1.json a2.json -o merged", [["exit", 0], ["png", "merged.png"], ["json_len", "merged.json", "frames", 6]],
  pre=["mkdir w i && cp frames/walk_* w/ && cp frames/idle_* i/", "gst atlas-pack w -o a1", "gst atlas-pack i -o a2"])
C("atlas_to_godot", "atlas-to-godot", "Write a Godot SpriteFrames .tres from the atlas.",
  "gst atlas-to-godot atlas.json -o frames.tres --res res://atlas.png",
  [["exit", 0], ["starts", "frames.tres", '[gd_resource type="SpriteFrames"'], ["count", "frames.tres", '[sub_resource type="AtlasTexture"', 6]], pre=[PACK])
C("atlas_to_godot_clips", "atlas-to-godot", "SpriteFrames with named walk and idle animations from a clips JSON.",
  "gst atlas-to-godot atlas.json -o frames.tres --clips clips.json --res res://atlas.png",
  [["exit", 0], ["contains", "frames.tres", '&"walk"'], ["contains", "frames.tres", '&"idle"']], pre=[PACK, CLIPS])
C("atlas_to_godot_trim_margin", "atlas-to-godot", "Trimmed frames must keep their 16x16 canvas in Godot (margin).",
  "gst atlas-to-godot atlas.json -o frames.tres --res res://atlas.png", [["exit", 0], ["regex", "frames.tres", r"margin = Rect2\("]], pre=[PACK])
C("anim_from_folder", "anim-from-folder", "Build clips from frames/: walk at 10 fps, idle plays once.",
  "gst anim-from-folder frames -o clips.json --pattern '{clip}_{frame}.png' --fps walk=10 --once idle",
  [["exit", 0], ["json_eq", "clips.json", "clips.walk.fps", 10], ["json_len", "clips.json", "clips.walk.frames", 4],
   ["json_eq", "clips.json", "clips.idle.loop", False], ["json_eq", "clips.json", "clips.walk.loop", True]])
C("anim_from_folder_glob", "anim-from-folder", "Set every clip starting with 'wa' to 6 fps using a glob.",
  "gst anim-from-folder frames -o clips.json --pattern '{clip}_{frame}.png' --fps 'wa*=6' --default-fps 8",
  [["exit", 0], ["json_eq", "clips.json", "clips.walk.fps", 6], ["json_eq", "clips.json", "clips.idle.fps", 8]])
C("frame_timing_check", "frame-timing-check", "Check the 12 fps clips against a 12 fps grid, strictly.",
  "gst frame-timing-check clips.json --fps 12 --strict --report ft.json", [["exit", 0], ["json", "ft.json"]], pre=[CLIPS + " --default-fps 12"])
C("spritesheet_gif", "spritesheet-gif", "Render the walk clip of the atlas to a GIF.",
  "gst spritesheet-gif atlas.json --clips clips.json --clip walk -o walk.gif", [["exit", 0], ["img_frames", "walk.gif", 4]], pre=[PACK, CLIPS])
C("sprite_angles", "sprite-angles", "Bake sprite.png at 8 rotation angles into a sheet.",
  "gst sprite-angles sprite.png -o ang.png --angles 8 --prefix s", [["exit", 0], ["png", "ang.png"], ["json_len", "ang.json", "frames", 8]])
C("sprite_flip_sheet", "sprite-flip-sheet", "Make a horizontally flipped copy of the atlas sheet.",
  "gst sprite-flip-sheet atlas.png atlas.json -o flip.png --horizontal", [["exit", 0], ["png", "flip.png"]], pre=["gst atlas-pack frames -o atlas --no-trim"])
C("hitbox_gen", "hitbox-gen", "Generate a hitbox from walk_0's alpha.",
  "gst hitbox-gen frames/walk_0.png -o hb.json", [["exit", 0], ["json", "hb.json"]])
C("hitbox_to_godot", "hitbox-to-godot", "Turn the hitboxes into a Godot Area2D scene with AABB shapes.",
  "gst hitbox-to-godot hb.json -o hb.tscn --shape aabb",
  [["exit", 0], ["starts", "hb.tscn", "[gd_scene"], ["contains", "hb.tscn", "Area2D"]], pre=["gst hitbox-gen frames/walk_0.png -o hb.json"])

# ---------------------------------------------------------------- maps / levels
C("dungeon_gen_bsp", "dungeon-gen", "Generate a 30x20 BSP dungeon with seed 3.",
  "gst dungeon-gen --mode bsp --size 30x20 --seed 3 -o d",
  [["exit", 0], ["ascii_grid", "d.txt", 30, 20], ["tiled_dims", "d.json", 30, 20], ["png", "d.png", 240, 160], ["json_len_min", "d.json", "tilesets", 1]])
C("dungeon_gen_deterministic", "dungeon-gen", "Same seed twice must give the same map.",
  "gst dungeon-gen --size 24x16 --seed 9 -o a && gst dungeon-gen --size 24x16 --seed 9 -o b", [["exit", 0], ["files_identical", "a.txt", "b.txt"]])
C("dungeon_gen_caves", "dungeon-gen", "Generate a 40x25 cave map.",
  "gst dungeon-gen --mode caves --size 40x25 --seed 2 -o c", [["exit", 0], ["ascii_grid", "c.txt", 40, 25], ["tiled_dims", "c.json", 40, 25]])
C("map_blank", "map-blank", "Make an empty 12x9 map with layers a and b.",
  "gst map-blank -o b.json --size 12x9 --tile 16 --layers a,b", [["exit", 0], ["tiled_dims", "b.json", 12, 9], ["json_len", "b.json", "layers", 2]])
C("map_fill_rect", "map-fill", "Fill a 3x2 rectangle at 0,0 of the ground layer with gid 2.",
  "gst map-fill map.json -o f.json --layer ground --gid 2 --rect 0,0,3,2",
  [["exit", 0], ["tiled_layer_count", "f.json", "ground", 2, 6], ["tiled_layer_count", "f.json", "ground", 1, 74], ["unchanged", "map.json"]])
C("map_mirror_h", "map-mirror", "Mirror the level horizontally.",
  "gst map-mirror f.json -o m.json --axis h", [["exit", 0], ["tiled_mirror_h", "f.json", "m.json", "ground"]],
  pre=["gst map-fill map.json -o f.json --layer ground --gid 2 --rect 0,0,3,2"])
C("map_rotate_90", "map-rotate", "Rotate the 10x8 map by 90 degrees.",
  "gst map-rotate map.json -o r.json --degrees 90", [["exit", 0], ["tiled_dims", "r.json", 8, 10], ["tiled_layer_count", "r.json", "walls", 2, 32]])
C("map_crop", "map-crop", "Crop the map to its used area.", "gst map-crop map.json -o c.json", [["exit", 0], ["tiled_dims", "c.json", 10, 8]])
C("map_stamp", "map-stamp", "Stamp a 2x2 pillar prefab (gid 2) onto the ground layer at 4,3.",
  "gst map-stamp map.json --prefab p2.json --at 4,3 --layer ground --tiles-only -o s.json",
  [["exit", 0], ["tiled_layer_count", "s.json", "ground", 2, 4]],
  pre=["gst map-blank -o p.json --size 2x2 --tile 16 --layers ground --tileset tiles.png --tilecount 2 --columns 2",
       "gst map-fill p.json -o p2.json --layer ground --gid 2 --rect 0,0,2,2"])
C("map_path_found", "map-path", "Find a path from the spawn object to the goal object, walls solid.",
  "gst map-path map.json --start-name spawn --goal-name goal --solid-layer walls --json p.json --fail-if-none",
  [["exit", 0], ["json", "p.json"]])
C("map_path_blocked", "map-path", "A wall column splits the map; the spawn-to-goal path must fail.",
  "gst map-path split.json --start-name spawn --goal-name goal --solid-layer walls --fail-if-none", [["exit_nonzero"]], pre=[SPLIT])
C("map_reach_all", "map-reach", "From tile 2,2, how many walkable tiles can I reach? (walls solid)",
  "gst map-reach map.json --start 2,2 --solid-layer walls --json r.json", [["exit", 0], ["stdout_regex", r"\b48 of 48 walkable"], ["json", "r.json"]])
C("map_reach_islands", "map-reach", "Fail if the split map has unreachable islands.",
  "gst map-reach split.json --start 2,2 --solid-layer walls --fail-on-islands", [["exit_nonzero"]], pre=[SPLIT])
C("tile_colliders", "tile-colliders", "Merge the solid wall tiles into collision rectangles.",
  "gst tile-colliders map.json --layer walls -o col.json", [["exit", 0], ["json", "col.json"]])
C("tile_colliders_to_godot", "tile-colliders-to-godot", "Make a StaticBody2D scene from the wall colliders.",
  "gst tile-colliders-to-godot col.json -o col.tscn",
  [["exit", 0], ["starts", "col.tscn", "[gd_scene"], ["contains", "col.tscn", "StaticBody2D"]], pre=["gst tile-colliders map.json --layer walls -o col.json"])
C("nav_to_godot", "nav-to-godot", "Make a NavigationRegion2D for the map, walls solid.",
  "gst nav-to-godot map.json -o nav.tscn --solid-layer walls",
  [["exit", 0], ["starts", "nav.tscn", "[gd_scene"], ["contains", "nav.tscn", "NavigationRegion2D"], ["contains", "nav.tscn", "NavigationPolygon"]])
C("map_to_godot", "map-to-godot", "Export the map as a Godot TileMapLayer scene plus TileSet.",
  "gst map-to-godot map.json -o m.tscn --write-tileset m_ts.tres",
  [["exit", 0], ["contains", "m.tscn", "TileMapLayer"], ["starts", "m_ts.tres", '[gd_resource type="TileSet"'], ["stdout_regex", r"\b112 cell"]])
C("map_objects_to_godot", "map-objects-to-godot", "Export the spawn and goal objects to a Godot scene.",
  "gst map-objects-to-godot map.json -o o.tscn", [["exit", 0], ["starts", "o.tscn", "[gd_scene"], ["contains", "o.tscn", "spawn"], ["contains", "o.tscn", "goal"]])
C("tile_preview", "tile-preview", "Render the map to a PNG.", "gst tile-preview map.json -o tp.png", [["exit", 0], ["png", "tp.png", 160, 128]])
C("tile_preview_scale", "tile-preview", "Render the map at 2x.", "gst tile-preview map.json -o tp.png --scale 2", [["exit", 0], ["png", "tp.png", 320, 256]])
C("tmx_gid_usage", "tmx-gid-usage", "Count GID usage in the map.", "gst tmx-gid-usage map.json --json g.json", [["exit", 0], ["json", "g.json"]])
C("tilemap_stats", "tilemap-stats", "Stats for the map; fail on empty layers.",
  "gst tilemap-stats map.json --csv s.csv --fail-on-empty-layer", [["exit", 0], ["csv_rows", "s.csv", 1]])
C("tilemap_stats_empty_layer", "tilemap-stats", "A blank map must fail --fail-on-empty-layer.",
  "gst tilemap-stats b.json --fail-on-empty-layer", [["exit_nonzero"]], pre=["gst map-blank -o b.json --size 4x4 --layers a"])
C("tmx_objects_csv", "tmx-objects-csv", "Export the map objects to CSV.", "gst tmx-objects-csv map.json -o o.csv", [["exit", 0], ["csv_rows", "o.csv", 2]])
C("tmx_to_json", "tmx-to-json", "Convert map.tmx to Tiled JSON.",
  "gst tmx-to-json map.tmx -o t.json", [["exit", 0], ["tiled_dims", "t.json", 4, 3], ["tiled_layer_count", "t.json", "ground", 2, 2]])
C("map_auto_layer_sample_rules", "map-auto-layer", "Apply the sample's floor rule table to my map.",
  "gst map-auto-layer map.json --rules %s/data/floor_rules.json --layer walls -o a.json" % SAMPLE, [["exit", 0], ["json_len", "a.json", "layers", 4]])
C("level_budget_sample", "level-budget", "Check the shipped Ember Crypt levels against their object budget.",
  "gst level-budget %s/project/levels/floor1.json %s/project/levels/floor2.json %s/project/levels/boss.json --budget %s/data/level_budget.json --fail-on-under" % ((SAMPLE,) * 4), [["exit", 0]])
C("tmx_props_lint_sample", "tmx-props-lint", "Lint the shipped Ember Crypt level object properties.",
  "gst tmx-props-lint %s/project/levels/floor1.json %s/project/levels/boss.json --schema %s/data/map_props.schema.json" % ((SAMPLE,) * 3), [["exit", 0]])

# ---------------------------------------------------------------- Godot project / data
C("godot_res_lint_clean", "godot-res-lint", "Lint my Godot project for missing res:// paths.", "gst godot-res-lint proj --strict", [["exit", 0]])
C("godot_res_lint_missing", "godot-res-lint", "The broken project references a missing PNG; lint must fail and name it.",
  "gst godot-res-lint proj_broken --strict", [["exit_nonzero"], ["stdout_contains", "missing.png"]])
C("asset_unused", "asset-unused", "Which files in proj/ does nothing reference?",
  "gst asset-unused proj --json u.json", [["exit", 0], ["json_eq", "u.json", "unused", ["art/orphan.png"]]])
C("asset_unused_strict", "asset-unused", "Fail CI when unused assets exist.", "gst asset-unused proj --strict", [["exit", 1]])
C("input_map_lint", "input-map-lint", "Lint the input map in project.godot.", "gst input-map-lint proj/project.godot --json im.json", [["json", "im.json"]])
C("import_presets_snippet", "godot-import-presets", "Print the pixel-art project.godot defaults.",
  "gst godot-import-presets --project-snippet", [["exit", 0], ["stdout_regex", r"^\[\w+\]"]])
C("data_to_godot", "data-to-godot", "Turn enemies.csv into a Godot Resource plus script.",
  "gst data-to-godot enemies.csv -o e.tres --script e.gd",
  [["exit", 0], ["starts", "e.tres", "[gd_resource"], ["contains", "e.tres", "Slime"], ["contains", "e.gd", "extends"]])
C("texture_budget", "texture-budget", "Estimate VRAM for the project textures.", "gst texture-budget proj --json tb.json", [["exit", 0], ["json", "tb.json"]])
C("texture_budget_over", "texture-budget", "Fail when textures exceed a tiny budget.", "gst texture-budget proj --fail-over-mb 0.000001", [["exit_nonzero"]])
C("asset_manifest_verify", "asset-manifest", "Build a manifest of proj/ and verify it.",
  "gst asset-manifest build proj -o man.json && gst asset-manifest verify man.json proj", [["exit", 0], ["json", "man.json"]])
C("asset_manifest_detects_change", "asset-manifest", "After editing a file, manifest verify must fail.",
  "gst asset-manifest verify man.json proj", [["exit_nonzero"]],
  pre=["gst asset-manifest build proj -o man.json", "cp frames/walk_1.png proj/art/hero.png"])
C("asset_rename_apply", "asset-rename", "Prefix every frame filename with hero_.",
  "gst asset-rename run frames --prefix hero_ --apply", [["exit", 0], ["exists", "frames/hero_walk_0.png"], ["glob", "frames/walk_*.png", 0]])
C("asset_rename_dry_run", "asset-rename", "Preview the hero_ prefix rename without touching files.",
  "gst asset-rename run frames --prefix hero_", [["exit", 0], ["exists", "frames/walk_0.png"], ["glob", "frames/hero_*", 0]])
C("game_data_lint_sample", "game-data-lint", "Lint the Ember Crypt data tables against their schema.",
  "gst game-data-lint %s/data/schema.json --root %s/data --strict" % (SAMPLE, SAMPLE), [["exit", 0]])
C("drop_sim_expect_pass", "drop-sim", "A table that always drops a coin: assert coin chance is 100%.",
  "gst drop-sim loot.json --trials 2000 --seed 1 --expect t:coin:1:1 --json ds.json", [["exit", 0], ["json", "ds.json"]],
  pre=["""echo '{"tables": {"t": {"entries": [{"item": "coin", "weight": 1}]}}}' > loot.json"""])
C("drop_sim_expect_fail", "drop-sim", "Assert the always-coin table drops coins at most 50%: must fail.",
  "gst drop-sim loot.json --trials 2000 --seed 1 --expect t:coin:0:0.5", [["exit_nonzero"]],
  pre=["""echo '{"tables": {"t": {"entries": [{"item": "coin", "weight": 1}]}}}' > loot.json"""])

# ---------------------------------------------------------------- localisation / fonts
C("loc_check", "loc-check", "Validate loc.csv.", "gst loc-check loc.csv", [["exit", 0]])
C("loc_placeholder_ok", "loc-placeholder-lint", "Check placeholders match across languages.", "gst loc-placeholder-lint loc.csv", [["exit", 0]])
C("loc_placeholder_missing", "loc-placeholder-lint", "German drops {n} in loc_bad.csv: must fail.", "gst loc-placeholder-lint loc_bad.csv", [["exit_nonzero"]])
C("loc_key_lint", "loc-key-lint", "Lint key naming with _ as separator.", "gst loc-key-lint loc.csv --separator _", [["exit", 0]])
C("loc_stats", "loc-stats", "Summarise loc.csv.", "gst loc-stats loc.csv --json ls.json", [["exit", 0], ["json", "ls.json"]])
C("pseudoloc", "pseudoloc", "Add a pseudo-localised en_XA column.",
  "gst pseudoloc loc.csv -o p.csv --column en --new-column en_XA", [["exit", 0], ["csv_header_has", "p.csv", ["id", "en", "en_XA"]], ["csv_rows", "p.csv", 3]])
C("loc_sort", "loc-sort", "Sort loc.csv by key.", "gst loc-sort loc.csv -o s.csv", [["exit", 0], ["csv_col_sorted", "s.csv", 3]])
C("loc_merge", "loc-merge", "Merge loc.csv and loc_b.csv; keys only in one file are fine.",
  "gst loc-merge loc.csv loc_b.csv -o m.csv --no-fail", [["exit", 0], ["csv_rows", "m.csv", 4]])
C("loc_merge_missing_keys_exit", "loc-merge", "Without --no-fail, keys missing from one side make the merge exit 1 (per --help).",
  "gst loc-merge loc.csv loc_b.csv -o m.csv", [["exit", 1], ["csv_rows", "m.csv", 4]])
C("loc_to_godot", "loc-to-godot", "Write a Godot translation CSV for en and de.",
  "gst loc-to-godot loc.csv -o g.csv --key id --langs en,de", [["exit", 0], ["csv_header_has", "g.csv", ["en", "de"]], ["csv_rows", "g.csv", 3]])
C("loc_fit_ok", "loc-fit", "Do my strings fit 300 px at 11 px DejaVu?",
  "gst loc-fit loc.csv --font font.ttf --size 11 --limit-default 300 --max-lines 1", [["exit", 0]])
C("loc_fit_too_narrow", "loc-fit", "With a 5 px limit every string overflows: must fail.",
  "gst loc-fit loc.csv --font font.ttf --size 11 --limit-default 5 --max-lines 1", [["exit_nonzero"]])
C("font_subset", "font-subset", "Subset DejaVu Sans to just ABC.",
  "gst font-subset font.ttf -o sub.ttf --chars ABC", [["exit", 0], ["font_magic", "sub.ttf"], ["smaller", "sub.ttf", "font.ttf"]])
C("font_check_ok", "font-check", "Does DejaVu cover every character in chars.txt?", "gst font-check chars.txt --font font.ttf", [["exit", 0]])
C("font_check_missing", "font-check", "The ABC-only subset cannot cover chars.txt: must fail.",
  "gst font-check chars.txt --font sub.ttf", [["exit_nonzero"]], pre=["gst font-subset font.ttf -o sub.ttf --chars ABC"])
C("bmfont_gen", "bmfont-gen", "Bake a 16 px BMFont with the characters ABC.",
  "gst bmfont-gen --font font.ttf --size 16 --chars ABC -o bm", [["exit", 0], ["regex", "bm.fnt", r"chars count=\d+"], ["glob_min", "bm*.png", 1]])
C("font_to_godot", "font-to-godot", "Make a Godot Theme from the BMFont.",
  "gst font-to-godot bm.fnt -o th.tres", [["exit", 0], ["starts", "th.tres", "[gd_resource"]], pre=["gst bmfont-gen --font font.ttf --size 16 --chars ABC -o bm"])
C("font_preview", "font-preview", "Render a review sheet of the font at 12 px.", "gst font-preview font.ttf -o fp.png --sizes 12", [["exit", 0], ["png", "fp.png"]])

# ---------------------------------------------------------------- audio
C("sfx_gen_count", "sfx-gen", "Generate 3 coin sounds with seed 5.", "gst sfx-gen coin -o g -n 3 --seed 5", [["exit", 0], ["glob", "g/*.wav", 3]])
C("sfx_gen_deterministic", "sfx-gen", "The same seed must give byte-identical sounds.",
  "gst sfx-gen laser -o a -n 1 --seed 5 && gst sfx-gen laser -o b -n 1 --seed 5", [["exit", 0], ["files_identical", "a/*.wav", "b/*.wav"]])
C("sfx_pitch_octave", "sfx-pitch", "Pitch tone.wav up an octave (duration halves).",
  "gst sfx-pitch tone.wav -o hi.wav --semitones 12", [["exit", 0], ["wav", "hi.wav", {"frames_range": [10800, 11250], "rate": 44100}]])
C("sfx_pitch_ratio", "sfx-pitch", "Play tone.wav at half speed (ratio 0.5, duration doubles).",
  "gst sfx-pitch tone.wav -o lo.wav --ratio 0.5", [["exit", 0], ["wav", "lo.wav", {"frames_range": [43650, 44550]}]])
C("sfx_reverse", "sfx-reverse", "Reverse tone.wav.", "gst sfx-reverse tone.wav -o r.wav", [["exit", 0], ["wav_reversed", "tone.wav", "r.wav"]])
C("sfx_normalize_peak", "sfx-normalize", "Normalise tone.wav to -3 dBFS peak.",
  "gst sfx-normalize tone.wav -o n.wav --peak -3", [["exit", 0], ["wav_peak_db", "n.wav", -3.0, 0.1]])
C("wav_gain", "wav-gain", "Turn tone.wav down 6 dB.", "gst wav-gain tone.wav --gain -6 -o g.wav", [["exit", 0], ["wav_peak_db", "g.wav", -12.04, 0.1]])
C("wav_mono", "wav-mono", "Fold the stereo tone to mono.",
  "gst wav-mono tone_stereo.wav -o m.wav", [["exit", 0], ["wav", "m.wav", {"channels": 1, "frames": 22050}]])
C("wav_resample", "wav-resample", "Resample tone.wav to 22050 Hz.",
  "gst wav-resample tone.wav --rate 22050 -o rs.wav", [["exit", 0], ["wav", "rs.wav", {"rate": 22050, "frames_range": [11015, 11035]}]])
C("wav_pad_head_tail", "wav-pad", "Add 0.5 s silence before and 0.25 s after tone.wav.",
  "gst wav-pad tone.wav -o p.wav --head 0.5 --tail 0.25", [["exit", 0], ["wav", "p.wav", {"frames_range": [55120, 55130]}]])
C("wav_pad_to_duration", "wav-pad", "Pad tone.wav to last 1 second.",
  "gst wav-pad tone.wav -o p.wav --to-duration 1.0", [["exit", 0], ["wav", "p.wav", {"frames_range": [44095, 44105]}]])
C("wav_trim_silence", "wav-trim", "Trim the leading/trailing silence off padded.wav.",
  "gst wav-trim padded.wav -o tr", [["exit", 0], ["wav", "tr/*.wav", {"frames_range": [13000, 20000]}]])
C("wav_fade", "wav-fade", "Fade tone.wav in and out over 0.1 s.",
  "gst wav-fade tone.wav -o f.wav --in 0.1 --out-dur 0.1", [["exit", 0], ["wav", "f.wav", {"frames": 22050}], ["wav_first_abs_le", "f.wav", 0.001]])
C("wav_loop_meta_roundtrip", "wav-loop-meta", "Set loop points 100..1000 on tone.wav and show them.",
  "gst wav-loop-meta set tone.wav --start 100 --end 1000 -o lm.wav && gst wav-loop-meta show lm.wav",
  [["exit", 0], ["stdout_regex", r"\b100\b"], ["stdout_regex", r"\b1000\b"]])
C("wav_loop_snap", "wav-loop-snap", "Cut tone.wav to samples 0..9999 with no loop metadata.",
  "gst wav-loop-snap tone.wav -o ls.wav --start 0 --end 9999 --no-meta", [["exit", 0], ["wav", "ls.wav", {"frames_range": [9999, 10000]}]])
C("wav_loud_apply", "wav-loud-apply", "Bring quiet.wav to -16 LUFS with a -1 dBTP ceiling.",
  "gst wav-loud-apply quiet.wav -o la --target -16 --max-true-peak -1",
  [["exit", 0], ["wav_peak_le", "la/*.wav", -0.9], ["wav_peak_ge", "la/*.wav", -20.0]])
C("wav_batch_meta", "wav-batch-meta", "Loudness report for two WAVs as CSV.",
  "gst wav-batch-meta tone.wav quiet.wav --csv wb.csv --quiet", [["csv_rows", "wb.csv", 2]])
C("cue_sheet", "cue-sheet", "Build a cue sheet for two WAVs.", "gst cue-sheet tone.wav quiet.wav --csv cs.csv", [["exit", 0], ["csv_rows", "cs.csv", 2]])
C("sfx_envelope", "sfx-envelope", "Apply an ADSR (10/50/0.5/50 ms) to tone.wav.",
  "gst sfx-envelope tone.wav -o env --attack-ms 10 --decay-ms 50 --sustain 0.5 --release-ms 50",
  [["exit", 0], ["wav", "env/*.wav", {"frames": 22050}], ["wav_first_abs_le", "env/*.wav", 0.001]])
C("sfx_variants", "sfx-variants", "Make 3 seeded variations of tone.wav.", "gst sfx-variants tone.wav -o var -n 3 --seed 1", [["exit", 0], ["glob", "var/*.wav", 3]])
C("sfx_mix", "sfx-mix", "Mix tone.wav and quiet.wav (offset 250 ms), normalised to the -1 dB peak.",
  "gst sfx-mix mix.json -o mix.wav", [["exit", 0], ["wav", "mix.wav", {"frames_range": [33075, 50000]}], ["wav_peak_db", "mix.wav", -1.0, 0.15]],
  pre=["""echo '{"sample_rate": 44100, "channels": 1, "normalize": true, "peak_db": -1.0, "tail_ms": 100, "layers": [{"file": "tone.wav", "offset_ms": 0}, {"file": "quiet.wav", "offset_ms": 250}]}' > mix.json"""])
C("sfx_mix_peak_ceiling", "sfx-mix", "Mix tone.wav with a -10 dB peak ceiling.",
  "gst sfx-mix mix.json -o mix.wav", [["exit", 0], ["wav_peak_db", "mix.wav", -10.0, 0.15]],
  pre=["""echo '{"sample_rate": 44100, "channels": 1, "peak_db": -10.0, "layers": [{"file": "tone.wav"}]}' > mix.json"""])
C("sfx_bank_pack", "sfx-bank", "Pack two WAVs into one audio sprite bank.",
  "gst sfx-bank pack tone.wav quiet.wav -o bank", [["exit", 0], ["wav", "bank.wav", {"frames_range": [44100, 200000]}], ["json", "bank.json"]])
C("sfx_spectrogram", "sfx-spectrogram", "Spectrogram of tone.wav.", "gst sfx-spectrogram tone.wav -o sp", [["exit", 0], ["glob_min", "sp/*.png", 1]])

# ---------------------------------------------------------------- 3D
C("obj_validate", "obj-validate", "Validate cube.obj.", "gst obj-validate cube.obj --strict", [["exit", 0]])
C("obj_triangulate", "obj-triangulate", "Triangulate cube.obj.", "gst obj-triangulate cube.obj -o tri.obj", [["exit", 0], ["obj_faces", "tri.obj", 12, 3]])
C("obj_bounds_box", "obj-bounds", "Report cube.obj bounds and write its AABB as an OBJ.",
  "gst obj-bounds cube.obj -o b.json --box box.obj", [["exit", 0], ["json", "b.json"], ["obj_faces", "box.obj", 12, 3]])
C("obj_to_glb", "obj-to-glb", "Convert cube.obj to GLB.", "gst obj-to-glb cube.obj -o glb", [["exit", 0], ["glb_magic", "glb/*.glb"]])
C("gltf_inspect", "gltf-inspect", "Inspect the converted GLB.", "gst gltf-inspect glb/*.glb", [["exit", 0]], pre=["gst obj-to-glb cube.obj -o glb"])

if __name__ == "__main__":
    import json, os
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "cases.jsonl"), "w") as f:
        for c in CASES:
            f.write(json.dumps(c) + "\n")
    print(len(CASES), "cases,", len({c["tool"] for c in CASES}), "tools")
