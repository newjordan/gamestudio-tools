"""Fuzz targets: every kit tool that reads WAV, PNG/GIF, Tiled JSON/TMX,
GLB/glTF, OBJ, atlas JSON, CSV loc, Yarn/ink or BMFont.

argv templates use placeholders:
  {input}  mutated file (extension already matches the kind)
  {input2} a sibling valid seed of the same kind (or a second mutated copy)
  {out}    output path (file)
  {outdir} output directory
  {sidecar} helper path for extra required files (rules, remap, palette, schema, text)
"""
from __future__ import annotations

# (name, kind, argv)
# kind selects the seed / mutation family.

def _t(name, kind, argv):
    return {"name": name, "kind": kind, "argv": argv}


# Shared argv snippets
O = ["{input}", "-o", "{out}"]
OD = ["{input}", "-o", "{outdir}"]
IN = ["{input}"]
TWO = ["{input}", "{input2}"]
TWO_O = ["{input}", "{input2}", "-o", "{out}"]

TARGETS = [
    # ----- WAV -----
    _t("audio-concat", "wav", TWO_O),
    _t("audio-convert", "wav", ["{input}", "-o", "{outdir}"]),
    _t("audio-tidy", "wav", ["{input}", "-o", "{outdir}"]),
    _t("cue-sheet", "wav", ["{input}", "--json", "{out}"]),
    _t("loop-finder", "wav", ["{input}", "--json", "{out}"]),
    _t("loop-xfade", "wav", O),
    _t("sfx-bank", "wav", ["pack", "{input}", "-o", "{out}"]),
    _t("sfx-envelope", "wav", ["{input}", "--json", "{out}"]),
    _t("sfx-normalize", "wav", ["{input}", "-o", "{outdir}"]),
    _t("sfx-pitch", "wav", O),
    _t("sfx-reverse", "wav", O),
    _t("sfx-spectrogram", "wav", O),
    _t("sfx-variants", "wav", O),
    _t("vo-diff", "wav", ["{input}", "{input2}", "--json", "{out}"]),
    _t("voice-slate", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-batch-meta", "wav", ["{input}", "--json", "{out}"]),
    _t("wav-chan-split", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-chan-swap", "wav", O),
    _t("wav-dc-remove", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-fade", "wav", O),
    _t("wav-gain", "wav", ["{input}", "--gain", "-3", "-o", "{out}"]),
    _t("wav-gap-squeeze", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-gate", "wav", O),
    _t("wav-invert", "wav", O),
    _t("wav-limit", "wav", O),
    _t("wav-loop-meta", "wav", ["show", "{input}"]),
    _t("wav-loop-snap", "wav", O),
    _t("wav-loud-apply", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-mono", "wav", O),
    _t("wav-pad", "wav", O),
    _t("wav-resample", "wav", ["{input}", "--rate", "16000", "-o", "{out}"]),
    _t("wav-silence", "wav", O),
    _t("wav-split-silence", "wav", ["{input}", "-o", "{outdir}"]),
    _t("wav-trim", "wav", ["{input}", "-o", "{outdir}"]),

    # ----- PNG -----
    _t("alpha-bleed", "png", O),
    _t("colorblind-sim", "png", ["sim", "{input}", "-o", "{out}"]),
    _t("contact-sheet", "png", O),
    _t("curve-trace", "png", O),
    _t("frames-to-sheet", "png", O),
    _t("hitbox-gen", "png", O),
    _t("image-diff", "png", ["{input}", "{input2}", "--json", "{out}"]),
    _t("nine-slice", "png", ["{input}", "-o", "{out}"]),
    _t("normal-fix", "png", ["check", "{input}"]),
    _t("onion-skin", "png", O),
    _t("palette-extract", "png", O),
    _t("palette-apply", "png", ["{input}", "-o", "{out}", "--palette", "{sidecar}"]),
    _t("palette-swap", "png", ["{input}", "-o", "{out}", "--map", "{sidecar}"]),
    _t("pixel-lint", "png", ["{input}", "--json", "{out}"]),
    _t("pixelize", "png", O),
    _t("sheet-pad", "png", O),
    _t("sprite-align", "png", O),
    _t("sprite-angles", "png", O),
    _t("sprite-canvas", "png", ["{input}", "-o", "{out}", "--size", "16x16"]),
    _t("sprite-fx", "png", O),
    _t("sprite-outline-gen", "png", O),
    _t("sprite-pad", "png", ["{input}", "-o", "{out}", "--pad", "1"]),
    _t("sprite-pivot", "png", O),
    _t("sprite-recolor", "png", O),
    _t("sprite-reframe", "png", ["{input}", "-o", "{out}", "--size", "16x16"]),
    _t("sprite-rotate", "png", ["{input}", "-o", "{out}", "--angle", "90"]),
    _t("sprite-scale", "png", O),
    _t("sprite-shadow", "png", O),
    _t("sprite-slice", "png", ["{input}", "-o", "{outdir}"]),
    _t("sprite-stack", "png", ["{input}", "-o", "{out}", "--layers", "2"]),
    _t("sprite-trim", "png", O),
    _t("sprite-unpad", "png", ["{input}", "-o", "{out}", "--pad", "1"]),
    _t("texture-resize", "png", O),
    _t("texture-seamless", "png", O),
    _t("tile-dedupe", "png", ["{input}", "--tile", "8", "-o", "{out}"]),
    _t("tile-extrude", "png", ["{input}", "--tile", "8x8", "-o", "{out}"]),
    _t("tileset-from-image", "png", ["{input}", "--tile", "8", "-o", "{out}"]),
    _t("autotile-gen", "png", ["{input}", "--tile", "8", "-o", "{out}"]),
    _t("channel-pack", "png", ["unpack", "{input}", "-o", "{outdir}"]),

    # ----- GIF -----
    _t("gif-optimize", "gif", O),
    _t("gif-to-frames", "gif", ["{input}", "-o", "{outdir}"]),
    _t("tile-anim-gif", "gif", O),
    _t("spritesheet-gif", "atlas", ["{input}", "-o", "{out}"]),  # atlas+sheet; also fuzz gif tool via gif kinds above

    # ----- atlas JSON -----
    _t("atlas-convert", "atlas", ["{input}", "--to", "hash", "-o", "{out}"]),
    _t("atlas-merge", "atlas", TWO_O + ["--no-pot", "--padding", "0"]),
    _t("atlas-rename", "atlas", ["{input}", "-o", "{out}", "--pattern", "s/_/-/"]),
    _t("atlas-sort", "atlas", O),
    _t("atlas-to-godot", "atlas", O),
    _t("atlas-unpack", "atlas", ["{input}", "-o", "{outdir}"]),
    _t("atlas-validate", "atlas", IN),
    _t("sprite-sheet-optimize", "atlas", ["{input}", "-o", "{out}"]),
    _t("sprite-flip-sheet", "atlas", ["{input}", "-o", "{out}"]),  # may need sheet; tool often finds it from meta
    _t("sheet-pad-atlas", "atlas", ["{input}", "-o", "{out}"]),  # alias handled below? skip if not a tool
    _t("atlas-pack", "png", O),

    # ----- Tiled JSON -----
    _t("map-auto-layer", "tiled", ["{input}", "--rules", "{sidecar}", "-o", "{out}"]),
    _t("map-chunk", "tiled", O),
    _t("map-clean", "tiled", O),
    _t("map-crop", "tiled", O),
    _t("map-diff", "tiled", TWO),
    _t("map-fill", "tiled", ["{input}", "--gid", "1", "-o", "{out}"]),
    _t("map-layer-merge", "tiled", O),
    _t("map-layer-rename", "tiled", ["{input}", "--pattern", "ground", "--repl", "floor", "-o", "{out}"]),
    _t("map-layer-split", "tiled", O),
    _t("map-merge", "tiled", TWO_O),
    _t("map-mirror", "tiled", O),
    _t("map-outline", "tiled", ["{input}", "--json", "{out}"]),
    _t("map-pad", "tiled", O),
    _t("map-path", "tiled", ["{input}", "--json", "{out}"]),
    _t("map-reach", "tiled", ["{input}", "--json", "{out}"]),
    _t("map-reorder", "tiled", O),
    _t("map-rotate", "tiled", ["{input}", "--degrees", "90", "-o", "{out}"]),
    _t("map-scale", "tiled", O),
    _t("map-shift", "tiled", O),
    _t("map-stamp", "tiled", ["{input}", "--prefab", "{input2}", "-o", "{out}"]),
    _t("godot-tileset", "tiled", O),
    _t("nav-grid", "tiled", O),
    _t("room-graph", "tiled", ["{input}", "--json", "{out}"]),
    _t("tile-colliders", "tiled", O),
    _t("tile-preview", "tiled", O),
    _t("tile-replace", "tiled", ["{input}", "--remap", "{sidecar}", "-o", "{out}"]),
    _t("tilemap-stats", "tiled", IN),
    _t("tmx-anim-list", "tiled", ["{input}", "--json", "{out}"]),
    _t("tmx-decode", "tiled", O),
    _t("tmx-embed-tileset", "tiled", O),
    _t("tmx-encode", "tiled", O),
    _t("tmx-gid-usage", "tiled", ["{input}", "--json", "{out}"]),
    _t("tmx-infinite-to-finite", "tiled", O),
    _t("tmx-layer-export", "tiled", O),
    _t("tmx-layer-filter", "tiled", O),
    _t("tmx-layer-opacity", "tiled", ["{input}", "--json", "{out}"]),
    _t("tmx-objects-csv", "tiled", ["{input}", "-o", "{out}"]),
    _t("tmx-props-lint", "tiled", ["{input}", "--schema", "{sidecar}"]),
    _t("tmx-tileset-list", "tiled", ["{input}", "--json", "{out}"]),
    _t("wfc-tiles", "tiled", O),

    # ----- TMX -----
    _t("tmx-to-json", "tmx", ["{input}", "-o", "{out}"]),
    _t("tmx-anim-list-tmx", "tmx", ["{input}", "--json", "{out}"]),
    _t("tmx-gid-usage-tmx", "tmx", ["{input}", "--json", "{out}"]),
    _t("tmx-tileset-list-tmx", "tmx", ["{input}", "--json", "{out}"]),
    _t("tmx-objects-csv-tmx", "tmx", ["{input}", "-o", "{out}"]),
    _t("tmx-decode-tmx", "tmx", O),
    _t("tmx-world", "tiled", O),

    # ----- GLB / glTF -----
    _t("glb-attr-drop", "glb", ["{input}", "-o", "{out}", "--drop", "NORMAL"]),
    _t("glb-attr-rename", "glb", ["{input}", "-o", "{out}", "--pattern", "s/NORMAL/NORMAL2/"]),
    _t("glb-center", "glb", O),
    _t("glb-diff", "glb", TWO),
    _t("glb-extras-strip", "glb", O),
    _t("glb-lod", "glb", ["{input}", "-o", "{outdir}"]),
    _t("glb-merge", "glb", TWO_O),
    _t("glb-quantize", "glb", O),
    _t("glb-rename-nodes", "glb", O),
    _t("glb-split", "glb", O),
    _t("glb-uv-transform", "glb", O),
    _t("glb-weld", "glb", O),
    _t("gltf-inspect", "glb", IN),
    _t("gltf-strip", "glb", O),
    _t("gltf-inspect-gltf", "gltf", IN),
    _t("gltf-strip-gltf", "gltf", O),
    _t("glb-extras-strip-gltf", "gltf", O),
    _t("mesh-colliders", "glb", ["{input}", "--json", "{out}"]),
    _t("mesh-pivot-fix", "glb", O),
    _t("uv-check", "glb", IN),

    # ----- OBJ -----
    _t("obj-bounds", "obj", O),
    _t("obj-clean-uv", "obj", O),
    _t("obj-decimate", "obj", O),
    _t("obj-drop-unused", "obj", O),
    _t("obj-flip", "obj", O),
    _t("obj-merge", "obj", TWO_O),
    _t("obj-normals", "obj", O),
    _t("obj-recenter", "obj", O),
    _t("obj-split", "obj", O),
    _t("obj-subdivide", "obj", O),
    _t("obj-to-glb", "obj", ["{input}", "-o", "{outdir}"]),
    _t("obj-transform", "obj", O),
    _t("obj-triangulate", "obj", O),
    _t("obj-uv-unwrap", "obj", O),
    _t("obj-validate", "obj", IN),
    _t("obj-weld", "obj", O),

    # ----- CSV loc -----
    _t("loc-check", "loc", IN),
    _t("loc-diff", "loc", TWO),
    _t("loc-fill", "loc", O),
    _t("loc-fit", "loc", ["{input}", "--json", "{out}"]),
    _t("loc-icu-extract", "loc", O),
    _t("loc-join", "loc", TWO_O),
    _t("loc-key-lint", "loc", IN),
    _t("loc-merge", "loc", TWO_O),
    _t("loc-missing", "loc", IN),
    _t("loc-placeholder-lint", "loc", IN),
    _t("loc-plurals", "loc", IN),
    _t("loc-rename", "loc", ["{input}", "-o", "{out}", "--pattern", "s/ui./hud./"]),
    _t("loc-sort", "loc", O),
    _t("loc-split", "loc", OD),
    _t("loc-stats", "loc", IN),
    _t("pseudoloc", "loc", O),

    # ----- Yarn / ink -----
    _t("dialogue-extract", "yarn", ["{input}", "-o", "{out}"]),
    _t("dialogue-graph", "yarn", ["{input}", "--mermaid", "{out}"]),
    _t("dialogue-stats", "yarn", ["{input}", "--json", "{out}"]),
    _t("dialogue-extract-ink", "ink", ["{input}", "-o", "{out}"]),
    _t("dialogue-graph-ink", "ink", ["{input}", "--mermaid", "{out}"]),
    _t("dialogue-stats-ink", "ink", ["{input}", "--json", "{out}"]),

    # ----- BMFont -----
    _t("font-check", "fnt", ["{sidecar}", "--font", "{input}", "--json", "{out}"]),

    # ----- batch 31 readers -----
    _t("map-to-godot", "tiled", ["{input}", "-o", "{out}"]),
    _t("map-to-godot-tmx", "tmx", ["{input}", "-o", "{out}"]),
    _t("loc-to-godot", "loc", O),
    _t("dialogue-lint", "yarn", IN),
    _t("dialogue-lint-ink", "ink", IN),
    _t("texture-budget", "png", ["{input}", "--json", "{out}"]),
    _t("ase-decode", "ase", ["{input}", "-o", "{outdir}"]),

    # ----- batch 32 readers -----
    _t("map-objects-to-godot", "tiled", ["{input}", "-o", "{out}"]),
    _t("map-objects-to-godot-tmx", "tmx", ["{input}", "-o", "{out}"]),
    _t("map-objects-to-godot-anim", "tiledanim", ["{input}", "-o", "{out}"]),
    _t("map-objects-to-godot-tmxext", "tmxext", ["{input}", "-o", "{out}"]),
    _t("map-objects-to-godot-tsx", "tsx", ["{sidecar}", "-o", "{out}"]),
    _t("nav-to-godot", "tiled", ["{input}", "-o", "{out}"]),
    _t("nav-to-godot-tmx", "tmx", ["{input}", "-o", "{out}"]),
    _t("nav-to-godot-colliders", "colliders", ["{sidecar}", "--colliders", "{input}", "-o", "{out}"]),
    _t("tilemap-stats-zstd", "tiledzstd", IN),
    _t("tmx-decode-zstd", "tiledzstd", O),
    _t("map-clean-zstd", "tiledzstd", O),
    _t("tmx-to-json-zstd", "tmxzstd", ["{input}", "-o", "{out}"]),
    _t("tile-colliders-to-godot", "tiled", ["{input}", "-o", "{out}"]),
    _t("hitbox-to-godot", "atlas", ["{input}", "-o", "{out}"]),
    _t("nine-slice-to-godot", "png", ["{input}", "-o", "{out}", "--insets", "1,1,1,1"]),
    _t("ase-json-import", "asejson", ["{input}", "-o", "{out}"]),
    _t("font-to-godot", "fnt", ["{input}", "-o", "{out}"]),
    _t("font-to-godot-xml", "fntxml", ["{input}", "-o", "{out}"]),
    _t("font-to-godot-bin", "fntbin", ["{input}", "-o", "{out}"]),
    _t("ase-to-godot", "ase", ["{input}", "-o", "{out}", "--frames-dir", "{outdir}"]),
    _t("data-to-godot", "loc", ["{input}", "-o", "{out}"]),
]

# Names that are aliases (same tool, different kind / argv). The tool name is
# the part before a "-" suffix only when the alias is listed here.

ALIASES = {
    "tmx-anim-list-tmx": "tmx-anim-list",
    "tmx-gid-usage-tmx": "tmx-gid-usage",
    "tmx-tileset-list-tmx": "tmx-tileset-list",
    "tmx-objects-csv-tmx": "tmx-objects-csv",
    "tmx-decode-tmx": "tmx-decode",
    "gltf-inspect-gltf": "gltf-inspect",
    "gltf-strip-gltf": "gltf-strip",
    "glb-extras-strip-gltf": "glb-extras-strip",
    "dialogue-extract-ink": "dialogue-extract",
    "dialogue-graph-ink": "dialogue-graph",
    "dialogue-stats-ink": "dialogue-stats",
    "dialogue-lint-ink": "dialogue-lint",
    "map-to-godot-tmx": "map-to-godot",
    "map-objects-to-godot-tmx": "map-objects-to-godot",
    "map-objects-to-godot-anim": "map-objects-to-godot",
    "map-objects-to-godot-tmxext": "map-objects-to-godot",
    "map-objects-to-godot-tsx": "map-objects-to-godot",
    "nav-to-godot-tmx": "nav-to-godot",
    "tilemap-stats-zstd": "tilemap-stats",
    "tmx-decode-zstd": "tmx-decode",
    "map-clean-zstd": "map-clean",
    "tmx-to-json-zstd": "tmx-to-json",
    "nav-to-godot-colliders": "nav-to-godot",
    "font-to-godot-xml": "font-to-godot",
    "font-to-godot-bin": "font-to-godot",
    "sheet-pad-atlas": "sheet-pad",
}


def tool_name(entry):
    return ALIASES.get(entry["name"], entry["name"])


def iter_targets(only=None):
    for t in TARGETS:
        # drop accidental non-tools
        if t["name"] == "sheet-pad-atlas":
            # sheet-pad takes sheet + optional atlas; keep as atlas kind via alias
            pass
        name = tool_name(t)
        if only and name not in only and t["name"] not in only:
            continue
        yield t
