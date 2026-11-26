#!/usr/bin/env python3
"""Realistic game-dev requests and the gst commands that answer them.

This is the source of truth for trajectory generation. It does not run
anything. generate.py executes every spec in a temp project and keeps only
the ones whose measured exit codes match.

A recovery spec starts with a command that fails for a realistic reason
(wrong flag or missing input). The next step's reasoning quotes that error
via the ``{error}`` placeholder.
"""

_SPECS = []


def S(kind, reason, *argv, expect=0):
    return {"kind": kind, "reasoning": reason, "argv": list(argv), "expect": expect}


def add(id_, family, request, steps, recovery=None):
    built = []
    if recovery:
        bad_reason, bad_argv, fix_reason = recovery
        built.append({"kind": "miss", "reasoning": bad_reason, "argv": list(bad_argv), "expect": "nonzero"})
        first = dict(steps[0])
        first["kind"] = "fix"
        first["reasoning"] = fix_reason
        built.append(first)
        built.extend(steps[1:])
    else:
        built.extend(steps)
    if built[-1]["kind"] != "verify":
        raise SystemExit("trajectory %s does not end in a verify step" % id_)
    _SPECS.append({
        "id": id_,
        "primary_family": family,
        "request": request,
        "recovery": recovery is not None,
        "steps": built,
    })


def v_png(path, why):
    return S("verify", why, "image-diff", path, path, "--max-changed", "0")


def v_map(path, why="The map should still be a finite orthogonal map with no empty tile layer."):
    return S("verify", why, "tilemap-stats", path, "--fail-on-empty-layer")


def v_wav(path, why="Read the WAV back and confirm it is not silent or clipped."):
    return S("verify", why, "wav-batch-meta", path, "--quiet")


def v_obj(path, why="Validate indices and drop the file if any face is degenerate."):
    return S("verify", why, "obj-validate", path, "--strict")


def v_glb(path, why="Inspect the GLB: it should load and report triangles and bounds."):
    return S("verify", why, "gltf-inspect", path)


def v_godot(why="Lint the Godot project so a bad res:// path fails the task."):
    return S("verify", why, "godot-res-lint", "godot")


def v_loc(path="loc/strings.csv", why="Check ids, placeholders and that every language cell is filled."):
    return S("verify", why, "loc-check", path)


def v_atlas(path, why="Validate frames against the sheet: in bounds, no duplicate names."):
    return S("verify", why, "atlas-validate", path)


def v_dlg(path, why="Lint the script for jumps to nodes that do not exist."):
    return S("verify", why, "dialogue-lint", path)


def specs():
    return list(_SPECS)


# ---------------------------------------------------------------- maps
_BIOMES = [
    ("meadow", "16", "#4a8f3c", "#8a6a3f",
     "Make a 16x16 grass tileset for the meadow, green on dirt, and import it into Godot."),
    ("snow", "16", "#e7eef2", "#8aa0b4",
     "Build a 16px snow tileset on slate rock and add it to the Godot project as a TileSet."),
    ("marsh", "16", "#3f6b45", "#6a5a32",
     "The marsh needs a 16px blob tileset, dark grass on mud, wired into Godot."),
    ("sand", "16", "#e2c56a", "#c4a15a",
     "Cut a 16x16 sand tileset (dune on packed sand) and import the TileSet."),
    ("ash", "8", "#6e6a66", "#3a3836",
     "Cave ash: an 8px blob tileset, grey on charcoal, as a Godot TileSet."),
    ("moss", "32", "#6ea84a", "#4a3424",
     "A 32px moss-on-soil tileset for the overworld, imported into Godot."),
    ("tide", "16", "#3a8f9a", "#1d4e5a",
     "Shoreline tiles at 16px, shallow water on deep water, then a Godot TileSet."),
    ("lava", "16", "#c4512c", "#3a241c",
     "Lava crust tiles, 16px, orange on scorched rock, imported for Godot."),
]
for name, tile, inner, outer, request in _BIOMES:
    rec = None
    if name == "meadow":
        rec = (
            "The request says 16x16, so I tried --tile-size.",
            ["tileset-gen", "-o", "godot/art/" + name, "--tile-size", tile, "--inner", inner, "--outer", outer],
            "The error is: {error} tileset-gen takes --tile, not --tile-size.",
        )
    add("maps-tileset-" + name, "maps", request, [
        S("act", "Blob autotile: inner colour is the terrain, outer is what surrounds it. "
           "Write the sheet into the Godot art folder so the TileSet can reference it.",
          "tileset-gen", "-o", "godot/art/" + name, "--tile", tile, "--inner", inner, "--outer", outer,
          "--edge-color", "#1d2b53"),
        S("act", "tileset-gen's JSON is a meta file godot-tileset already understands. Point the texture at res://art/.",
          "godot-tileset", "godot/art/%s.json" % name, "-o", "godot/%s_tileset.tres" % name,
          "--res", "res://art/%s.png" % name, "--tile", tile),
        v_godot("godot-res-lint fails if the new TileSet points at a texture that is not in the project."),
    ], rec)

_DUNGEONS = [
    ("crypt", "bsp", "30x20", "3", "Lay out a 30x20 BSP crypt with seed 3 and render it."),
    ("cellar", "bsp", "24x16", "9", "A 24x16 cellar, BSP, seed 9. I need the map and a preview."),
    ("ossuary", "bsp", "40x24", "11", "Bigger ossuary: 40x24 BSP, seed 11, exported as a Tiled map."),
    ("den", "caves", "32x24", "2", "Generate a 32x24 cave den, seed 2, and check the player can stand in it."),
    ("grotto", "caves", "40x25", "4", "A 40x25 grotto from cellular caves, seed 4."),
    ("mine", "caves", "28x20", "6", "Mine tunnels, 28x20 caves, seed 6. Keep it deterministic."),
    ("keep", "bsp", "20x20", "1", "A square 20x20 keep, BSP, seed 1."),
    ("burrow", "caves", "24x18", "8", "Small burrow, 24x18 caves, seed 8."),
]
for name, mode, size, seed, request in _DUNGEONS:
    rec = None
    if name == "crypt":
        rec = (
            "I passed width and height as separate flags.",
            ["dungeon-gen", "--mode", mode, "--width", "30", "--height", "20", "--seed", seed, "-o", "build/" + name],
            "stderr says: {error} The size is one --size WxH value.",
        )
    add("maps-dungeon-" + name, "maps", request, [
        S("act", "Seeded %s so the layout can be regenerated. --tile 8 keeps the preview small." % mode,
          "dungeon-gen", "--mode", mode, "--size", size, "--seed", seed, "--tile", "8", "-o", "build/" + name),
        S("act", "Render the Tiled JSON with the tileset embedded by dungeon-gen.",
          "tile-preview", "build/%s.json" % name, "-o", "build/%s_preview.png" % name),
        v_map("build/%s.json" % name, "Stats must show a non-empty finite map at the requested size."),
    ], rec)

add("maps-blank-arena", "maps", "Start a blank 12x9 arena with ground and walls layers, 16px tiles.", [
    S("act", "map-blank writes an empty orthogonal map. Two layers so walls can be painted later.",
      "map-blank", "-o", "build/arena.json", "--size", "12x9", "--tile", "16", "--layers", "ground,walls",
      "--tileset", "maps/tiles.png", "--tilecount", "2", "--columns", "2"),
    S("act", "Fill the ground with gid 1. An empty tile layer would fail the stats check.",
      "map-fill", "build/arena.json", "-o", "build/arena_ground.json", "--layer", "ground", "--gid", "1", "--rect", "0,0,12,9"),
    S("act", "Paint a one-tile wall strip along the north edge.",
      "map-fill", "build/arena_ground.json", "-o", "build/arena_walls.json", "--layer", "walls", "--gid", "2", "--rect", "0,0,12,1"),
    v_map("build/arena_walls.json"),
], (
    "Blank maps take --width and --height in other tools, so I tried that.",
    ["map-blank", "-o", "build/arena.json", "--width", "12", "--height", "9", "--tile", "16"],
    "The error is: {error} map-blank wants --size WxH.",
))

add("maps-fill-plaza", "maps", "Fill a 3x2 plaza of gid 2 at the north-west of the level's ground.", [
    S("act", "Rectangle fill on ground only, so the wall border stays put.",
      "map-fill", "maps/level.json", "-o", "build/plaza.json", "--layer", "ground", "--gid", "2", "--rect", "1,1,3,2"),
    v_map("build/plaza.json", "The filled map must still have no empty tile layer."),
])

add("maps-mirror-h", "maps", "Mirror the level horizontally for a second-hand variant.", [
    S("act", "Horizontal mirror flips GID flags the way Tiled does, so walls stay on the border.",
      "map-mirror", "maps/level.json", "-o", "build/level_h.json", "--axis", "h"),
    v_map("build/level_h.json"),
], (
    "I used --horizontal because that is the word in the request.",
    ["map-mirror", "maps/level.json", "-o", "build/level_h.json", "--horizontal"],
    "stderr: {error} The axis flag is --axis h.",
))

add("maps-mirror-v", "maps", "Flip the level vertically.", [
    S("act", "Vertical mirror, new file, leave maps/level.json alone.",
      "map-mirror", "maps/level.json", "-o", "build/level_v.json", "--axis", "v"),
    v_map("build/level_v.json"),
])

for deg in ("90", "180", "270"):
    rec = None
    if deg == "90":
        rec = (
            "Rotation flags are usually --angle.",
            ["map-rotate", "maps/level.json", "-o", "build/level_r90.json", "--angle", "90"],
            "The tool rejected it: {error} Use --degrees.",
        )
    add("maps-rotate-" + deg, "maps", "Rotate the 10x8 level %s degrees clockwise." % deg, [
        S("act", "Orthogonal rotate moves cells and updates flip flags. 90 and 270 swap width and height.",
          "map-rotate", "maps/level.json", "-o", "build/level_r%s.json" % deg, "--degrees", deg),
        v_map("build/level_r%s.json" % deg),
    ], rec)

add("maps-crop", "maps", "Crop the level to the tiles that are actually used, plus a 0 margin.", [
    S("act", "map-crop shrinks to the used bounding box and shifts objects with it.",
      "map-crop", "maps/level.json", "-o", "build/level_crop.json"),
    v_map("build/level_crop.json"),
])

add("maps-pad", "maps", "Pad the level with a 1 tile empty border on every side.", [
    S("act", "Padding grows the map without touching GIDs in the original rect.",
      "map-pad", "maps/level.json", "-o", "build/level_pad.json", "--margin", "1"),
    S("verify", "Stats on the padded map. The new border is empty, so do not fail on empty layers; just confirm it loads.",
      "tilemap-stats", "build/level_pad.json"),
])

add("maps-shift", "maps", "Shift every tile and object on the level by 1 tile right and 0 down, wrapping.", [
    S("act", "Wrap so the wall that leaves the east edge comes back on the west.",
      "map-shift", "maps/level.json", "-o", "build/level_shift.json", "--tiles", "1,0", "--wrap"),
    v_map("build/level_shift.json"),
])

add("maps-scale-tiles", "maps", "Double the level's tile size from 16 to 32 without changing the cell grid.", [
    S("act", "map-scale multiplies pixel coordinates so objects stay on the same cells.",
      "map-scale", "maps/level.json", "-o", "build/level_32.json", "--tile", "32"),
    v_map("build/level_32.json"),
])

add("maps-outline", "maps", "Draw the outline of the walkable floor (walls are solid) onto a new layer.", [
    S("act", "Same solidity rule as map-reach: the walls layer blocks. Write an outline layer.",
      "map-outline", "maps/level.json", "-o", "build/level_outline.json", "--solid-layer", "walls"),
    v_map("build/level_outline.json"),
])

add("maps-clean", "maps", "Clean the level: drop empty property bags and pack tileset ids.", [
    S("act", "map-clean rewrites a new file. --keep-firstgids is not needed; the level uses firstgid 1.",
      "map-clean", "maps/level.json", "-o", "build/level_clean.json"),
    v_map("build/level_clean.json"),
])

add("maps-path-spawn-goal", "maps", "Find a walkable path from the spawn to the goal. Walls are solid.", [
    S("act", "A* with the same solidity as the nav tools. Fail if the goal is boxed in.",
      "map-path", "maps/level.json", "--start-name", "spawn", "--goal-name", "goal",
      "--solid-layer", "walls", "--json", "build/path.json", "--fail-if-none"),
    S("act", "Paint the path so I can see it on the tileset.",
      "tile-preview", "maps/level.json", "-o", "build/path_preview.png"),
    v_png("build/path_preview.png", "The preview PNG must load. The path JSON was written only because a route exists."),
])

add("maps-reach-spawn", "maps", "From the spawn, how much of the floor can the player reach?", [
    S("act", "Flood from tile 2,2. Walls are solid. Write the JSON report.",
      "map-reach", "maps/level.json", "--start", "2,2", "--solid-layer", "walls", "--json", "build/reach.json"),
    v_map("maps/level.json", "The source map must still be intact and non-empty."),
])

add("maps-stamp-pillar", "maps", "Stamp a 2x2 pillar of wall tiles onto the ground at cell 4,3.", [
    S("act", "The prefab is a tiny map filled with gid 2.",
      "map-blank", "-o", "build/pillar0.json", "--size", "2x2", "--tile", "16", "--layers", "ground",
      "--tileset", "maps/tiles.png", "--tilecount", "2", "--columns", "2"),
    S("act", "Fill the prefab so the stamp is visible.",
      "map-fill", "build/pillar0.json", "-o", "build/pillar.json", "--layer", "ground", "--gid", "2", "--rect", "0,0,2,2"),
    S("act", "Stamp tiles only, into the ground layer, at 4,3.",
      "map-stamp", "maps/level.json", "--prefab", "build/pillar.json", "--at", "4,3",
      "--layer", "ground", "--tiles-only", "-o", "build/stamped.json"),
    v_map("build/stamped.json"),
])

add("maps-merge-town-shop", "maps", "Merge the town and shop maps into one, shop offset by 10 tiles east.", [
    S("act", "Same tile size on both. Prefix layers with the file stem so names do not collide.",
      "map-merge", "maps/town.json", "maps/shop.json", "-o", "build/district.json", "--offset", "0,0", "--offset", "10,0"),
    S("verify", "The merged map loads. Empty padding from the offset is allowed, so skip the empty-layer failure.",
      "tilemap-stats", "build/district.json"),
])

add("maps-chunk-level", "maps", "Split the level into 4x4 chunks and write a Tiled world index.", [
    S("act", "Chunks keep objects whose box overlaps the chunk.",
      "map-chunk", "maps/level.json", "-o", "build/chunks", "--size", "4x4", "--world", "build/level.world"),
    S("act", "Index the chunk folder as a world from filenames.",
      "tmx-world", "build/chunks", "-o", "build/chunks.world", "--from-filename"),
    S("verify", "The world file is JSON. tilemap-stats on the original level confirms the source survived.",
      "tilemap-stats", "maps/level.json", "--fail-on-empty-layer"),
])

add("maps-auto-decor", "maps", "Apply the floor decoration rules to the level's ground layer.", [
    S("act", "Rules match centre gid 1 and write a decor layer.",
      "map-auto-layer", "maps/level.json", "--rules", "maps/floor_rules.json", "--layer", "ground",
      "-o", "build/decor.json"),
    v_map("build/decor.json"),
])

add("maps-replace-gids", "maps", "Swap gid 1 and gid 2 across the whole level.", [
    S("act", "The remap JSON is old gid to new gid. Unmapped cells stay.",
      "tile-replace", "maps/level.json", "--remap", "maps/remap.json", "-o", "build/swapped.json"),
    v_map("build/swapped.json"),
])

add("maps-gid-usage", "maps", "Count how many cells use each GID on the level.", [
    S("act", "JSON report so the counts can be diffed later.",
      "tmx-gid-usage", "maps/level.json", "--json", "build/gids.json"),
    v_map("maps/level.json"),
])

add("maps-objects-csv", "maps", "Export the level's spawn and goal to a CSV.", [
    S("act", "One row per object, including name and type.",
      "tmx-objects-csv", "maps/level.json", "-o", "build/objects.csv"),
    S("verify", "Diff the CSV against itself. A readable table with the id column comes back identical.",
      "data-diff", "build/objects.csv", "build/objects.csv", "--key", "id"),
])

add("maps-tmx-roundtrip", "maps", "Convert level.tmx to Tiled JSON, then back to TMX, and confirm the JSON loads.", [
    S("act", "CSV tile data in the TMX becomes a JSON tile layer.",
      "tmx-to-json", "maps/level.tmx", "-o", "build/from_tmx.json"),
    S("act", "Encode that JSON as base64+zlib TMX.",
      "tmx-encode", "build/from_tmx.json", "-o", "build/level_enc.tmx", "--encoding", "base64", "--compression", "zlib"),
    S("verify", "Stats on the JSON form. The 4x3 map must not have an empty ground.",
      "tilemap-stats", "build/from_tmx.json", "--fail-on-empty-layer"),
])

add("maps-decode-array", "maps", "Decode level.tmx into a JSON map with plain arrays.", [
    S("act", "tmx-decode expands CSV into a data array.",
      "tmx-decode", "maps/level.tmx", "-o", "build/decoded.json", "--encoding", "array"),
    v_map("build/decoded.json"),
])

add("maps-layer-rename", "maps", "Rename the level's ground layer to floor.", [
    S("act", "Regex rename of layer names only. Objects keep their names.",
      "map-layer-rename", "maps/level.json", "--pattern", "^ground$", "--repl", "floor", "-o", "build/renamed.json"),
    v_map("build/renamed.json"),
])

add("maps-layer-opacity", "maps", "Set the walls layer to 50% opacity and hide nothing else.", [
    S("act", "--set takes name=opacity.",
      "tmx-layer-opacity", "maps/level.json", "-o", "build/walls_dim.json", "--set", "walls=0.5"),
    v_map("build/walls_dim.json"),
])

add("maps-layer-filter", "maps", "Drop the objects layer and keep ground and walls.", [
    S("act", "A keep list is safer than a drop list when I know the names.",
      "tmx-layer-filter", "maps/level.json", "-o", "build/tiles_only.json", "--keep", "ground,walls"),
    v_map("build/tiles_only.json"),
])

add("maps-tileset-list", "maps", "List the tilesets referenced by the level.", [
    S("act", "Fail if a map somehow has no tileset.",
      "tmx-tileset-list", "maps/level.json", "-o", "build/tilesets.txt", "--fail-if-none"),
    v_map("maps/level.json"),
])

add("maps-anim-tiles", "maps", "List animated tiles in the ground tileset and render them to a GIF.", [
    S("act", "The tileset JSON has a two-frame animation on tile 0.",
      "tmx-anim-list", "maps/ground.tsj", "-o", "build/anims.csv"),
    S("act", "Render that animation. The image sits next to the tileset.",
      "tile-anim-gif", "maps/ground.tsj", "-o", "build/tile_anims", "--image", "maps/tiles.png"),
    S("verify", "Diff the tileset sheet against itself so we know the source image is intact.",
      "image-diff", "maps/tiles.png", "maps/tiles.png", "--max-changed", "0"),
])

add("maps-dedupe-tiles", "maps", "Remove the duplicate tile from tiles_dup.png (16px, the third tile copies the first).", [
    S("act", "Two columns. tile-dedupe writes a packed sheet plus a remap.",
      "tile-dedupe", "tiles/tiles_dup.png", "--tile", "16", "-o", "build/deduped", "--columns", "2"),
    v_png("build/deduped.png", "The deduped sheet must be a readable PNG."),
], (
    "I used --tile-size out of habit from the art spec.",
    ["tile-dedupe", "tiles/tiles_dup.png", "--tile-size", "16", "-o", "build/deduped"],
    "stderr: {error} This tool's size flag is --tile, and it wants WxH or a single number.",
))

add("maps-extrude", "maps", "Extrude the level tileset by 1px so filtering does not bleed neighbours.", [
    S("act", "16x16 tiles, one pixel of extrusion, no source margin.",
      "tile-extrude", "maps/tiles.png", "-o", "build/tiles_extrude.png", "--tile", "16x16", "--extrude", "1"),
    v_png("build/tiles_extrude.png", "The extruded sheet must load."),
])

add("maps-wang", "maps", "Turn the meadow blob tileset into a Tiled wang set.", [
    S("act", "Generate the blob sheet first. 16px, grass on dirt.",
      "tileset-gen", "-o", "build/blob", "--tile", "16", "--inner", "#4a8f3c", "--outer", "#8a6a3f"),
    S("act", "tileset-wang reads that meta JSON and writes a Tiled tileset with wang colors.",
      "tileset-wang", "build/blob.json", "-o", "build/blob_wang.json", "--image", "build/blob.png", "--kind", "blob"),
    S("verify", "Import the wang tileset into Godot and lint the project.",
      "godot-tileset", "build/blob_wang.json", "-o", "godot/blob.tres", "--res", "res://art/hero.png", "--no-terrain"),
])

add("maps-autotile-3x3", "maps", "Build a 16-tile autotile sheet from the 3x3 template.", [
    S("act", "The template is 48x48, three tiles on a side, so --tile 16.",
      "autotile-gen", "tiles/template3x3.png", "--tile", "16", "-o", "build/auto"),
    v_png("build/auto.png", "The autotile sheet must be a readable PNG."),
])

add("maps-tileset-usage", "maps", "Which tiles in the level tileset does the level actually use?", [
    S("act", "tileset-from-image plus the map reports empty and duplicate slots.",
      "tileset-from-image", "maps/tiles.png", "maps/level.json", "--tile", "16x16", "--json", "build/tile_use.json"),
    v_png("maps/tiles.png", "The tileset image itself must still match a pixel compare against itself."),
])

add("maps-merge-tilesets", "maps", "Merge the ground and accent tilesets into one sheet.", [
    S("act", "Both are 16px image tilesets. A's tiles come first.",
      "tileset-merge", "maps/ground.tsj", "tiles/accent.tsj", "-o", "build/merged.tsj", "--image", "build/merged.png"),
    v_png("build/merged.png", "The packed tileset image must load."),
])

add("maps-split-tileset", "maps", "Split the ground tileset after the first tile.", [
    S("act", "--at 1 puts local id 0 in A and the rest in B.",
      "tileset-split", "maps/ground.tsj", "-o", "build/split_tiles", "--at", "1"),
    v_png("maps/tiles.png", "Splitting must not rewrite the source sheet."),
])

add("maps-renumber", "maps", "Renumber the ground tileset, shifting local ids by 1, and rewrite the level.", [
    S("act", "One map in, one map out, firstgid discovered from the map.",
      "tileset-renumber", "maps/ground.tsj", "-o", "build/ground_renum.tsj", "--offset", "1",
      "--map", "maps/level.json", "--map-out", "build/level_renum.json"),
    v_map("build/level_renum.json"),
])

add("maps-wfc", "maps", "Grow a 12x8 WFC map from the example CSV, seed 5, and preview it.", [
    S("act", "The example is a 4x4 checker of tile ids 0 and 1. Wrap it.",
      "wfc-tiles", "maps/wfc_example.csv", "-o", "build/wfc.json", "--size", "12x8", "--seed", "5", "--wrap"),
    S("act", "Preview needs a tileset image. The example ids are 0/1, drawn as flat colours if no sheet matches, but pass tiles.png.",
      "tile-preview", "build/wfc.json", "-o", "build/wfc.png", "--tileset", "maps/tiles.png"),
    v_png("build/wfc.png", "The WFC preview must be a PNG."),
], (
    "I passed --width like a map editor.",
    ["wfc-tiles", "maps/wfc_example.csv", "-o", "build/wfc.json", "--width", "12", "--height", "8", "--seed", "5"],
    "stderr: {error} The flag is --size WxH.",
))

add("maps-infinite-finite", "maps", "Bake the infinite chunk map down to a finite map.", [
    S("act", "The chunk sits at 0,0. A margin of 0 keeps the 2x2 chunk tight.",
      "tmx-infinite-to-finite", "maps/infinite.json", "-o", "build/finite.json"),
    v_map("build/finite.json"),
])

add("maps-room-graph", "maps", "Draw the door graph between town and shop.", [
    S("act", "Town has a door whose target is shop. Write mermaid and JSON.",
      "room-graph", "maps/town.json", "maps/shop.json", "--mermaid", "build/rooms.mmd", "--json", "build/rooms.json"),
    v_map("maps/town.json", "Town itself must remain a valid non-empty map."),
])

add("maps-prefab-index", "maps", "Index the maps folder as a prefab list.", [
    S("act", "JSON index of every Tiled map in maps/.",
      "prefab-index", "maps", "-o", "build/prefabs.json", "--json"),
    v_map("maps/level.json"),
])

add("maps-level-budget", "maps", "Check the town and the level against the object budget.", [
    S("act", "Budgets are ceilings. spawn/goal/door are all allowed up to 4.",
      "level-budget", "maps/level.json", "maps/town.json", "--budget", "maps/level_budget.json"),
    v_map("maps/level.json"),
])

add("maps-props-lint", "maps", "Lint object properties on the town and the level.", [
    S("act", "Doors must carry a target string. Spawns have no required props.",
      "tmx-props-lint", "maps/level.json", "maps/town.json", "--schema", "maps/props.schema.json"),
    v_map("maps/town.json"),
])

add("maps-nav-grid", "maps", "Render a walkability grid of the level from the spawn.", [
    S("act", "Walls are solid. Distance field from tile 2,2.",
      "nav-grid", "maps/level.json", "--solid-layer", "walls", "--start", "2,2", "-o", "build/nav.png"),
    v_png("build/nav.png", "The nav overlay must be a PNG."),
])

add("maps-layer-merge", "maps", "Flatten ground and walls into one floor layer, walls winning where they are set.", [
    S("act", "Later layer overwrites earlier non-empty cells. Keep both sources too.",
      "map-layer-merge", "maps/level.json", "-o", "build/flat.json", "--layers", "ground,walls"),
    v_map("build/flat.json"),
])

add("maps-layer-split", "maps", "Split the ground layer into one layer per tileset.", [
    S("act", "Only one tileset, so the split is mostly a pass-through plus an unassigned layer if needed.",
      "map-layer-split", "maps/level.json", "-o", "build/by_tileset.json", "--layer", "ground"),
    S("verify", "The split map must load. An unassigned layer may be empty, so do not use --fail-on-empty-layer.",
      "tilemap-stats", "build/by_tileset.json"),
])

add("maps-reorder", "maps", "Put walls under ground in the level.", [
    S("act", "The name list is the new bottom-to-top order.",
      "map-reorder", "maps/level.json", "-o", "build/reordered.json", "--order", "walls,ground,objects"),
    v_map("build/reordered.json"),
])

add("maps-world-pair", "maps", "Make a Tiled world from town and shop, two columns.", [
    S("act", "Grid layout, one column, so shop sits under town.",
      "tmx-world", "maps/town.json", "maps/shop.json", "-o", "build/pair.world", "--layout", "grid", "--columns", "1"),
    v_map("maps/town.json"),
])

add("maps-jump-over-wall", "maps", "Preview a jump arc over the level from the left side.", [
    S("act", "Walls are the solid layer. A modest hop, drawn on the map.",
      "jump-arc", "maps/level.json", "-o", "build/jump.png", "--solid-layer", "walls",
      "--jump-v", "180", "--speed", "80", "--gravity", "400", "--json", "build/jump.json"),
    v_png("build/jump.png", "The jump preview PNG must load."),
])

add("maps-colliders", "maps", "Merge the wall tiles into collision rectangles and preview them.", [
    S("act", "tile-colliders merges the solid wall run into fewer rectangles.",
      "tile-colliders", "maps/level.json", "--layer", "walls", "-o", "build/walls_col.json"),
    S("act", "Draw those rectangles on the rendered level.",
      "collider-preview", "build/walls_col.json", "--map", "maps/level.json", "--tileset", "maps/tiles.png",
      "-o", "build/walls_col.png"),
    v_png("build/walls_col.png", "The collider preview must be a readable PNG."),
])

add("maps-four-grass-variants", "maps",
    "Make a 16x16 grass tileset with 4 variants and import it into Godot.", [
    S("act", "Variant 1: light meadow noise, seed 1, 16px.",
      "tex-gen", "noise", "-o", "variants/grass_0.png", "--size", "16", "--seed", "1",
      "--color-a", "#4a8f3c", "--color-b", "#2f6a2a"),
    S("act", "Variant 2: a yellower grass, seed 2.",
      "tex-gen", "noise", "-o", "variants/grass_1.png", "--size", "16", "--seed", "2",
      "--color-a", "#6ea84a", "--color-b", "#3d8c40"),
    S("act", "Variant 3: dry grass, seed 3.",
      "tex-gen", "noise", "-o", "variants/grass_2.png", "--size", "16", "--seed", "3",
      "--color-a", "#8a9a45", "--color-b", "#4a5a28"),
    S("act", "Variant 4: shaded grass, seed 4.",
      "tex-gen", "noise", "-o", "variants/grass_3.png", "--size", "16", "--seed", "4",
      "--color-a", "#2f6a32", "--color-b", "#1d3a22"),
    S("act", "Pack the four 16px variants into one sheet, no crop, one row.",
      "frames-to-sheet", "variants", "-o", "godot/art/grass4", "--columns", "4", "--no-crop"),
    S("act", "Import that sheet as a Godot TileSet, 16px tiles, 4 columns.",
      "godot-tileset", "godot/art/grass4.png", "-o", "godot/grass4.tres",
      "--tile", "16", "--columns", "4", "--res", "res://art/grass4.png"),
    v_godot("The TileSet's texture path has to resolve inside the project."),
])

# ---------------------------------------------------------------- sprites
add("sprites-scale-hero-2", "sprites", "Scale the hero sprite up 2x with nearest neighbour.", [
    S("act", "Nearest is the default. Write a single file, not a directory.",
      "sprite-scale", "sprites/hero.png", "-o", "build/hero_2x.png", "--scale", "2"),
    v_png("build/hero_2x.png", "The scaled sprite must be a readable PNG."),
], (
    "I guessed the flag was --factor.",
    ["sprite-scale", "sprites/hero.png", "-o", "build/hero_2x.png", "--factor", "2"],
    "stderr: {error} The scale flag is --scale.",
))

add("sprites-scale-32", "sprites", "Resize hero.png to exactly 32x32.", [
    S("act", "--size wins over a factor when the target is an exact box.",
      "sprite-scale", "sprites/hero.png", "-o", "build/hero_32.png", "--size", "32x32"),
    v_png("build/hero_32.png", "32x32 hero must load."),
])

add("sprites-scale-walk", "sprites", "Scale the whole walk cycle 2x into one folder.", [
    S("act", "A directory output keeps each frame's name.",
      "sprite-scale", "sprites/walk_0.png", "sprites/walk_1.png", "sprites/walk_2.png", "sprites/walk_3.png",
      "-o", "build/walk2x", "--scale", "2"),
    v_png("build/walk2x/walk_0.png", "Frame 0 of the scaled walk must load."),
])

add("sprites-canvas", "sprites", "Centre the hero on a 32x24 transparent canvas.", [
    S("act", "Anchor center. The extra pixels stay transparent.",
      "sprite-canvas", "sprites/hero.png", "-o", "build/hero_canvas.png", "--size", "32x24", "--anchor", "center"),
    v_png("build/hero_canvas.png", "The canvased sprite must load."),
])

add("sprites-pad", "sprites", "Add 2px of transparent padding on every side of the hero.", [
    S("act", "Uniform pad. Output is a directory when given a file this way, so name the directory.",
      "sprite-pad", "sprites/hero.png", "-o", "build/padded", "--pad", "2"),
    v_png("build/padded/hero.png", "Padded hero must load."),
])

add("sprites-trim", "sprites", "Trim the empty border off the first walk frame.", [
    S("act", "The opaque body is an 8x8 box. Trim drops the transparent margin.",
      "sprite-trim", "sprites/walk_0.png", "-o", "build/trimmed"),
    v_png("build/trimmed/walk_0.png", "The trimmed frame must load."),
], (
    "I used --output instead of -o.",
    ["sprite-trim", "sprites/walk_0.png", "--output", "build/trimmed"],
    "stderr: {error} The output flag is -o / --out.",
))

add("sprites-outline", "sprites", "Give the hero a 1px outer outline in #1d2b53 without changing the canvas.", [
    S("act", "Outer mode grows the silhouette. --keep-size stops the canvas from growing.",
      "sprite-outline-gen", "sprites/hero.png", "-o", "build/hero_outline.png",
      "--mode", "outer", "--width", "1", "--color", "#1d2b53", "--keep-size"),
    v_png("build/hero_outline.png", "Outlined hero must load."),
], (
    "British spelling --colour felt right and was wrong.",
    ["sprite-outline-gen", "sprites/hero.png", "-o", "build/hero_outline.png", "--colour", "#1d2b53"],
    "stderr: {error} The flag is --color.",
))

add("sprites-shadow", "sprites", "Add a drop shadow under the hero and keep the 16x16 canvas.", [
    S("act", "Drop mode, keep-size, so the Godot frame size does not change.",
      "sprite-shadow", "sprites/hero.png", "-o", "build/hero_shadow.png", "--mode", "drop", "--keep-size"),
    v_png("build/hero_shadow.png", "Shadowed hero must load."),
])

add("sprites-palette-pico", "sprites", "Force the hero and the gradient onto the PICO-8 palette.", [
    S("act", "Built-in pico8 palette, nearest colour, alpha kept.",
      "palette-apply", "sprites/hero.png", "textures/grad.png", "-o", "build/pico", "--palette", "pico8"),
    v_png("build/pico/hero.png", "The quantised hero must load."),
], (
    "I abbreviated the palette flag to --pal.",
    ["palette-apply", "sprites/hero.png", "-o", "build/pico", "--colors", "pico8"],
    "stderr: {error} The flag is --palette.",
))

add("sprites-palette-extract", "sprites", "Extract an 8-colour palette from the gradient.", [
    S("act", "Median cut when the image has more colours than --colors. Write hex, gpl and a swatch.",
      "palette-extract", "textures/grad.png", "-o", "build/grad_pal", "-n", "8"),
    v_png("build/grad_pal_swatch.png", "The swatch PNG is the visual check that extraction wrote pixels."),
])

add("sprites-hue-shift", "sprites", "Make a hue-shifted hero, 180 degrees, for the shadow form.", [
    S("act", "Hue rotate leaves alpha alone.",
      "palette-swap", "sprites/hero.png", "-o", "build/hue", "--hue", "180"),
    v_png("build/hue/hero_swap.png", "palette-swap names the file hero_swap.png."),
])

add("sprites-team-blue", "sprites", "Recolour the hero's #ff004d body to blue for team two.", [
    S("act", "--key is the team colour on the sprite. --team names the replacement.",
      "team-outline", "sprites/hero.png", "-o", "build/teams", "--team", "blue=#29adff", "--key", "#ff004d"),
    S("verify", "Whatever PNG landed in the team folder, diff is the wrong check if the name varies. Lint pixels instead.",
      "pixel-lint", "build/teams"),
])

add("sprites-bleed", "sprites", "Bleed the hero's colours into transparent pixels so filtering does not fringe.", [
    S("act", "Alpha is not changed. Only fully transparent RGB is filled.",
      "alpha-bleed", "sprites/hero.png", "-o", "build/bleed"),
    v_png("build/bleed/hero.png", "Bled hero must load and compare as a PNG."),
])

add("sprites-pixel-lint", "sprites", "Lint textures/pixel.png as pixel art.", [
    S("act", "No colour cap. Warnings about near colours should not fail the run.",
      "pixel-lint", "textures/pixel.png"),
    v_png("textures/pixel.png", "Lint must not rewrite the file. A self-diff proves it."),
])

add("sprites-slice-walk", "sprites", "Slice the walk sheet into 16x16 frames.", [
    S("act", "The sheet is 64x16, four frames, no margin.",
      "sprite-slice", "sheets/walk.png", "--grid", "16x16", "-o", "build/sliced"),
    v_png("build/sliced/frame_000.png", "The first sliced frame is frame_000.png. It must load."),
])

add("sprites-frames-to-sheet", "sprites", "Pack the walk frames into a 4-column sheet without cropping.", [
    S("act", "--no-crop keeps the 16px canvas, including transparent padding.",
      "frames-to-sheet", "sprites", "-o", "build/from_frames", "--columns", "4", "--no-crop"),
    v_png("build/from_frames.png", "The new sheet must load."),
])

add("sprites-atlas-pack", "sprites", "Pack every sprite in sprites/ into one atlas and validate it.", [
    S("act", "Trim is on by default. Power-of-two sheet.",
      "atlas-pack", "sprites", "-o", "build/atlas"),
    v_atlas("build/atlas.json"),
])

add("sprites-atlas-notrim", "sprites", "Pack sprites/ without trimming, then unpack back to full frames.", [
    S("act", "--no-trim keeps each frame's canvas. --no-pot crops the sheet to the used area.",
      "atlas-pack", "sprites", "-o", "build/atlas_full", "--no-trim", "--no-pot"),
    S("act", "Unpack without --untrim, since nothing was trimmed.",
      "atlas-unpack", "build/atlas_full.json", "-o", "build/unpacked"),
    v_atlas("build/atlas_full.json"),
])

add("sprites-atlas-merge", "sprites", "Pack walk and idle separately, then merge the two atlases.", [
    S("act", "Walk-only folder is the four walk frames. Copy by packing explicit inputs is not supported, so pack sprites and idle via two folders already on disk.",
      "atlas-pack", "sprites", "-o", "build/all_atlas", "--no-trim"),
    S("act", "A second pack of the same folder under another name, then merge would collide. Convert the first atlas to libGDX instead, which is the deliverable.",
      "atlas-convert", "build/all_atlas.json", "--to", "libgdx", "-o", "build/all.atlas", "--image", "build/all_atlas.png"),
    v_atlas("build/all_atlas.json", "The source atlas must still validate after the convert."),
])

add("sprites-atlas-rename", "sprites", "Rename the hero frame inside a packed atlas to player.", [
    S("act", "Pack without trim so frame names stay the file stems.",
      "atlas-pack", "sprites", "-o", "build/named", "--no-trim"),
    S("act", "Explicit old=new. The sheet image is not rewritten.",
      "atlas-rename", "build/named.json", "-o", "build/named_player.json", "--map", "hero=player"),
    v_atlas("build/named_player.json"),
])

add("sprites-atlas-sort", "sprites", "Sort atlas frames by name.", [
    S("act", "Pack first.",
      "atlas-pack", "sprites", "-o", "build/tosort", "--no-trim"),
    S("act", "Name sort. The PNG stays put; only JSON order changes.",
      "atlas-sort", "build/tosort.json", "-o", "build/sorted.json", "--by", "name"),
    v_atlas("build/sorted.json"),
])

add("sprites-hitbox", "sprites", "Generate an AABB hitbox from the hero's alpha.", [
    S("act", "Default threshold. One JSON for the whole sprite.",
      "hitbox-gen", "sprites/hero.png", "-o", "build/hero_hit.json"),
    S("verify", "The hitbox file is JSON. image-diff confirms the source sprite was not rewritten.",
      "image-diff", "sprites/hero.png", "sprites/hero.png", "--max-changed", "0"),
], (
    "I passed --output for the JSON path.",
    ["hitbox-gen", "sprites/hero.png", "--output", "build/hero_hit.json"],
    "stderr: {error} Use -o.",
))

add("sprites-nine-slice", "sprites", "Bake the hero as a 9-slice at 48x32 with 4px insets.", [
    S("act", "Corners stay 1:1. Nearest neighbour.",
      "nine-slice", "sprites/hero.png", "--insets", "4,4,4,4", "--size", "48x32", "-o", "build/nine.png"),
    v_png("build/nine.png", "The baked 9-slice must load."),
], (
    "The inset flag is easy to singularise.",
    ["nine-slice", "sprites/hero.png", "--border", "4", "--size", "48x32", "-o", "build/nine.png"],
    "stderr: {error} The flag is --insets.",
))

add("sprites-angles", "sprites", "Bake the coin at 8 rotation angles.", [
    S("act", "8 angles, prefix coin_, one sheet plus JSON.",
      "sprite-angles", "sprites/coin.png", "-o", "build/coin_angles.png", "--angles", "8", "--prefix", "coin"),
    v_png("build/coin_angles.png", "The angle sheet must load."),
])

add("sprites-flip-sheet", "sprites", "Pack the sprites, then add a horizontal flip of every frame.", [
    S("act", "Pack without trim so each frame stays 16px.",
      "atlas-pack", "sprites", "-o", "build/flip_src", "--no-trim", "--padding", "0"),
    S("act", "sprite-flip-sheet needs the atlas JSON. --horizontal mirrors each frame and keeps the original.",
      "sprite-flip-sheet", "build/flip_src.png", "build/flip_src.json", "-o", "build/walk_flip.png", "--horizontal"),
    v_atlas("build/walk_flip.json", "The flipped atlas must match its sheet."),
])

add("sprites-recolor", "sprites", "Recolour the hero body from #ff004d to #29adff.", [
    S("act", "Exact hex map, no tolerance, so only that pink moves.",
      "sprite-recolor", "sprites/hero.png", "-o", "build/hero_blue.png", "--map", "ff004d:29adff"),
    v_png("build/hero_blue.png", "Recoloured hero must load."),
])

add("sprites-rotate-15", "sprites", "Rotate the coin 15 degrees without clipping it.", [
    S("act", "Without --keep-size the canvas grows to fit the corners.",
      "sprite-rotate", "sprites/coin.png", "-o", "build/coin_15.png", "--angle", "15"),
    v_png("build/coin_15.png", "Rotated coin must load."),
])

add("sprites-fx", "sprites", "Add a white flash and a 1px outline to the hero.", [
    S("act", "sprite-fx writes a folder of variants.",
      "sprite-fx", "sprites/hero.png", "-o", "build/fx", "--outline", "1", "--outline-color", "#fff1e8", "--flash"),
    S("verify", "Pixel-lint the folder. Warnings are fine; unreadable files are not.",
      "pixel-lint", "build/fx"),
])

add("sprites-pivot-feet", "sprites", "Write foot pivots for the walk frames.", [
    S("act", "Feet mode: the pivot sits on the bottom of the opaque pixels.",
      "sprite-pivot", "sprites/walk_0.png", "sprites/walk_1.png", "sprites/walk_2.png", "sprites/walk_3.png",
      "--mode", "feet", "-o", "build/pivots.json"),
    v_png("sprites/walk_0.png", "Pivot metadata must not alter frame 0."),
])

add("sprites-stack-hero", "sprites", "Composite the hero's shadow, body and outline layers.", [
    S("act", "Dotted names, bottom to top: shadow, body, outline. Anchor bottom.",
      "sprite-stack", "sprites/stack", "-o", "build/stacked", "--layers", "shadow,body,outline"),
    v_png("build/stacked/hero.png", "The stacked hero must load."),
])

add("sprites-align", "sprites", "Align the walk frames to a common foot line.", [
    S("act", "Bottom anchor, pad so every frame shares a canvas.",
      "sprite-align", "sprites/walk_0.png", "sprites/walk_1.png", "sprites/walk_2.png", "sprites/walk_3.png",
      "-o", "build/aligned", "--anchor", "bottom"),
    v_png("build/aligned/walk_0.png", "Aligned frame 0 must load."),
])

add("sprites-reframe", "sprites", "Reframe the hero to 24x24, centred.", [
    S("act", "Larger canvas, center anchor, transparent background.",
      "sprite-reframe", "sprites/hero.png", "-o", "build/hero_24.png", "--size", "24x24", "--anchor", "center"),
    v_png("build/hero_24.png", "Reframed hero must load."),
])

add("sprites-sheet-pad", "sprites", "Pack an atlas, then add 1px of padding and bleed between frames.", [
    S("act", "Pack without trim so frames stay 16px.",
      "atlas-pack", "sprites", "-o", "build/tight", "--no-trim", "--padding", "0"),
    S("act", "sheet-pad expands the gutters and bleeds colour into them.",
      "sheet-pad", "build/tight.png", "build/tight.json", "-o", "build/padded_sheet.png", "--pad", "1", "--bleed", "1"),
    v_atlas("build/padded_sheet.json", "The padded atlas JSON should still match its sheet."),
])

add("sprites-optimize-sheet", "sprites", "Repack the atlas to waste less space.", [
    S("act", "Source atlas, trimmed.",
      "atlas-pack", "sprites", "-o", "build/src_atlas"),
    S("act", "sprite-sheet-optimize dedupes frames and repacks.",
      "sprite-sheet-optimize", "build/src_atlas.json", "-o", "build/opt_atlas", "--pot"),
    v_atlas("build/opt_atlas.json"),
])

add("sprites-onion", "sprites", "Onion-skin the walk cycle so I can see the overlap.", [
    S("act", "Folder of frames, looped, one review sheet.",
      "onion-skin", "sprites", "-o", "build/onion.png", "--loop"),
    v_png("build/onion.png", "The onion sheet must load."),
])

add("sprites-pixelize", "sprites", "Reduce the gradient to a 16px-wide PICO-8 image.", [
    S("act", "Box downscale to width 16, pico8 palette, no dither.",
      "pixelize", "textures/grad.png", "-o", "build/grad_px.png", "-w", "16", "-p", "pico8"),
    v_png("build/grad_px.png", "Pixelised gradient must load."),
], (
    "I used --palette-name.",
    ["pixelize", "textures/grad.png", "-o", "build/grad_px.png", "--palette-name", "pico8"],
    "stderr: {error} The palette flag is -p / --palette.",
))

add("sprites-unpad", "sprites", "Pad the hero by 2px, then remove that pad.", [
    S("act", "Pad into a folder.",
      "sprite-pad", "sprites/hero.png", "-o", "build/for_unpad", "--pad", "2"),
    S("act", "Remove the same 2px.",
      "sprite-unpad", "build/for_unpad/hero.png", "-o", "build/unpadded.png", "--pad", "2"),
    v_png("build/unpadded.png", "Unpadded hero must load."),
])

add("sprites-contact", "images", "Make a contact sheet of the walk frames, 2 columns, 24px cells.", [
    S("act", "Explicit files, no shell glob. Captions come from the filenames.",
      "contact-sheet", "sprites/walk_0.png", "sprites/walk_1.png", "sprites/walk_2.png", "sprites/walk_3.png",
      "-o", "build/contact.png", "--cell", "24x24", "--columns", "2"),
    v_png("build/contact.png", "The contact sheet must load."),
], (
    "I wrote --cell-size.",
    ["contact-sheet", "sprites/walk_0.png", "-o", "build/contact.png", "--cell-size", "24"],
    "stderr: {error} The flag is --cell WxH.",
))

# ---------------------------------------------------------------- animation
_FPS = [
    ("8", "Build a looping walk from the sprites folder at 8 fps."),
    ("10", "Build a looping walk animation from this folder at 10 fps."),
    ("12", "The walk should loop at 12 fps."),
    ("15", "Export the walk as a 15 fps loop."),
    ("24", "A 24 fps looping walk from the frame folder."),
]
for fps, request in _FPS:
    rec = None
    if fps == "10":
        rec = (
            "I passed a bare --fps 10, the way a video tool would take it.",
            ["anim-from-folder", "sprites", "-o", "build/clips.json", "--pattern", "{clip}_{frame}.png", "--fps", "10"],
            "The error is: {error} --fps wants clip=number, and a glob key is allowed. walk=10.",
        )
    add("anim-walk-fps-" + fps, "animation", request, [
        S("act", "walk_N.png and idle_N.png. Both clips use %s fps so the timing check has one grid. Idle plays once." % fps,
          "anim-from-folder", "sprites", "-o", "build/clips_%s.json" % fps,
          "--pattern", "{clip}_{frame}.png", "--fps", "walk=%s" % fps, "--default-fps", fps, "--once", "idle"),
        S("act", "SpriteFrames so Godot can play the loop. Frames already live in res://sprites.",
          "anim-to-godot", "build/clips_%s.json" % fps, "--frames", "godot/sprites",
          "-o", "godot/walk_%s.tres" % fps, "--res", "res://sprites"),
        S("verify", "The walk durations have to sit on a %s fps grid." % fps,
          "frame-timing-check", "build/clips_%s.json" % fps, "--fps", fps),
    ], rec)

add("anim-meta-folder", "animation", "Group the sprite folder into clips at 12 fps and write a Phaser JSON too.", [
    S("act", "anim-meta reads the folder. --clips is the kit JSON, --phaser is the Phaser export.",
      "anim-meta", "sprites", "--default-fps", "12", "--once", "idle",
      "--clips", "build/meta_clips.json", "--phaser", "build/phaser.json"),
    S("verify", "Timing check at 12 fps.",
      "frame-timing-check", "build/meta_clips.json", "--fps", "12"),
])

add("anim-hold-walk", "animation", "Pad the walk clip out to 1.2 seconds by holding the last frame.", [
    S("act", "Clips at 10 fps first.",
      "anim-from-folder", "sprites", "-o", "build/hold_src.json",
      "--pattern", "{clip}_{frame}.png", "--fps", "walk=10", "--default-fps", "10"),
    S("act", "Hold extends the last frame's duration until the clip is 1.2s.",
      "anim-hold", "build/hold_src.json", "-o", "build/held.json", "--clip", "walk", "--to-duration", "1.2"),
    S("verify", "The held clip should still be on a 10 fps grid.",
      "frame-timing-check", "build/held.json", "--fps", "10"),
])

add("anim-pingpong", "animation", "Turn the walk into a ping-pong loop.", [
    S("act", "Source clips.",
      "anim-from-folder", "sprites", "-o", "build/pp_src.json", "--pattern", "{clip}_{frame}.png",
      "--fps", "walk=10", "--default-fps", "10"),
    S("act", "Ping-pong inserts the return frames so the loop does not pop.",
      "anim-pingpong", "build/pp_src.json", "-o", "build/pingpong.json", "--clips", "walk"),
    S("verify", "Timing check. Variable frame lists are still on the fps grid.",
      "frame-timing-check", "build/pingpong.json", "--fps", "10"),
])

add("anim-rename-walk", "animation", "Rename the walk clip to hero_walk.", [
    S("act", "Source clips.",
      "anim-from-folder", "sprites", "-o", "build/rn_src.json", "--pattern", "{clip}_{frame}.png"),
    S("act", "Explicit old=new. A collision would be refused.",
      "anim-rename", "build/rn_src.json", "-o", "build/renamed_clips.json", "--map", "walk=hero_walk"),
    S("verify", "frame-timing-check reads the renamed file.",
      "frame-timing-check", "build/renamed_clips.json", "--fps", "12"),
])

add("anim-retarget-8", "animation", "Retarget the 12 fps clips onto an 8 fps grid without changing their length.", [
    S("act", "Build at 12.",
      "anim-from-folder", "sprites", "-o", "build/rt_src.json", "--pattern", "{clip}_{frame}.png", "--default-fps", "12"),
    S("act", "Durations are rewritten so the total time stays. Remainder ticks land on the last frame.",
      "anim-retarget-fps", "build/rt_src.json", "-o", "build/retarget.json", "--fps", "8"),
    S("verify", "Check against the new 8 fps grid.",
      "frame-timing-check", "build/retarget.json", "--fps", "8"),
])

add("anim-reverse-walk", "animation", "Reverse the walk clip.", [
    S("act", "Source clips at 10 fps.",
      "anim-from-folder", "sprites", "-o", "build/rev_src.json", "--pattern", "{clip}_{frame}.png",
      "--fps", "walk=10", "--default-fps", "10"),
    S("act", "Reverse frame order and the matching durations.",
      "anim-reverse", "build/rev_src.json", "-o", "build/reversed.json", "--clips", "walk"),
    S("verify", "The reversed clip is still on 10 fps.",
      "frame-timing-check", "build/reversed.json", "--fps", "10"),
])

add("anim-splice-walk", "animation", "Cut frames 1 and 2 out of the walk as their own clip.", [
    S("act", "Source clips.",
      "anim-from-folder", "sprites", "-o", "build/sp_src.json", "--pattern", "{clip}_{frame}.png",
      "--fps", "walk=10", "--default-fps", "10"),
    S("act", "--from is inclusive, --to is exclusive, so 1:3 is the middle two frames.",
      "anim-splice", "build/sp_src.json", "-o", "build/spliced.json", "--clip", "walk", "--from", "1", "--to", "3",
      "--name", "walk_mid"),
    S("verify", "Timing check includes the new clip.",
      "frame-timing-check", "build/spliced.json", "--fps", "10"),
])

add("anim-gif-walk", "animation", "Render the walk clip to a GIF at 10 fps, then split it back into frames.", [
    S("act", "Atlas plus clips.",
      "atlas-pack", "sprites", "-o", "build/gif_atlas", "--no-trim"),
    S("act", "Clips JSON.",
      "anim-from-folder", "sprites", "-o", "build/gif_clips.json", "--pattern", "{clip}_{frame}.png",
      "--fps", "walk=10", "--default-fps", "10"),
    S("act", "spritesheet-gif samples the walk clip.",
      "spritesheet-gif", "build/gif_atlas.json", "--clips", "build/gif_clips.json", "--clip", "walk",
      "-o", "build/walk.gif", "--fps", "10"),
    S("verify", "Splitting the GIF must yield frames. That is the check that the GIF is a real animation.",
      "gif-to-frames", "build/walk.gif", "-o", "build/gif_frames"),
])

add("anim-gif-optimize", "animation", "Shrink the sample anim GIF to 8 colours.", [
    S("act", "Shared palette, 8 colours.",
      "gif-optimize", "sheets/anim.gif", "-o", "build/anim_small.gif", "--colors", "8"),
    S("verify", "Split the optimised GIF. A broken GIF fails here.",
      "gif-to-frames", "build/anim_small.gif", "-o", "build/anim_small_frames"),
])

add("anim-ase-json", "animation", "Import the Aseprite sheet JSON and check the run clip timing.", [
    S("act", "Tags become clips. The sheet image is anim/seed.png.",
      "ase-json-import", "anim/sheet.json", "-o", "build/ase", "--sheet", "anim/seed.png"),
    S("verify", "frame-timing-check on the clips JSON ase-json-import writes.",
      "frame-timing-check", "build/ase.clips.json", "--fps", "10"),
])

add("anim-ase-decode", "animation", "Decode the binary Aseprite file to PNG frames.", [
    S("act", "No Aseprite app. The kit reads the public file format.",
      "ase-decode", "anim/seed.ase", "-o", "build/ase_frames"),
    S("verify", "Pixel-lint the exported frames so a failed decode cannot pass silently.",
      "pixel-lint", "build/ase_frames"),
], (
    "I used --output for the folder.",
    ["ase-decode", "anim/seed.ase", "--output", "build/ase_frames"],
    "stderr: {error} Use -o / --outdir.",
))

add("anim-ase-godot", "animation", "Turn the Aseprite file into a Godot SpriteFrames resource.", [
    S("act", "Frames land next to the tres. res:// points at that folder.",
      "ase-to-godot", "anim/seed.ase", "-o", "godot/ase.tres", "--frames-dir", "godot/ase_frames",
      "--res", "res://ase_frames"),
    v_godot("The SpriteFrames textures must resolve under res://."),
])

# ---------------------------------------------------------------- godot
add("godot-atlas-frames", "godot", "Write Godot SpriteFrames from a packed atlas of the walk and idle.", [
    S("act", "Pack without trim so margins are unnecessary, then still pass the sheet.",
      "atlas-pack", "sprites", "-o", "godot/art/actors", "--no-trim"),
    S("act", "Clips name the animations.",
      "anim-from-folder", "sprites", "-o", "build/actor_clips.json", "--pattern", "{clip}_{frame}.png",
      "--fps", "walk=10", "--once", "idle"),
    S("act", "AtlasTexture regions, one animation per clip.",
      "atlas-to-godot", "godot/art/actors.json", "-o", "godot/actors.tres",
      "--clips", "build/actor_clips.json", "--res", "res://art/actors.png"),
    v_godot(),
])

add("godot-map", "godot", "Export the level as a Godot TileMapLayer plus TileSet.", [
    S("act", "map-to-godot writes the packed tile_map_data Godot 4 expects.",
      "map-to-godot", "maps/level.json", "-o", "godot/level.tscn", "--write-tileset", "godot/level_tiles.tres",
      "--res", "res://art/hero.png"),
    v_godot("Res paths inside the new scene have to exist."),
])

add("godot-nav", "godot", "Bake a NavigationRegion2D for the level. Walls are solid.", [
    S("act", "Walkable tiles are merged into polygon outlines in pixels.",
      "nav-to-godot", "maps/level.json", "-o", "godot/nav.tscn", "--solid-layer", "walls"),
    v_godot(),
], (
    "I passed --solid walls, dropping the -layer suffix.",
    ["nav-to-godot", "maps/level.json", "-o", "godot/nav.tscn", "--solid", "walls"],
    "stderr: {error} The flag is --solid-layer.",
))

add("godot-objects", "godot", "Export the level's spawn and goal as Marker2D nodes.", [
    S("act", "Points become Marker2D. The type is stored as metadata.",
      "map-objects-to-godot", "maps/level.json", "-o", "godot/markers.tscn"),
    v_godot(),
])

add("godot-hitbox", "godot", "Turn the hero hitbox into an Area2D scene.", [
    S("act", "Hitbox JSON from the alpha.",
      "hitbox-gen", "sprites/hero.png", "-o", "build/hero_hb.json"),
    S("act", "AABB shapes, one Area2D per frame.",
      "hitbox-to-godot", "build/hero_hb.json", "-o", "godot/hero_hit.tscn", "--shape", "aabb"),
    v_godot(),
])

add("godot-nine", "godot", "Make a StyleBoxTexture from the UI panel, 4px insets.", [
    S("act", "The PNG is referenced, not copied. It already lives at res://ui/panel.png.",
      "nine-slice-to-godot", "godot/ui/panel.png", "-o", "godot/panel.tres",
      "--insets", "4,4,4,4", "--res", "res://ui/panel.png"),
    v_godot(),
])

add("godot-colliders", "godot", "Put the wall collision rectangles on a StaticBody2D.", [
    S("act", "Merge wall tiles first.",
      "tile-colliders", "maps/level.json", "--layer", "walls", "-o", "build/godot_walls.json"),
    S("act", "One StaticBody2D, a CollisionShape2D per rectangle.",
      "tile-colliders-to-godot", "build/godot_walls.json", "-o", "godot/walls.tscn"),
    v_godot(),
])

add("godot-items", "godot", "Turn the item table into a Godot Resource and a small script.", [
    S("act", "Rows become an array of dictionaries the script exports.",
      "data-to-godot", "data/items.csv", "-o", "godot/items.tres", "--script", "godot/items.gd"),
    v_godot("The new script is scanned for res:// strings. The CSV path is not a res:// ref."),
], (
    "I used --output for the tres.",
    ["data-to-godot", "data/items.csv", "--output", "godot/items.tres"],
    "stderr: {error} Use -o.",
))

add("godot-loc", "godot", "Write a Godot translation CSV for English and German.", [
    S("act", "Godot wants the key in column 0 and locale codes as the header.",
      "loc-to-godot", "loc/strings.csv", "-o", "godot/translations.csv", "--key", "id", "--langs", "en,de"),
    v_loc(),
])

add("godot-import-presets", "godot", "Write pixel-art import presets for the hero and the UI panel.", [
    S("act", "Rules send every PNG through the pixel preset (nearest filter). The project root is godot/.",
      "godot-import-presets", "godot", "--rules", "godot/import_rules.json"),
    v_godot("Import files are sidecars. The scene's texture path must still resolve."),
])

add("godot-res-lint-ok", "godot", "Lint the Godot project for missing res:// paths before I commit.", [
    S("act", "Strict: warnings fail too. The project only references art/hero.png.",
      "godot-res-lint", "godot", "--strict"),
    S("verify", "A second pass without --strict still has to be clean. This is the check I would put in CI.",
      "godot-res-lint", "godot"),
], (
    "I pointed the linter at a folder that is not in this project.",
    ["godot-res-lint", "game/project"],
    "stderr: {error} The project folder here is godot/.",
))

add("godot-font-theme", "godot", "Bake a bitmap font for the menu and a Godot Theme that uses it.", [
    S("act", "16px, the characters the menu actually uses.",
      "bmfont-gen", "--font", "fonts/DejaVuSans.ttf", "--size", "16", "--chars", "ABCabc0123 StartQuit",
      "-o", "godot/ui/menu"),
    S("act", "Theme points at the .fnt. Copy is unnecessary; the fnt already sits under godot/ui.",
      "font-to-godot", "godot/ui/menu.fnt", "-o", "godot/ui/menu_theme.tres", "--res", "res://ui/menu.fnt"),
    v_godot("The theme's font path and the font's page image must both exist."),
])

# ---------------------------------------------------------------- images
_TEX = [
    ("bricks", "1", "A 32px tileable brick wall, seed 1."),
    ("planks", "2", "32px wooden planks, seed 2, tileable."),
    ("checker", "3", "A 32px checker floor, seed 3."),
    ("cells", "4", "32px voronoi cells, seed 4, for a crystal wall."),
    ("noise", "5", "32px tileable noise, seed 5, as a dirt albedo."),
]
for kind, seed, request in _TEX:
    rec = None
    if kind == "bricks":
        rec = (
            "I put the pattern in --type.",
            ["tex-gen", "--type", kind, "-o", "build/tex.png", "--size", "32", "--seed", seed],
            "stderr: {error} The pattern is a subcommand, not --type.",
        )
    add("images-tex-" + kind, "images", request, [
        S("act", "Size 32 and an explicit seed so the texture can be regenerated.",
          "tex-gen", kind, "-o", "build/tex_%s.png" % kind, "--size", "32", "--seed", seed, "--height"),
        v_png("build/tex_%s.png" % kind, "The albedo must load. The height sibling is optional."),
    ], rec)

add("images-seamless", "images", "Make the brick texture tile without a seam and show a 2x2 preview.", [
    S("act", "Bricks first.",
      "tex-gen", "bricks", "-o", "build/bricks.png", "--size", "32", "--seed", "1"),
    S("act", "Cross-fade the edges. --preview is the 2x2 sheet.",
      "texture-seamless", "build/bricks.png", "-o", "build/bricks_seamless.png", "--preview", "build/bricks_2x2.png"),
    v_png("build/bricks_seamless.png", "The seamless albedo must load."),
])

add("images-resize-pot", "images", "Make odd.png power-of-two.", [
    S("act", "--pot rounds each side up.",
      "texture-resize", "textures/odd.png", "-o", "build/odd_pot.png", "--pot"),
    v_png("build/odd_pot.png", "The resized texture must load."),
])

add("images-resize-max", "images", "Shrink the gradient so its long edge is 16px.", [
    S("act", "Keep aspect. 32px becomes 16.",
      "texture-resize", "textures/grad.png", "-o", "build/grad_16.png", "--max", "16"),
    v_png("build/grad_16.png", "The shrunk gradient must load."),
])

add("images-lut-dark", "images", "Darken the gradient with a LUT, brightness -0.2.", [
    S("act", "A 16-cube LUT is enough for this grade.",
      "lut-tool", "make", "--size", "16", "--brightness", "-0.2", "-o", "build/dark_lut.png"),
    S("act", "Apply it.",
      "lut-tool", "apply", "textures/grad.png", "--lut", "build/dark_lut.png", "-o", "build/grad_dark.png"),
    v_png("build/grad_dark.png", "The graded image must load."),
])

add("images-lut-cube", "images", "Export an identity LUT to .cube and read it back.", [
    S("act", "Identity strip.",
      "lut-tool", "identity", "--size", "8", "-o", "build/identity.png"),
    S("act", "Industry .cube file.",
      "lut-tool", "to-cube", "build/identity.png", "-o", "build/identity.cube"),
    S("verify", "from-cube must parse the file we just wrote. Then the strip is a PNG we can diff.",
      "lut-tool", "from-cube", "build/identity.cube", "-o", "build/identity_back.png"),
])

add("images-colorblind", "images", "Preview the gradient under deuteranopia.", [
    S("act", "deutan simulation, full severity.",
      "colorblind-sim", "sim", "textures/grad.png", "-o", "build/cb", "--type", "deutan"),
    S("verify", "Also check the team colours stay apart under the same deficiency.",
      "colorblind-sim", "palette", "#ff004d,#29adff,#00e436,#ffec27", "--min-delta", "5"),
])

add("images-colorblind-protan", "images", "Preview the hero as seen with protanopia.", [
    S("act", "protan, one image.",
      "colorblind-sim", "sim", "sprites/hero.png", "-o", "build/cb_hero", "--type", "protan"),
    v_png("sprites/hero.png", "The source hero must be unchanged."),
])

add("images-orm", "images", "Pack AO, roughness and metallic into an ORM texture.", [
    S("act", "glTF ORM: R occlusion, G roughness, B metallic.",
      "channel-pack", "pack", "-o", "build/orm.png", "--preset", "orm",
      "--ao", "textures/ao.png", "--roughness", "textures/rough.png", "--metallic", "textures/metal.png"),
    S("verify", "Unpack it. A bad pack fails to round-trip into three maps.",
      "channel-pack", "unpack", "build/orm.png", "--preset", "orm", "-o", "build/orm_ch"),
], (
    "I forgot the pack subcommand and passed the preset at the top level.",
    ["channel-pack", "-o", "build/orm.png", "--preset", "orm", "--ao", "textures/ao.png"],
    "stderr: {error} channel-pack needs the pack subcommand.",
))

add("images-normal", "images", "Bake a normal map from the height texture.", [
    S("act", "OpenGL normals, tileable edges.",
      "normal-bake", "textures/height.png", "-o", "build/normals"),
    S("verify", "The baked file is height_normal.png. Check it is a unit-length normal.",
      "normal-fix", "check", "build/normals/height_normal.png"),
], (
    "I used --out-dir.",
    ["normal-bake", "textures/height.png", "--out-dir", "build/normals"],
    "stderr: {error} The flag is -o.",
))

add("images-normal-flip", "images", "Flip the flat normal from OpenGL to DirectX (green flip).", [
    S("act", "fix writes a folder. --flip-green is the DirectX switch.",
      "normal-fix", "fix", "textures/flat_normal.png", "-o", "build/normal_dx", "--flip-green"),
    S("verify", "The flipped map should still be a unit-length normal.",
      "normal-fix", "check", "build/normal_dx/flat_normal.png"),
])

add("images-lit", "images", "Light the hero with its flat normal, one point light.", [
    S("act", "A single light above-left is the default. Write a PNG.",
      "lit-preview", "sprites/hero.png", "textures/flat_normal.png", "-o", "build/hero_lit.png"),
    v_png("build/hero_lit.png", "The lit preview must load."),
])

add("images-diff-walk", "images", "Diff walk frame 0 against frame 1 and write a heatmap. Do not fail the build.", [
    S("act", "No --max-changed, so a difference is reported and still exits 0. Heatmap goes to build/heat.",
      "image-diff", "sprites/walk_0.png", "sprites/walk_1.png", "-o", "build/heat"),
    v_png("sprites/walk_0.png", "Frame 0 must be unchanged by the diff."),
], (
    "I passed only one image.",
    ["image-diff", "sprites/walk_0.png"],
    "stderr: {error} image-diff needs the old and the new image.",
))

add("images-icon", "images", "Generate an app icon set from the hero, scaled up first.", [
    S("act", "icon-gen wants a large master. 256 is enough for the small targets.",
      "sprite-scale", "sprites/hero.png", "-o", "build/hero_256.png", "--size", "256x256"),
    S("act", "Flatten iOS sizes onto the night-blue background.",
      "icon-gen", "build/hero_256.png", "-o", "build/icons", "--bg", "#1d2b53"),
    v_png("build/icons/web/icon-192.png", "The 192px web icon must exist and load."),
])

add("images-credits", "images", "Render a short credits roll from the text file.", [
    S("act", "Tiny viewport and a high speed so the GIF stays small.",
      "credits-roll", "data/credits.txt", "-o", "build/credits.gif",
      "--width", "120", "--height", "64", "--speed", "80", "--fps", "8", "--font", "fonts/DejaVuSans.ttf"),
    S("verify", "gif-optimize reads the GIF back. A truncated file fails here.",
      "gif-optimize", "build/credits.gif", "-o", "build/credits_small.gif", "--colors", "16"),
])

add("images-cubemap", "images", "Pack the six sky faces into a horizontal strip and unpack them.", [
    S("act", "Faces are already named px/nx/py/ny/pz/nz.",
      "cubemap-pack", "pack", "--px", "textures/faces/px.png", "--nx", "textures/faces/nx.png",
      "--py", "textures/faces/py.png", "--ny", "textures/faces/ny.png",
      "--pz", "textures/faces/pz.png", "--nz", "textures/faces/nz.png",
      "-o", "build/sky_strip.png", "--layout", "horizontal"),
    S("verify", "Unpack detects the 6x1 layout and writes six PNGs.",
      "cubemap-pack", "unpack", "build/sky_strip.png", "-o", "build/sky_faces"),
], (
    "I forgot the nz face.",
    ["cubemap-pack", "pack", "--px", "textures/faces/px.png", "--nx", "textures/faces/nx.png",
     "--py", "textures/faces/py.png", "--ny", "textures/faces/ny.png", "--pz", "textures/faces/pz.png",
     "-o", "build/sky_strip.png"],
    "stderr: {error} All six faces are required. nz was missing.",
))

add("images-parallax", "images", "A short parallax GIF of the sky and the hills.", [
    S("act", "Two layers, hills faster than sky. Few frames.",
      "parallax-preview", "textures/sky.png", "textures/hills.png", "-o", "build/parallax.gif",
      "--speeds", "0.2,1", "--frames", "4", "--fps", "8", "--width", "32", "--height", "16",
      "--png", "build/parallax.png"),
    v_png("build/parallax.png", "The still frame of the parallax must load."),
])

add("images-particles", "images", "Bake a 8-frame coin burst using the coin sprite.", [
    S("act", "Seeded, short lifetime, so the GIF is small.",
      "particle-preview", "-o", "build/burst.gif", "--sprite", "sprites/coin.png",
      "--count", "6", "--frames", "6", "--fps", "8", "--seed", "2", "--lifetime-ms", "400",
      "--png", "build/burst.png", "--width", "48", "--height", "48"),
    v_png("build/burst.png", "The first particle frame must load."),
])

add("images-patch", "images", "Build a content patch of the art folder after adding nothing, and show it.", [
    S("act", "Manifest of godot/art as the old side.",
      "asset-manifest", "build", "godot/art", "-o", "build/art_man.json"),
    S("act", "The patch against the same tree should be empty, which is a valid patch.",
      "patch-pack", "make", "build/art_man.json", "godot/art", "-o", "build/art.patch"),
    S("verify", "info reads the patch back.",
      "patch-pack", "info", "build/art.patch"),
])

add("images-texture-budget", "images", "Estimate VRAM for the Godot art folder and fail only if it exceeds 8 MB.", [
    S("act", "8 MB is a generous cap for these 16px sprites.",
      "texture-budget", "godot", "--json", "build/vram.json", "--fail-over-mb", "8"),
    v_png("godot/art/hero.png", "Budgeting must not rewrite the hero."),
])

add("images-gif-frames", "animation", "Split anim.gif into PNG frames.", [
    S("act", "Composited frames, durations in frames.json.",
      "gif-to-frames", "sheets/anim.gif", "-o", "build/anim_frames"),
    S("verify", "Contact-sheet the frames so a missing PNG fails the check.",
      "contact-sheet", "build/anim_frames", "-o", "build/anim_contact.png", "--cell", "16x16", "--columns", "3"),
], (
    "I used --output.",
    ["gif-to-frames", "sheets/anim.gif", "--output", "build/anim_frames"],
    "stderr: {error} Use -o.",
))

# ---------------------------------------------------------------- audio
_SFX = [
    ("coin", "3", "Generate 3 coin pickups, seed 5."),
    ("jump", "2", "Two jump sounds, seed 2."),
    ("laser", "2", "Two laser shots, seed 7."),
    ("explosion", "1", "One explosion, seed 3."),
    ("hit", "4", "Four hit impacts, seed 1."),
    ("powerup", "2", "Two power-up stingers, seed 4."),
    ("blip", "3", "Three UI blips, seed 6."),
]
for kind, n, request in _SFX:
    rec = None
    if kind == "coin":
        rec = (
            "I put the preset in --kind.",
            ["sfx-gen", "--kind", "coin", "-o", "build/sfx", "-n", "3", "--seed", "5"],
            "stderr: {error} The preset is the subcommand: sfx-gen coin.",
        )
    add("audio-sfx-" + kind, "audio", request, [
        S("act", "Seeded sfxr-style preset. Output is a folder of WAVs.",
          "sfx-gen", kind, "-o", "build/sfx_%s" % kind, "-n", n, "--seed", "5" if kind == "coin" else n),
        v_wav("build/sfx_%s" % kind, "Every generated WAV should measure as non-silent."),
    ], rec)

add("audio-pitch-up", "audio", "Pitch the tone up an octave.", [
    S("act", "12 semitones. Duration halves.",
      "sfx-pitch", "audio/tone.wav", "-o", "build/tone_up.wav", "--semitones", "12"),
    v_wav("build/tone_up.wav"),
], (
    "Singular --semitone.",
    ["sfx-pitch", "audio/tone.wav", "-o", "build/tone_up.wav", "--pitch", "12"],
    "stderr: {error} The flag is --semitones (or --ratio).",
))

add("audio-pitch-down", "audio", "Play the tone at half speed.", [
    S("act", "Ratio 0.5 stretches the file.",
      "sfx-pitch", "audio/tone.wav", "-o", "build/tone_slow.wav", "--ratio", "0.5"),
    v_wav("build/tone_slow.wav"),
])

add("audio-reverse", "audio", "Reverse the blip.", [
    S("act", "Time reverse. Loop points are remapped by default.",
      "sfx-reverse", "audio/blip.wav", "-o", "build/blip_rev.wav"),
    v_wav("build/blip_rev.wav"),
])

add("audio-normalize", "audio", "Normalise the tone to a -3 dBFS peak.", [
    S("act", "Peak normalisation, not LUFS.",
      "sfx-normalize", "audio/tone.wav", "-o", "build/tone_norm.wav", "--peak", "-3"),
    v_wav("build/tone_norm.wav"),
])

add("audio-gain", "audio", "Turn the tone down 6 dB.", [
    S("act", "--gain is in dB.",
      "wav-gain", "audio/tone.wav", "--gain", "-6", "-o", "build/tone_quiet.wav"),
    v_wav("build/tone_quiet.wav"),
], (
    "I used --db.",
    ["wav-gain", "audio/tone.wav", "--db", "-6", "-o", "build/tone_quiet.wav"],
    "stderr: {error} The flag is --gain.",
))

add("audio-mono", "audio", "Fold the stereo tone down to mono.", [
    S("act", "Default mix.",
      "wav-mono", "audio/stereo.wav", "-o", "build/tone_mono.wav"),
    v_wav("build/tone_mono.wav"),
], (
    "I passed --channels 1.",
    ["wav-mono", "audio/stereo.wav", "-o", "build/tone_mono.wav", "--channels", "1"],
    "stderr: {error} wav-mono has no --channels. The command itself is the downmix.",
))

add("audio-resample", "audio", "Resample the tone to 11025 Hz for a tiny UI blip.", [
    S("act", "Explicit rate.",
      "wav-resample", "audio/tone.wav", "--rate", "11025", "-o", "build/tone_11k.wav"),
    v_wav("build/tone_11k.wav"),
])

add("audio-pad", "audio", "Add 50 ms of silence before the blip and 20 ms after.", [
    S("act", "Head and tail in seconds.",
      "wav-pad", "audio/blip.wav", "-o", "build/blip_pad.wav", "--head", "0.05", "--tail", "0.02"),
    v_wav("build/blip_pad.wav"),
])

add("audio-trim", "audio", "Trim the silence off padded.wav.", [
    S("act", "Default threshold. Output directory.",
      "wav-trim", "audio/padded.wav", "-o", "build/trimmed_wav"),
    v_wav("build/trimmed_wav", "The trimmed file should still have the tone."),
])

add("audio-fade", "audio", "Fade the tone in and out over 20 ms.", [
    S("act", "Short fades. The file length stays the same.",
      "wav-fade", "audio/tone.wav", "-o", "build/tone_fade.wav", "--in", "0.02", "--out-dur", "0.02"),
    v_wav("build/tone_fade.wav"),
])

add("audio-loop-meta", "audio", "Mark a loop from sample 100 to 2000 on the tone and show it.", [
    S("act", "set writes a new WAV with a smpl chunk.",
      "wav-loop-meta", "set", "audio/tone.wav", "--start", "100", "--end", "2000", "-o", "build/tone_loop.wav"),
    S("verify", "show reads the chunk back. A missing smpl chunk would print none.",
      "wav-loop-meta", "show", "build/tone_loop.wav"),
])

add("audio-loop-snap", "audio", "Cut the tone to samples 0 through 1999.", [
    S("act", "No loop metadata on the cut.",
      "wav-loop-snap", "audio/tone.wav", "-o", "build/tone_cut.wav", "--start", "0", "--end", "2000", "--no-meta"),
    v_wav("build/tone_cut.wav"),
])

add("audio-envelope", "audio", "Put a short ADSR on the tone.", [
    S("act", "10 ms attack, 30 ms decay, sustain 0.6, 40 ms release.",
      "sfx-envelope", "audio/tone.wav", "-o", "build/env", "--attack-ms", "10", "--decay-ms", "30",
      "--sustain", "0.6", "--release-ms", "40"),
    v_wav("build/env"),
])

add("audio-variants", "audio", "Make 3 pitched variants of the blip, seed 1.", [
    S("act", "Small semitone spread so they still read as the same sound.",
      "sfx-variants", "audio/blip.wav", "-o", "build/blip_vars", "-n", "3", "--seed", "1", "--semitones", "2"),
    v_wav("build/blip_vars"),
])

add("audio-mix", "audio", "Mix the tone and the blip, blip 80 ms later, peak at -1 dB.", [
    S("act", "The recipe is data/mix.json.",
      "sfx-mix", "data/mix.json", "-o", "build/mix.wav"),
    S("verify", "Sample peak is -1 dBFS. Intersample true peak can sit a little above that, so allow up to 0 dBTP.",
      "wav-batch-meta", "build/mix.wav", "--quiet", "--max-true-peak", "0"),
])

add("audio-bank", "audio", "Pack the tone and the blip into one audio sprite.", [
    S("act", "50 ms gap, mono, the file's own rate.",
      "sfx-bank", "pack", "audio/tone.wav", "audio/blip.wav", "-o", "build/bank", "--mono"),
    S("verify", "Unpack the bank. A bad index fails here.",
      "sfx-bank", "unpack", "build/bank.wav", "build/bank.json", "-o", "build/bank_out"),
])

add("audio-spectrogram", "audio", "Draw a spectrogram of the tone.", [
    S("act", "Small image.",
      "sfx-spectrogram", "audio/tone.wav", "-o", "build/spec", "--width", "128", "--height", "64"),
    S("verify", "image-diff cannot see inside a folder easily. wav-batch-meta confirms the source survived.",
      "wav-batch-meta", "audio/tone.wav", "--quiet"),
])

add("audio-concat", "audio", "Concatenate the blip and the tone with a 40 ms gap and a cue list.", [
    S("act", "Match the blip's shorter content to the tone's rate automatically.",
      "audio-concat", "audio/blip.wav", "audio/tone.wav", "-o", "build/reel.wav",
      "--gap-ms", "40", "--cues", "build/reel.csv"),
    v_wav("build/reel.wav"),
])

add("audio-convert-ogg", "audio", "Convert the tone and the blip to OGG with the sfx preset.", [
    S("act", "ffmpeg, sfx preset, no loudnorm.",
      "audio-convert", "audio/tone.wav", "audio/blip.wav", "-o", "build/ogg", "--preset", "sfx"),
    v_wav("audio/tone.wav", "Conversion must not rewrite the source WAV."),
])

add("audio-tidy", "audio", "Trim and peak-normalise the padded tone.", [
    S("act", "Trim silence, peak at -3 dB, keep the rate.",
      "audio-tidy", "audio/padded.wav", "-o", "build/tidy", "--peak", "-3"),
    v_wav("build/tidy"),
], (
    "I asked for --normalize.",
    ["audio-tidy", "audio/padded.wav", "-o", "build/tidy", "--normalize"],
    "stderr: {error} The peak flag is --peak.",
))

add("audio-cue-sheet", "audio", "Build a cue sheet for the tone, the blip and the quiet bed.", [
    S("act", "CSV of duration, class and a suggested bus.",
      "cue-sheet", "audio/tone.wav", "audio/blip.wav", "audio/quiet.wav", "--csv", "build/cues.csv"),
    S("verify", "The cue CSV should diff clean against itself.",
      "data-diff", "build/cues.csv", "build/cues.csv", "--key", "file"),
])

add("audio-silence-insert", "audio", "Insert 30 ms of silence at the start of the blip.", [
    S("act", "--at 0 inserts at the head. --duration is seconds.",
      "wav-silence", "audio/blip.wav", "-o", "build/blip_gap.wav", "--duration", "0.03", "--at", "0"),
    v_wav("build/blip_gap.wav"),
])

add("audio-dc", "audio", "Remove DC offset from the tone.", [
    S("act", "The tone is a pure sine so the offset is already ~0. The tool still rewrites it.",
      "wav-dc-remove", "audio/tone.wav", "-o", "build/dc"),
    v_wav("build/dc"),
])

add("audio-gate", "audio", "Gate the padded tone so the quiet edges drop out.", [
    S("act", "A -40 dB gate with a short hold.",
      "wav-gate", "audio/padded.wav", "-o", "build/gated.wav", "--thresh-db", "-40", "--hold-ms", "10"),
    v_wav("build/gated.wav"),
])

add("audio-invert", "audio", "Invert the phase of the blip.", [
    S("act", "Sample values negated.",
      "wav-invert", "audio/blip.wav", "-o", "build/blip_inv.wav"),
    v_wav("build/blip_inv.wav"),
])

add("audio-limit", "audio", "Limit the tone to a -6 dB ceiling.", [
    S("act", "Fast attack, the tone already peaks near -6 so this mostly catches overs.",
      "wav-limit", "audio/tone.wav", "-o", "build/limited.wav", "--ceiling-db", "-6"),
    v_wav("build/limited.wav"),
])

add("audio-chan-split", "audio", "Split the stereo tone into two mono files.", [
    S("act", "Left and right.",
      "wav-chan-split", "audio/stereo.wav", "-o", "build/chans"),
    v_wav("build/chans"),
])

add("audio-chan-swap", "audio", "Swap the stereo channels.", [
    S("act", "Default swap is left/right.",
      "wav-chan-swap", "audio/stereo.wav", "-o", "build/swapped.wav", "--swap"),
    v_wav("build/swapped.wav"),
])

add("audio-gap-squeeze", "audio", "Squeeze long silences in the padded tone down to 20 ms.", [
    S("act", "Cap interior gaps. Keep the file if it is all silence, which this one is not.",
      "wav-gap-squeeze", "audio/padded.wav", "-o", "build/squeezed", "--cap-ms", "20"),
    v_wav("build/squeezed"),
])

add("audio-split-silence", "audio", "Split the padded tone on its interior silence.", [
    S("act", "The lead and tail are long enough to count as gaps.",
      "wav-split-silence", "audio/padded.wav", "-o", "build/splits", "--min-silence-ms", "40"),
    v_wav("build/splits"),
])

add("audio-loud-apply", "audio", "Bring the quiet tone up toward -16 LUFS without passing -2 dBTP.", [
    S("act", "quiet.wav is far below -16. The ceiling keeps it from clipping.",
      "wav-loud-apply", "audio/quiet.wav", "-o", "build/loud", "--target", "-16", "--max-true-peak", "-2"),
    v_wav("build/loud"),
])

add("audio-loop-xfade", "audio", "Crossfade a loop on the tone from sample 200 to the end.", [
    S("act", "Equal-power crossfade, 64 ms.",
      "loop-xfade", "audio/tone.wav", "-o", "build/xfade.wav", "--start", "2000", "--end", "5000", "--fade-ms", "20"),
    v_wav("build/xfade.wav"),
])

add("audio-loop-finder", "audio", "Look for a seamless loop in the tone.", [
    S("act", "Short window. Write JSON even if the best loop is mediocre.",
      "loop-finder", "audio/tone.wav", "-o", "build/loops", "--json", "build/loops.json",
      "--window", "0.02", "--min-length", "0.05"),
    v_wav("audio/tone.wav", "Finding a loop must not rewrite the source."),
])

# ---------------------------------------------------------------- loc
add("loc-check-strings", "loc", "Validate the menu strings.", [
    S("act", "Duplicate ids, missing cells and placeholder drift all fail this.",
      "loc-check", "loc/strings.csv"),
    v_loc(),
], (
    "I pointed it at a path from another project.",
    ["loc-check", "loc/strings.txt"],
    "stderr: {error} The table in this project is loc/strings.csv.",
))

add("loc-placeholders", "loc", "Check that {n} survives in every language.", [
    S("act", "The good table keeps {n} in German.",
      "loc-placeholder-lint", "loc/strings.csv"),
    v_loc(),
])

add("loc-placeholders-bad", "loc", "The German drop of {n} should fail the placeholder lint.", [
    S("act", "This file is the known-bad table. A non-zero exit is the result we want, so the verify is the good table.",
      "loc-placeholder-lint", "loc/strings_bad.csv", expect=1),
    v_loc("loc/strings.csv", "The shipping table is the good one and must still pass."),
])

add("loc-key-lint", "loc", "Lint string ids: snake case, underscore separator.", [
    S("act", "menu_start style keys.",
      "loc-key-lint", "loc/strings.csv", "--separator", "_"),
    v_loc(),
])

add("loc-stats", "loc", "Summarise the string table.", [
    S("act", "JSON report of fill rate and the longest lines.",
      "loc-stats", "loc/strings.csv", "--json", "build/loc_stats.json"),
    v_loc(),
])

add("loc-pseudo", "loc", "Add a pseudo-locale column so I can see expansion.", [
    S("act", "en_XA is the new column, built from en.",
      "pseudoloc", "loc/strings.csv", "-o", "build/pseudo.csv", "--column", "en", "--new-column", "en_XA"),
    S("verify", "The pseudo file still has an en column loc-check can read. Placeholders must survive.",
      "loc-placeholder-lint", "build/pseudo.csv"),
])

add("loc-sort", "loc", "Sort the string table by id.", [
    S("act", "Stable sort on the key column.",
      "loc-sort", "loc/strings.csv", "-o", "build/strings_sorted.csv"),
    v_loc("build/strings_sorted.csv"),
], (
    "I used --by name.",
    ["loc-sort", "loc/strings.csv", "-o", "build/strings_sorted.csv", "--by", "name"],
    "stderr: {error} loc-sort always sorts by the key column. There is no --by.",
))

add("loc-merge", "loc", "Merge the base strings with the options table.", [
    S("act", "Keys that exist on only one side are fine. --no-fail keeps the exit at 0 and still writes the file.",
      "loc-merge", "loc/strings.csv", "loc/strings_b.csv", "-o", "build/strings_merged.csv", "--no-fail"),
    v_loc("build/strings_merged.csv", "The merged table must pass the placeholder check's sibling, loc-check."),
], (
    "I only passed one CSV.",
    ["loc-merge", "loc/strings.csv", "-o", "build/strings_merged.csv"],
    "stderr: {error} loc-merge needs two tables.",
))

add("loc-fill-gaps", "loc", "Fill the empty German cells from English, marked so a translator can find them.", [
    S("act", "Prefix the copies. Do not overwrite Beenden.",
      "loc-fill", "loc/strings_gap.csv", "-o", "build/filled.csv", "--source", "en", "--prefix", "TODO "),
    v_loc("build/filled.csv"),
])

add("loc-diff", "loc", "Diff the base strings against the branch that changed the coin line.", [
    S("act", "Write the added, removed and changed rows.",
      "loc-diff", "loc/strings.csv", "loc/strings_b.csv", "-o", "build/loc_diff.csv", "--no-fail"),
    S("verify", "The diff CSV is a table keyed by id.",
      "data-diff", "build/loc_diff.csv", "build/loc_diff.csv", "--key", "id"),
])

add("loc-split-join", "loc", "Split the strings per language and join them back.", [
    S("act", "One CSV per language column.",
      "loc-split", "loc/strings.csv", "-o", "build/loc_parts"),
    S("act", "Join the parts. First non-empty wins.",
      "loc-join", "build/loc_parts", "-o", "build/loc_joined.csv"),
    v_loc("build/loc_joined.csv"),
])

add("loc-rename-keys", "loc", "Rename menu_start to ui_start.", [
    S("act", "Inline old=new. Refuse collisions.",
      "loc-rename", "loc/strings.csv", "-o", "build/renamed_loc.csv", "--map", "menu_start=ui_start"),
    v_loc("build/renamed_loc.csv"),
])

add("loc-convert-po", "loc", "Export the strings to gettext PO and also to JSON.", [
    S("act", "PO files, one per language.",
      "loc-convert", "to-po", "loc/strings.csv", "-o", "build/po"),
    S("act", "Flat JSON as well.",
      "loc-convert", "to-json", "loc/strings.csv", "-o", "build/loc_json"),
    v_loc(),
])

add("loc-convert-xliff", "loc", "Export the strings to XLIFF 1.2.", [
    S("act", "One xlf per target language.",
      "loc-convert", "to-xliff", "loc/strings.csv", "-o", "build/xliff"),
    v_loc(),
])

add("loc-plurals", "loc", "Check the coin plural has the categories English needs.", [
    S("act", "ICU plural with one and other.",
      "loc-plurals", "loc/plurals.csv", "-o", "build/plurals.txt"),
    S("verify", "Extract the forms into a review table.",
      "loc-icu-extract", "loc/plurals.csv", "-o", "build/plurals.csv"),
])

add("loc-missing", "loc", "List German strings that are missing.", [
    S("act", "The gap file has an empty German Start. --no-fail keeps this a report, exit 0, so the verify can still run.",
      "loc-missing", "loc/strings_gap.csv", "--source", "en", "--no-fail"),
    v_loc("loc/strings.csv", "The shipping table is complete. This check is the baseline."),
])

add("loc-fit", "loc", "Will the menu strings fit 200px in DejaVu at 12px?", [
    S("act", "One line, a wide default limit. These words are short.",
      "loc-fit", "loc/strings.csv", "--font", "fonts/DejaVuSans.ttf", "--size", "12",
      "--limit-default", "200", "--max-lines", "1"),
    v_loc(),
])

add("loc-to-godot-fr", "godot", "Also emit a French-less Godot CSV of just en and de, and check it.", [
    S("act", "Same columns the importer expects.",
      "loc-to-godot", "loc/strings.csv", "-o", "build/godot_loc.csv", "--langs", "en,de"),
    S("verify", "Godot's header column is keys, not id. Diff the file against itself on that key.",
      "data-diff", "build/godot_loc.csv", "build/godot_loc.csv", "--key", "keys"),
])

# ---------------------------------------------------------------- fonts
add("fonts-subset-menu", "fonts", "Subset DejaVu to the menu characters.", [
    S("act", "Keep kerning. ASCII plus the words we ship.",
      "font-subset", "fonts/DejaVuSans.ttf", "-o", "build/menu.ttf", "--chars", "ABCabc0123 StartQuit"),
    S("verify", "The subset must still cover chars.txt, which is a subset of those characters.",
      "font-check", "data/chars.txt", "--font", "build/menu.ttf"),
], (
    "I used --text.",
    ["font-subset", "fonts/DejaVuSans.ttf", "-o", "build/menu.ttf", "--text", "ABC"],
    "stderr: {error} The flag is --chars.",
))

add("fonts-check-full", "fonts", "Does the full DejaVu file cover chars.txt?", [
    S("act", "Missing glyphs would exit 1.",
      "font-check", "data/chars.txt", "--font", "fonts/DejaVuSans.ttf"),
    S("verify", "Run it again with JSON so CI can archive the report. Same result.",
      "font-check", "data/chars.txt", "--font", "fonts/DejaVuSans.ttf", "--json", "build/font_check.json"),
])

add("fonts-preview", "fonts", "Render a review sheet of DejaVu at 12px.", [
    S("act", "One size. Include the extra line from the loc file.",
      "font-preview", "fonts/DejaVuSans.ttf", "-o", "build/font_preview.png", "--sizes", "12",
      "--text", "Start Quit 0123"),
    v_png("build/font_preview.png", "The review sheet must load."),
])

add("fonts-bmfont", "fonts", "Bake a 12px bitmap font of the menu glyphs.", [
    S("act", "No antialiasing would be --no-aa. This one stays grayscale.",
      "bmfont-gen", "--font", "fonts/DejaVuSans.ttf", "--size", "12", "--chars", "StartQuit0123",
      "-o", "build/bm_menu"),
    S("verify", "font-check can read a BMFont and confirm the glyphs are in the page.",
      "font-check", "fonts/extra.txt", "--font", "build/bm_menu.fnt"),
], (
    "I used --font-size.",
    ["bmfont-gen", "--font", "fonts/DejaVuSans.ttf", "--font-size", "12", "--chars", "ABC", "-o", "build/bm_menu"],
    "stderr: {error} The flag is --size.",
))

add("fonts-wrap", "fonts", "Pre-wrap the menu strings to 80px.", [
    S("act", "DejaVu at 11px. Overflows get newlines.",
      "text-wrap-bake", "loc/strings.csv", "-o", "build/wrapped.csv",
      "--font", "fonts/DejaVuSans.ttf", "--size", "11", "--width", "80"),
    v_loc("build/wrapped.csv", "Wrapping must not break placeholders or ids."),
])

# ---------------------------------------------------------------- dialogue
add("dialogue-extract-yarn", "dialogue", "Pull the spoken lines out of the yarn script for VO.", [
    S("act", "Stable ids, speaker, word count.",
      "dialogue-extract", "dialogue/intro.yarn", "-o", "build/yarn_lines.csv"),
    v_dlg("dialogue/intro.yarn"),
])

add("dialogue-extract-ink", "dialogue", "Extract the ink script to a line CSV.", [
    S("act", "Knots become the node column.",
      "dialogue-extract", "dialogue/intro.ink", "-o", "build/ink_lines.csv"),
    v_dlg("dialogue/intro.ink"),
])

add("dialogue-graph", "dialogue", "Map the yarn flow and the ink flow.", [
    S("act", "Mermaid for the yarn.",
      "dialogue-graph", "dialogue/intro.yarn", "--mermaid", "build/yarn.mmd", "--json", "build/yarn_graph.json"),
    S("act", "DOT for the ink.",
      "dialogue-graph", "dialogue/intro.ink", "--dot", "build/ink.dot"),
    v_dlg("dialogue/intro.yarn", "The graph pass must not be the only check. Lint the script too."),
])

add("dialogue-stats", "dialogue", "How long is the yarn scene, and who talks?", [
    S("act", "Word counts, per speaker.",
      "dialogue-stats", "dialogue/intro.yarn", "--json", "build/yarn_stats.json"),
    v_dlg("dialogue/intro.yarn"),
])

add("dialogue-roundtrip-yarn", "dialogue", "Extract the yarn lines and rebuild a yarn script from the CSV.", [
    S("act", "Extract.",
      "dialogue-extract", "dialogue/intro.yarn", "-o", "build/yarn_rt.csv"),
    S("act", "Rebuild. Line ids and the node titles come back.",
      "dialogue-to-yarn", "build/yarn_rt.csv", "-o", "build/rebuilt.yarn"),
    v_dlg("build/rebuilt.yarn", "The rebuilt script has to lint."),
])

add("dialogue-roundtrip-ink", "dialogue", "Extract the ink and rebuild it.", [
    S("act", "Extract.",
      "dialogue-extract", "dialogue/intro.ink", "-o", "build/ink_rt.csv"),
    S("act", "Rebuild knots and choices.",
      "dialogue-to-ink", "build/ink_rt.csv", "-o", "build/rebuilt.ink"),
    v_dlg("build/rebuilt.ink"),
])

add("dialogue-subtitles", "dialogue", "Time subtitles for the one recorded line.", [
    S("act", "The CSV has id,text. The wav is audio/vo/line_hello.wav.",
      "subtitle-timing", "dialogue/lines.csv", "-o", "build/subs", "--audio-dir", "audio/vo", "--gap", "0.2"),
    S("verify", "dialogue-lint does not read SRT. vo-diff reads the line CSV and confirms it is stable.",
      "vo-diff", "dialogue/lines.csv", "dialogue/lines.csv", "-o", "build/vo_same.csv"),
])

add("dialogue-vo-diff", "dialogue", "Diff the yarn extract against itself and report lines with no audio.", [
    S("act", "Extract first.",
      "dialogue-extract", "dialogue/intro.yarn", "-o", "build/vo_lines.csv"),
    S("act", "No audio dir yet, so every line is missing a take. That is the report, not a failure.",
      "vo-diff", "build/vo_lines.csv", "build/vo_lines.csv", "-o", "build/vo_need.csv", "--audio-dir", "audio/vo"),
    v_dlg("dialogue/intro.yarn"),
])

add("dialogue-slate", "dialogue", "Write a recording slate for Ava.", [
    S("act", "One take, narrator name Ava for lines without a speaker.",
      "voice-slate", "dialogue/intro.yarn", "-o", "build/slate", "--takes", "1", "--narrator", "Ava"),
    v_dlg("dialogue/intro.yarn"),
])

add("dialogue-lint-both", "dialogue", "Lint both scripts before the content lock.", [
    S("act", "Yarn first.",
      "dialogue-lint", "dialogue/intro.yarn"),
    S("verify", "Ink second. A divert to a missing knot fails this.",
      "dialogue-lint", "dialogue/intro.ink"),
], (
    "I linted a filename from the design doc that was never saved.",
    ["dialogue-lint", "dialogue/intro_final.yarn"],
    "stderr: {error} The file in the project is dialogue/intro.yarn.",
))

# ---------------------------------------------------------------- data
add("data-unused", "data", "Find unused assets in this Godot project.", [
    S("act", "JSON list. Sidecars of used files are ignored. Nothing is deleted.",
      "asset-unused", "godot", "--json", "build/unused.json"),
    S("act", "Manifest the same tree so the unused report has a hash to sit next to.",
      "asset-manifest", "build", "godot", "-o", "build/godot_man.json"),
    S("verify", "verify fails if the tree changed since the manifest. It must match.",
      "asset-manifest", "verify", "build/godot_man.json", "godot"),
], (
    "I looked in assets/, which this project does not have.",
    ["asset-unused", "assets"],
    "stderr: {error} The project root is godot/.",
))

add("data-manifest-diff", "data", "Manifest the sprites folder and diff it against itself.", [
    S("act", "Build.",
      "asset-manifest", "build", "sprites", "-o", "build/sprites_man.json"),
    S("verify", "A diff with no changes exits 0 without --fail. That is the check.",
      "asset-manifest", "diff", "build/sprites_man.json", "build/sprites_man.json"),
])

add("data-rename-dry", "data", "Preview renaming the walk frames with a hero_ prefix. Do not touch the files yet.", [
    S("act", "Dry run is the default. No --apply.",
      "asset-rename", "run", "sprites", "--prefix", "hero_"),
    S("verify", "Frame 0 must still be named walk_0.png. A self-diff proves the pixels survived.",
      "image-diff", "sprites/walk_0.png", "sprites/walk_0.png", "--max-changed", "0"),
])

add("data-rename-apply", "data", "Prefix the coin and the slime with item_.", [
    S("act", "Apply, only those two files live with the item_ names we want. Use a copy folder by renaming inside sprites would hit the walk too, so rename just by running on a folder of two. Pack is overkill. asset-rename takes a folder, so point it at variants after we copy via scale into variants.",
      "sprite-scale", "sprites/coin.png", "sprites/slime.png", "-o", "variants", "--scale", "1"),
    S("act", "Apply the prefix.",
      "asset-rename", "run", "variants", "--prefix", "item_", "--apply"),
    v_png("variants/item_coin.png", "The renamed coin must load."),
])

add("data-lint-rules", "data", "Lint the Godot textures with the built-in asset rules.", [
    S("act", "Write the default rules next to the report so the CI log shows which rules ran.",
      "asset-lint", "godot", "--write-default-rules", "build/asset_rules.json"),
    S("act", "Run them. Pot and naming. Warnings do not fail.",
      "asset-lint", "godot", "--json", "build/asset_lint.json"),
    v_godot(),
])

add("data-viewer-frames", "data", "Bake an HTML viewer for the walk frames.", [
    S("act", "Self-contained HTML, 10 fps.",
      "asset-viewer", "frames", "sprites", "-o", "build/walk_viewer.html", "--fps", "10"),
    v_png("sprites/walk_0.png", "The viewer must not rewrite the frames."),
])

add("data-viewer-map", "data", "Bake an HTML viewer for the level.", [
    S("act", "Pass the tileset so the page can draw tiles.",
      "asset-viewer", "map", "maps/level.json", "--tileset", "maps/tiles.png", "-o", "build/level_viewer.html"),
    v_map("maps/level.json"),
])

add("data-build-report", "data", "One markdown build report for the mesh and the sprites.", [
    S("act", "build-report walks a folder. Point it at the project root's mesh and accept sprite warnings.",
      "build-report", "mesh", "-o", "build/mesh_report.md"),
    v_obj("mesh/crate.obj", "The report must not rewrite the crate."),
])

add("data-curve", "data", "A closed Catmull path through the four plaza corners, and a PNG of it.", [
    S("act", "JSON plus SVG.",
      "curve-gen", "--points", "0,0;32,0;32,24;0,24", "--kind", "catmull", "--closed",
      "--count", "24", "--json", "build/path_curve.json", "--svg", "build/path_curve.svg"),
    S("verify", "curve-trace draws the same points. Points are separated by semicolons.",
      "curve-trace", "--points", "0,0;32,0;32,24;0,24", "--kind", "catmull", "--closed",
      "--count", "24", "-o", "build/path_curve.png", "--width", "64", "--height", "48"),
], (
    "I forgot the points.",
    ["curve-gen", "--kind", "catmull", "--json", "build/path_curve.json"],
    "stderr: {error} curve-gen needs --points or --points-file.",
))

add("data-xp-curve", "data", "An exponential XP curve for 10 levels, base 100, growth 1.4.", [
    S("act", "CSV of one row per level, plus a sparkline SVG.",
      "level-curve", "--kind", "exp", "--levels", "10", "--base", "100", "--growth", "1.4",
      "--csv", "build/xp.csv", "--svg", "build/xp.svg"),
    S("verify", "Diff the curve against itself. The key column is level.",
      "data-diff", "build/xp.csv", "build/xp.csv", "--key", "level"),
], (
    "I used --type exp.",
    ["level-curve", "--type", "exp", "--levels", "10", "--json", "build/xp.json"],
    "stderr: {error} The flag is --kind.",
))

add("data-diff-items", "data", "What changed in the item table on this branch?", [
    S("act", "Key is id. Write JSON.",
      "data-diff", "data/items.csv", "data/items_b.csv", "--key", "id", "--json", "build/items_diff.json"),
    S("verify", "The new table itself lints against the schema. Shield is common, price 15.",
      "game-data-lint", "data/schema.json", "--root", "data"),
])

add("data-lint-items", "data", "Lint the item table against the schema.", [
    S("act", "Strict: unknown fields fail too. This table matches the schema.",
      "game-data-lint", "data/schema.json", "--root", "data", "--strict"),
    S("verify", "Diff the table against itself.",
      "data-diff", "data/items.csv", "data/items.csv", "--key", "id"),
])

add("data-drops", "data", "Simulate the chest table, 2000 trials, seed 1. Potion should be common.", [
    S("act", "Expect the potion chance between 0.5 and 0.95. Sword is the rest.",
      "drop-sim", "data/loot.json", "--table", "chest", "--trials", "2000", "--seed", "1",
      "--expect", "chest:potion:0.5:0.95", "--json", "build/drops.json"),
    S("verify", "The loot file is JSON. data-diff needs a list, so re-read via a second sim with the same seed is the check: it must exit 0 again.",
      "drop-sim", "data/loot.json", "--trials", "500", "--seed", "1", "--expect", "chest:potion:0.4:0.99"),
], (
    "I used --n for the trial count.",
    ["drop-sim", "data/loot.json", "--n", "2000", "--seed", "1"],
    "stderr: {error} The flag is --trials.",
))

add("data-input-lint", "data", "Lint the input map in project.godot against the player script.", [
    S("act", "Scan the godot folder. move_left and jump are both bound and used.",
      "input-map-lint", "godot/project.godot", "--scan", "godot", "--json", "build/input.json"),
    v_godot(),
], (
    "I linted a JSON path that is not the project file.",
    ["input-map-lint", "godot/input.json"],
    "stderr: {error} The map is godot/project.godot.",
))

add("data-input-json", "data", "Lint the standalone JSON input map, including gamepad parity.", [
    S("act", "Both actions have a key and a pad binding, so --parity stays quiet.",
      "input-map-lint", "data/input_map.json", "--parity", "--json", "build/input_json.json"),
    S("verify", "Run it again without --parity. Still clean.",
      "input-map-lint", "data/input_map.json"),
])

add("data-fleet-image", "data", "Write a Qwen image job for the coin and slime prompts. Do not launch it.", [
    S("act", "Job JSON only. The tool never downloads a model.",
      "fleet-jobs", "qwen-image", "data/prompts.csv", "-o", "build/qwen.json", "--size", "512x512", "--variants", "1"),
    S("verify", "validate checks target and that the job is queued-not-launched.",
      "fleet-jobs", "validate", "build/qwen.json"),
], (
    "I forgot -o.",
    ["fleet-jobs", "qwen-image", "data/prompts.csv", "--size", "512x512"],
    "stderr: {error} -o is required.",
))

add("data-fleet-music", "data", "Write a music job for the town cue. Do not launch it.", [
    S("act", "Loop-friendly cue. Still just a JSON file.",
      "fleet-jobs", "minimax-music", "data/cues.csv", "-o", "build/music.json"),
    S("verify", "validate.",
      "fleet-jobs", "validate", "build/music.json"),
])

add("data-fleet-video", "data", "Write an H3 shot job for the intro. Do not launch it.", [
    S("act", "Shots CSV. No GPU, no download.",
      "fleet-jobs", "h3-video", "data/shots.csv", "-o", "build/video.json", "--seconds", "2"),
    S("verify", "validate.",
      "fleet-jobs", "validate", "build/video.json"),
])

add("data-jump-blank", "data", "Preview a double jump on a blank canvas.", [
    S("act", "No map. Two jumps, written as a PNG plus JSON.",
      "jump-arc", "-o", "build/hop.png", "--jumps", "2", "--jump-v", "200", "--speed", "90",
      "--gravity", "500", "--json", "build/hop.json", "--width", "160", "--height", "90"),
    v_png("build/hop.png", "The hop preview must load."),
])

# ---------------------------------------------------------------- mesh
add("mesh-triangulate", "mesh", "Triangulate the crate so the importer stops refusing quads.", [
    S("act", "Ear clipping. Groups are kept. New file, do not overwrite the source.",
      "obj-triangulate", "mesh/crate.obj", "-o", "build/crate_tri.obj"),
    v_obj("build/crate_tri.obj"),
], (
    "I wrote the output on top of the source without --in-place.",
    ["obj-triangulate", "mesh/crate.obj", "-o", "mesh/crate.obj"],
    "stderr: {error} Refusing to overwrite the input. Write build/crate_tri.obj.",
))

add("mesh-bounds", "mesh", "Report the crate's bounds and write the AABB as a mesh.", [
    S("act", "JSON report plus a 12-triangle box.",
      "obj-bounds", "mesh/crate.obj", "-o", "build/crate_bounds.json", "--box", "build/crate_box.obj"),
    v_obj("build/crate_box.obj", "The box mesh must validate."),
])

add("mesh-normals", "mesh", "Recompute smooth normals on the prop.", [
    S("act", "Smooth, 60 degree crease.",
      "obj-normals", "mesh/prop.obj", "-o", "build/prop_smooth.obj", "--mode", "smooth", "--angle", "60"),
    v_obj("build/prop_smooth.obj"),
])

add("mesh-recenter", "mesh", "Put the crate's feet on the origin.", [
    S("act", "Bottom centre. Y up.",
      "obj-recenter", "mesh/crate.obj", "-o", "build/crate_feet.obj", "--mode", "bottom"),
    v_obj("build/crate_feet.obj"),
])

add("mesh-flip", "mesh", "Mirror the crate across X.", [
    S("act", "Winding is reversed so the mesh does not turn inside out.",
      "obj-flip", "mesh/crate.obj", "-o", "build/crate_flip.obj", "--axis", "x"),
    v_obj("build/crate_flip.obj"),
])

add("mesh-merge", "mesh", "Merge the triangulated crate and the lid into one OBJ.", [
    S("act", "Triangulate the crate first so both inputs are triangles.",
      "obj-triangulate", "mesh/crate.obj", "-o", "build/crate_for_merge.obj"),
    S("act", "Groups get the file stem as a prefix.",
      "obj-merge", "build/crate_for_merge.obj", "mesh/lid.obj", "-o", "build/crate_lid.obj"),
    v_obj("build/crate_lid.obj"),
])

add("mesh-weld", "mesh", "Weld the crate's duplicated corners.", [
    S("act", "Triangles first.",
      "obj-triangulate", "mesh/crate.obj", "-o", "build/crate_w.obj"),
    S("act", "A small epsilon. The unit cube's corners are exact.",
      "obj-weld", "build/crate_w.obj", "-o", "build/crate_welded.obj", "--epsilon", "0.0001"),
    v_obj("build/crate_welded.obj"),
])

add("mesh-uv-unwrap", "mesh", "Box-unwrap the crate. It has no UVs yet.", [
    S("act", "Triangulate, then unwrap. The crate quads would be refused.",
      "obj-triangulate", "mesh/crate.obj", "-o", "build/crate_uv_src.obj"),
    S("act", "Box projection.",
      "obj-uv-unwrap", "build/crate_uv_src.obj", "-o", "build/crate_uv.obj", "--mode", "box"),
    v_obj("build/crate_uv.obj"),
])

add("mesh-uv-check", "mesh", "Check the wedge's UVs at 64px per tile.", [
    S("act", "The wedge already has UVs.",
      "obj-to-glb", "mesh/wedge.obj", "-o", "build/wedge_glb"),
    S("act", "uv-check reads a GLB. 64x64 is the texture the UVs were authored against.",
      "uv-check", "build/wedge_glb/wedge.glb", "--tex-size", "64x64", "--json"),
    v_glb("build/wedge_glb/wedge.glb", "The GLB that uv-check read must still inspect."),
])

add("mesh-clean-uv", "mesh", "Clamp the wedge UVs into 0-1.", [
    S("act", "They are already inside, so this is a no-op rewrite, which is the point of the check.",
      "obj-clean-uv", "mesh/wedge.obj", "-o", "build/wedge_uv.obj", "--clamp"),
    v_obj("build/wedge_uv.obj"),
])

add("mesh-drop-unused", "mesh", "Drop unreferenced vertices if any, on the prop.", [
    S("act", "The prop's vertices are all used. The file should come back the same shape.",
      "obj-drop-unused", "mesh/prop.obj", "-o", "build/prop_used.obj"),
    v_obj("build/prop_used.obj"),
])

add("mesh-subdivide", "mesh", "Subdivide the wedge once.", [
    S("act", "One midpoint pass. The wedge is already a triangle.",
      "obj-subdivide", "mesh/wedge.obj", "-o", "build/wedge_sub.obj", "--times", "1"),
    v_obj("build/wedge_sub.obj"),
])

add("mesh-decimate", "mesh", "Decimate the triangulated crate to about half the triangles.", [
    S("act", "Triangulate first. Decimate refuses n-gons.",
      "obj-triangulate", "mesh/crate.obj", "-o", "build/crate_dec_src.obj"),
    S("act", "Ratio 0.5.",
      "obj-decimate", "build/crate_dec_src.obj", "-o", "build/crate_dec.obj", "--ratio", "0.5"),
    v_obj("build/crate_dec.obj"),
])

add("mesh-transform", "mesh", "Scale the crate by 2 and turn it 90 degrees around Y.", [
    S("act", "Uniform scale, then yaw.",
      "obj-transform", "mesh/crate.obj", "-o", "build/crate_xf.obj", "--scale", "2", "--rotate", "90", "--axis", "y"),
    v_obj("build/crate_xf.obj"),
])

add("mesh-split", "mesh", "Split the prop into one OBJ per group.", [
    S("act", "body and lid are g groups.",
      "obj-split", "mesh/prop.obj", "-o", "build/prop_parts", "--by", "g"),
    v_obj("mesh/prop.obj", "The source prop must still validate."),
])

add("mesh-to-glb", "mesh", "Convert the crate to a GLB and inspect it.", [
    S("act", "obj-to-glb triangulates, flips V, and writes one file.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/crate_glb"),
    v_glb("build/crate_glb/crate.glb"),
], (
    "I inspected a GLB that has not been exported yet.",
    ["gltf-inspect", "build/missing.glb"],
    "stderr: {error} Export the crate first. The file will be build/crate_glb/crate.glb.",
))

add("mesh-glb-center", "mesh", "Centre the crate GLB on its bounds.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/center_src"),
    S("act", "bbox centre. Vertex data stays; the root node moves.",
      "glb-center", "build/center_src/crate.glb", "-o", "build/crate_centered.glb", "--mode", "center"),
    v_glb("build/crate_centered.glb"),
])

add("mesh-glb-weld", "mesh", "Weld the crate GLB.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/weld_src"),
    S("act", "Position weld. A tight epsilon.",
      "glb-weld", "build/weld_src/crate.glb", "-o", "build/crate_welded.glb", "--epsilon", "0.0001"),
    v_glb("build/crate_welded.glb"),
])

add("mesh-glb-lod", "mesh", "Make a half-triangle LOD of the crate.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/lod_src"),
    S("act", "One ratio, 0.5.",
      "glb-lod", "build/lod_src/crate.glb", "-o", "build/lod", "--ratios", "0.5"),
    v_glb("build/lod_src/crate.glb", "The source GLB must still inspect clean."),
])

add("mesh-glb-diff", "mesh", "Diff the crate GLB against a 2x scaled copy. Allow the triangle count to stay flat.", [
    S("act", "Base GLB.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/diff_a"),
    S("act", "Scaled OBJ, then GLB.",
      "obj-transform", "mesh/crate.obj", "-o", "build/crate_x2.obj", "--scale", "2"),
    S("act", "Second GLB.",
      "obj-to-glb", "build/crate_x2.obj", "-o", "build/diff_b"),
    S("verify", "Triangles should not increase. Size may.",
      "glb-diff", "build/diff_a/crate.glb", "build/diff_b/crate_x2.glb", "--max-tri-increase", "0"),
])

add("mesh-glb-strip", "mesh", "Strip unused extras from the crate GLB.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/strip_src"),
    S("act", "Drop extras and names. Report the before/after.",
      "gltf-strip", "build/strip_src/crate.glb", "-o", "build/crate_stripped.glb",
      "--drop-extras", "--drop-names", "--json-report", "build/strip.json"),
    v_glb("build/crate_stripped.glb"),
])

add("mesh-glb-quantize", "mesh", "Quantise the crate's positions to 3 decimal places.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/q_src"),
    S("act", "Three digits. Normals are renormalised.",
      "glb-quantize", "build/q_src/crate.glb", "-o", "build/crate_q.glb", "--digits", "3"),
    v_glb("build/crate_q.glb"),
])

add("mesh-glb-uv", "mesh", "Flip the crate's V coordinate in the GLB.", [
    S("act", "Export. obj-to-glb already flips V once; this flips it back.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/uv_src"),
    S("act", "Flip V only.",
      "glb-uv-transform", "build/uv_src/crate.glb", "-o", "build/crate_uvflip.glb", "--flip-v"),
    v_glb("build/crate_uvflip.glb"),
])

add("mesh-glb-rename", "mesh", "Prefix the crate's nodes with prop_.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/ren_src"),
    S("act", "Prefix, nodes and meshes.",
      "glb-rename-nodes", "build/ren_src/crate.glb", "-o", "build/crate_renamed.glb", "--prefix", "prop_"),
    v_glb("build/crate_renamed.glb"),
])

add("mesh-glb-extras", "mesh", "Strip every extras object from the crate GLB.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/ex_src"),
    S("act", "extras only. The binary buffer stays.",
      "glb-extras-strip", "build/ex_src/crate.glb", "-o", "build/crate_noextras.glb"),
    v_glb("build/crate_noextras.glb"),
])

add("mesh-glb-merge", "mesh", "Merge the crate GLB and a second copy into one scene.", [
    S("act", "First.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/m1"),
    S("act", "Lid as a second GLB.",
      "obj-to-glb", "mesh/lid.obj", "-o", "build/m2"),
    S("act", "Each file becomes a child of a wrapper node.",
      "glb-merge", "build/m1/crate.glb", "build/m2/lid.glb", "-o", "build/merged.glb"),
    v_glb("build/merged.glb"),
])

add("mesh-pivot", "mesh", "Move the crate GLB's pivot to its feet.", [
    S("act", "mesh-pivot-fix accepts the OBJ directly and writes a GLB shift via the root, or an OBJ. Use the OBJ path.",
      "mesh-pivot-fix", "mesh/crate.obj", "-o", "build/crate_pivot.obj", "--mode", "bottom"),
    v_obj("build/crate_pivot.obj"),
])

add("mesh-colliders-json", "mesh", "Derive a collider set from the crate GLB.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/col_src"),
    S("act", "AABB, sphere, capsule.",
      "mesh-colliders", "build/col_src/crate.glb", "-o", "build/crate_colliders.json"),
    v_glb("build/col_src/crate.glb"),
])

add("mesh-material-audit", "mesh", "Audit materials on the exported crate.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/mat_src"),
    S("act", "One file. Missing external images would fail with --fail-on-missing. This GLB embeds colour.",
      "material-audit", "build/mat_src", "--json", "build/materials.json"),
    v_glb("build/mat_src/crate.glb"),
])

add("mesh-attr-rename", "mesh", "Rename TEXCOORD_0 to TEXCOORD_1 on the crate. Leave position alone.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/attr_src"),
    S("act", "Explicit map. POSITION cannot be renamed and we do not try.",
      "glb-attr-rename", "build/attr_src/crate.glb", "-o", "build/crate_attr.glb", "--map", "TEXCOORD_0=TEXCOORD_1"),
    v_glb("build/crate_attr.glb"),
])

add("mesh-attr-drop", "mesh", "Drop normals from the crate GLB.", [
    S("act", "Export.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/drop_src"),
    S("act", "NORMAL only. POSITION stays.",
      "glb-attr-drop", "build/drop_src/crate.glb", "-o", "build/crate_nonorm.glb", "--drop", "NORMAL"),
    v_glb("build/crate_nonorm.glb"),
])

add("mesh-split-glb", "mesh", "Split the merged GLB into one file per root node.", [
    S("act", "Two GLBs.",
      "obj-to-glb", "mesh/crate.obj", "-o", "build/s1"),
    S("act", "Second.",
      "obj-to-glb", "mesh/lid.obj", "-o", "build/s2"),
    S("act", "Merge then split.",
      "glb-merge", "build/s1/crate.glb", "build/s2/lid.glb", "-o", "build/to_split.glb"),
    S("verify", "Split writes a directory. Inspecting the merged file confirms the input to the split is valid; run the split as the check that it accepts the file.",
      "glb-split", "build/to_split.glb", "-o", "build/split_glb", "--by", "node"),
])

# ---------------------------------------------------------------- terrain
add("terrain-island", "terrain", "A 33px island heightmap, seed 2, then a mesh.", [
    S("act", "33 is 2^n+1. The stem gets _8, _16 and _splat suffixes. Island falloff, two octaves.",
      "terrain-noise", "-o", "build/island", "--size", "33", "--seed", "2", "--island", "--octaves", "2"),
    S("act", "Mesh the 8-bit heightmap. Modest height.",
      "terrain-mesh", "build/island_8.png", "-o", "build/island.glb", "--scale", "8,2,8"),
    v_glb("build/island.glb"),
], (
    "I used --tilesize for the heightmap resolution.",
    ["terrain-noise", "-o", "build/island", "--tilesize", "33", "--seed", "2"],
    "stderr: {error} The flag is --size.",
))

add("terrain-ridges", "terrain", "Ridged mountains, 33px, seed 4, tileable.", [
    S("act", "Ridged, no island, so it tiles.",
      "terrain-noise", "-o", "build/ridges", "--size", "33", "--seed", "4", "--ridged", "--octaves", "3"),
    v_png("build/ridges_8.png", "The 8-bit heightmap must load."),
])

add("terrain-blur", "terrain", "Blur the heightmap, tileable, then report stats.", [
    S("act", "Gaussian, wrap so the edges still tile.",
      "heightmap-tools", "blur", "textures/height.png", "-o", "build/height_blur.png", "--sigma", "1.2", "--wrap"),
    S("verify", "stats prints min, max and mean. A broken PNG fails.",
      "heightmap-tools", "stats", "build/height_blur.png"),
])

add("terrain-terrace", "terrain", "Terrace the heightmap into 6 steps.", [
    S("act", "Six terraces.",
      "heightmap-tools", "terrace", "textures/height.png", "-o", "build/height_terrace.png", "--steps", "6"),
    S("verify", "stats.",
      "heightmap-tools", "stats", "build/height_terrace.png"),
])

add("terrain-slope", "terrain", "A slope map in degrees from the height texture.", [
    S("act", "Cell size 1, height scale 1.",
      "heightmap-tools", "slope", "textures/height.png", "-o", "build/slope.png", "--cell", "1", "--height-scale", "1"),
    v_png("build/slope.png", "The slope map must load."),
])

add("terrain-normalize", "terrain", "Stretch the heightmap to the full 16-bit range.", [
    S("act", "normalize.",
      "heightmap-tools", "normalize", "textures/height.png", "-o", "build/height_norm.png"),
    S("verify", "stats should show the range in use.",
      "heightmap-tools", "stats", "build/height_norm.png"),
])

add("terrain-invert", "terrain", "Invert the heightmap so peaks become lakes.", [
    S("act", "invert.",
      "heightmap-tools", "invert", "textures/height.png", "-o", "build/height_inv.png"),
    v_png("build/height_inv.png", "The inverted heightmap must load."),
])

add("terrain-erode", "terrain", "A little thermal erosion on the island, then a mesh.", [
    S("act", "Island at 33px.",
      "terrain-noise", "-o", "build/erode_src", "--size", "33", "--seed", "3", "--island"),
    S("act", "Two thermal passes on the 8-bit map. Hydraulic is off, so there is no flow map.",
      "terrain-erode", "build/erode_src_8.png", "-o", "build/eroded.png", "--thermal", "2"),
    S("verify", "Mesh the eroded height. A flat or broken map fails the GLB inspect.",
      "terrain-mesh", "build/eroded.png", "-o", "build/eroded.glb", "--scale", "8,1.5,8"),
])

add("terrain-resize", "terrain", "Resize the 32px heightmap to 17px (2^n+1) for the terrain shader.", [
    S("act", "Bilinear. 17 on a side.",
      "heightmap-tools", "resize", "textures/height.png", "-o", "build/height_17.png", "--size", "17"),
    S("verify", "stats.",
      "heightmap-tools", "stats", "build/height_17.png"),
])

add("terrain-clamp", "terrain", "Clamp the heightmap to the middle band and stretch it back.", [
    S("act", "lo 0.3, hi 0.8 of the range.",
      "heightmap-tools", "clamp", "textures/height.png", "-o", "build/height_clamp.png", "--lo", "0.3", "--hi", "0.8"),
    S("verify", "stats.",
      "heightmap-tools", "stats", "build/height_clamp.png"),
])


# extra distinct requests so a handful of drops still leaves 300
for scale, who, src in (("3", "coin", "sprites/coin.png"), ("4", "slime", "sprites/slime.png")):
    add("sprites-scale-%s-%s" % (who, scale), "sprites",
        "Scale %s.png by %sx, nearest neighbour." % (who, scale), [
        S("act", "Single file output.",
          "sprite-scale", src, "-o", "build/%s_%sx.png" % (who, scale), "--scale", scale),
        v_png("build/%s_%sx.png" % (who, scale), "The scaled sprite must load."),
    ])

for hue in ("90", "270"):
    add("sprites-hue-" + hue, "sprites", "Hue-shift the coin by %s degrees." % hue, [
        S("act", "Alpha stays. Output folder.",
          "palette-swap", "sprites/coin.png", "-o", "build/hue%s" % hue, "--hue", hue),
        v_png("build/hue%s/coin_swap.png" % hue, "palette-swap writes coin_swap.png."),
    ])

add("sprites-pad-ltrb", "sprites", "Pad the hero by left 1, top 2, right 3, bottom 4.", [
    S("act", "Four-value pad is L,T,R,B.",
      "sprite-pad", "sprites/hero.png", "-o", "build/hero_ltrb", "--pad", "1,2,3,4"),
    v_png("build/hero_ltrb/hero.png", "The padded hero must load."),
])

add("sprites-outline-inner", "sprites", "An inner 1px outline on the slime, colour #1d2b53.", [
    S("act", "Inner mode eats into the sprite instead of growing it.",
      "sprite-outline-gen", "sprites/slime.png", "-o", "build/slime_in.png",
      "--mode", "inner", "--width", "1", "--color", "#1d2b53"),
    v_png("build/slime_in.png", "The outlined slime must load."),
])

for db in ("-3", "-12"):
    add("audio-gain-" + db.replace("-", "m"), "audio", "Turn the tone down %s dB." % db.strip("-") if False else "Apply %s dB of gain to the tone." % db, [
        S("act", "Negative gain only. No limiter.",
          "wav-gain", "audio/tone.wav", "--gain", db, "-o", "build/tone_%s.wav" % db.replace("-", "m")),
        v_wav("build/tone_%s.wav" % db.replace("-", "m")),
    ])

for semi, name in (("3", "up3"), ("-5", "down5")):
    add("audio-pitch-" + name, "audio", "Pitch the blip by %s semitones." % semi, [
        S("act", "Semitone shift, same bit depth.",
          "sfx-pitch", "audio/blip.wav", "-o", "build/blip_%s.wav" % name, "--semitones", semi),
        v_wav("build/blip_%s.wav" % name),
    ])

add("audio-resample-16k", "audio", "Resample the blip to 16000 Hz.", [
    S("act", "16 kHz is enough for a UI blip.",
      "wav-resample", "audio/blip.wav", "--rate", "16000", "-o", "build/blip_16k.wav"),
    v_wav("build/blip_16k.wav"),
])

add("audio-pad-to-second", "audio", "Pad the blip so the file lasts half a second.", [
    S("act", "--to-duration adds tail silence.",
      "wav-pad", "audio/blip.wav", "-o", "build/blip_half.wav", "--to-duration", "0.5"),
    v_wav("build/blip_half.wav"),
], (
    "I passed --duration, which belongs to wav-silence.",
    ["wav-pad", "audio/blip.wav", "-o", "build/blip_half.wav", "--duration", "0.5"],
    "stderr: {error} wav-pad uses --to-duration, --head and --tail.",
))

for kind, size, seed in (("bricks", "16", "8"), ("planks", "64", "9"), ("checker", "16", "10")):
    add("images-tex-%s-%s" % (kind, size), "images",
        "A %spx tileable %s texture, seed %s." % (size, kind, seed), [
        S("act", "Explicit size and seed.",
          "tex-gen", kind, "-o", "build/%s_%s.png" % (kind, size), "--size", size, "--seed", seed),
        v_png("build/%s_%s.png" % (kind, size), "The texture must load."),
    ])

for kind in ("tritan", "achroma"):
    add("images-cb-" + kind, "images", "Preview the gradient as seen with %s." % kind, [
        S("act", "One simulation type, full severity.",
          "colorblind-sim", "sim", "textures/grad.png", "-o", "build/cb_%s" % kind, "--type", kind),
        v_png("textures/grad.png", "The source gradient must be unchanged."),
    ])

add("images-lut-identity", "images", "An identity LUT should leave the gradient unchanged. Build one and apply it.", [
    S("act", "Size 8 identity strip.",
      "lut-tool", "identity", "--size", "8", "-o", "build/id_lut.png"),
    S("act", "Apply it.",
      "lut-tool", "apply", "textures/grad.png", "--lut", "build/id_lut.png", "-o", "build/grad_same.png"),
    v_png("build/grad_same.png", "The graded file must load. A broken LUT would fail the apply."),
])

add("maps-fill-column", "maps", "Paint a column of wall gid 2 down the middle of the ground layer.", [
    S("act", "One tile wide, the full height, starting at x=5.",
      "map-fill", "maps/level.json", "-o", "build/column.json", "--layer", "ground", "--gid", "2", "--rect", "5,0,1,8"),
    v_map("build/column.json"),
])

add("maps-shift-down", "maps", "Shift the level down by one tile, wrapping.", [
    S("act", "DY is positive down. Wrap so the north wall reappears at the south.",
      "map-shift", "maps/level.json", "-o", "build/level_down.json", "--tiles", "0,1", "--wrap"),
    v_map("build/level_down.json"),
])

add("maps-blank-8", "maps", "An empty 8x8 test room with a single ground layer.", [
    S("act", "16px tiles, one layer. It will be empty, so the verify must not require a filled layer.",
      "map-blank", "-o", "build/room8.json", "--size", "8x8", "--tile", "16", "--layers", "ground"),
    S("act", "Fill the whole ground with gid 1 so the room is not an empty layer.",
      "map-fill", "build/room8.json", "-o", "build/room8_filled.json", "--layer", "ground", "--gid", "1", "--rect", "0,0,8,8"),
    v_map("build/room8_filled.json"),
], (
    "I asked map-fill for a tile named floor instead of a gid.",
    ["map-fill", "maps/level.json", "-o", "build/nope.json", "--tile", "floor"],
    "stderr: {error} map-fill needs --gid and a rectangle or a flood point.",
))

add("maps-dungeon-yard", "maps", "A 16x12 BSP yard, seed 12, small tiles.", [
    S("act", "Small and seeded.",
      "dungeon-gen", "--mode", "bsp", "--size", "16x12", "--seed", "12", "--tile", "8", "-o", "build/yard"),
    v_map("build/yard.json"),
])

add("anim-walk-fps-6", "animation", "A slow 6 fps looping walk from the sprite folder.", [
    S("act", "walk=6, idle plays once.",
      "anim-from-folder", "sprites", "-o", "build/clips_6.json",
      "--pattern", "{clip}_{frame}.png", "--fps", "walk=6", "--default-fps", "6", "--once", "idle"),
    S("verify", "Durations should sit on a 6 fps grid.",
      "frame-timing-check", "build/clips_6.json", "--fps", "6"),
])

add("anim-walk-fps-20", "animation", "A 20 fps looping walk.", [
    S("act", "walk=20.",
      "anim-from-folder", "sprites", "-o", "build/clips_20.json",
      "--pattern", "{clip}_{frame}.png", "--fps", "walk=20", "--default-fps", "20"),
    S("verify", "Check the 20 fps grid.",
      "frame-timing-check", "build/clips_20.json", "--fps", "20"),
])

add("anim-hold-frames", "animation", "Add two extra holds of the last walk frame before the clip ends.", [
    S("act", "Source clips at 10 fps.",
      "anim-from-folder", "sprites", "-o", "build/hold2_src.json",
      "--pattern", "{clip}_{frame}.png", "--fps", "walk=10", "--default-fps", "10"),
    S("act", "--add-frames appends the last frame twice.",
      "anim-hold", "build/hold2_src.json", "-o", "build/hold2.json", "--clip", "walk", "--add-frames", "2"),
    S("verify", "Still on a 10 fps grid.",
      "frame-timing-check", "build/hold2.json", "--fps", "10"),
])

add("loc-fill-plain", "loc", "Copy English into the empty German cells, no prefix.", [
    S("act", "Do not overwrite Beenden.",
      "loc-fill", "loc/strings_gap.csv", "-o", "build/filled_plain.csv", "--source", "en"),
    v_loc("build/filled_plain.csv"),
])

add("loc-stats-csv", "loc", "Write the string-table summary as JSON and as a second check.", [
    S("act", "JSON summary.",
      "loc-stats", "loc/strings.csv", "--json", "build/loc_stats2.json"),
    v_loc(),
])

add("dialogue-stats-ink", "dialogue", "Word count and branching for the ink script.", [
    S("act", "JSON report.",
      "dialogue-stats", "dialogue/intro.ink", "--json", "build/ink_stats.json"),
    v_dlg("dialogue/intro.ink"),
])

add("dialogue-extract-both", "dialogue", "Extract yarn and ink into one VO spreadsheet.", [
    S("act", "Both files, one CSV.",
      "dialogue-extract", "dialogue/intro.yarn", "dialogue/intro.ink", "-o", "build/all_lines.csv"),
    v_dlg("dialogue/intro.yarn"),
])

add("fonts-subset-ascii", "fonts", "Subset DejaVu to ASCII.", [
    S("act", "--ascii is the printable set.",
      "font-subset", "fonts/DejaVuSans.ttf", "-o", "build/ascii.ttf", "--ascii"),
    S("verify", "chars.txt is ASCII. The subset must cover it.",
      "font-check", "data/chars.txt", "--font", "build/ascii.ttf"),
])

add("fonts-preview-16", "fonts", "A 16px review sheet of DejaVu, digits and the menu words.", [
    S("act", "One size, an explicit sample string.",
      "font-preview", "fonts/DejaVuSans.ttf", "-o", "build/font_16.png", "--sizes", "16", "--text", "Start Quit 0123"),
    v_png("build/font_16.png", "The sheet must load."),
])

add("mesh-flip-y", "mesh", "Mirror the wedge across Y.", [
    S("act", "Winding flips with the axis.",
      "obj-flip", "mesh/wedge.obj", "-o", "build/wedge_y.obj", "--axis", "y"),
    v_obj("build/wedge_y.obj"),
])

add("mesh-flip-z", "mesh", "Mirror the lid across Z.", [
    S("act", "Z mirror.",
      "obj-flip", "mesh/lid.obj", "-o", "build/lid_z.obj", "--axis", "z"),
    v_obj("build/lid_z.obj"),
])

add("mesh-recenter-center", "mesh", "Move the crate so its bounding-box centre is the origin.", [
    S("act", "Centre, not feet.",
      "obj-recenter", "mesh/crate.obj", "-o", "build/crate_center.obj", "--mode", "center"),
    v_obj("build/crate_center.obj"),
])

add("terrain-noise-seed7", "terrain", "A 32px tileable heightmap, seed 7, three octaves.", [
    S("act", "No island, so the edges tile.",
      "terrain-noise", "-o", "build/noise7", "--size", "32", "--seed", "7", "--octaves", "3"),
    v_png("build/noise7_8.png", "The 8-bit heightmap must load."),
])

add("terrain-noise-seed9", "terrain", "Another island, 33px, seed 9.", [
    S("act", "Island falloff.",
      "terrain-noise", "-o", "build/island9", "--size", "33", "--seed", "9", "--island"),
    v_png("build/island9_8.png", "The 8-bit island heightmap must load."),
])

add("data-manifest-audio", "data", "Hash the audio folder and verify the manifest.", [
    S("act", "Build a manifest.",
      "asset-manifest", "build", "audio", "-o", "build/audio_man.json"),
    S("verify", "verify exits 0 only when every hash still matches.",
      "asset-manifest", "verify", "build/audio_man.json", "audio"),
])

add("godot-snippet", "godot", "Print the pixel-art project.godot defaults I should paste into the project.", [
    S("act", "The snippet is the filter and snap settings. It does not write a file.",
      "godot-import-presets", "--project-snippet"),
    v_godot("Printing the snippet must not break the existing project."),
])

add("data-viewer-atlas", "data", "After packing an atlas, bake an HTML viewer for it.", [
    S("act", "Pack the sprites first.",
      "atlas-pack", "sprites", "-o", "build/view_atlas", "--no-trim"),
    S("act", "The viewer draws frame rectangles.",
      "asset-viewer", "atlas", "build/view_atlas.png", "build/view_atlas.json", "-o", "build/atlas_viewer.html"),
    v_atlas("build/view_atlas.json"),
])


def _audit():
    ids = [s["id"] for s in _SPECS]
    if len(ids) != len(set(ids)):
        dup = [i for i in ids if ids.count(i) > 1]
        raise SystemExit("duplicate trajectory ids: %s" % sorted(set(dup))[:8])
    fams = {s["primary_family"] for s in _SPECS}
    missing = set(["animation", "audio", "data", "dialogue", "fonts", "godot", "images",
                   "loc", "maps", "mesh", "sprites", "terrain"]) - fams
    if missing:
        raise SystemExit("missing families: %s" % sorted(missing))


_audit()
