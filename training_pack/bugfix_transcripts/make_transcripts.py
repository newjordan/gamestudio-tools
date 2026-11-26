#!/usr/bin/env python3
"""Assemble bugfix_transcripts.jsonl and bugfix_transcripts.md from the measured runs in runs/ and the
git diffs in diffs/ (git diff f750fe6 7f6ae09 -- <file>). Regenerate runs/ with rerun.sh first."""
import json, os, re
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda *p: open(os.path.join(H, *p), encoding="utf-8").read().rstrip("\n")

full = rd("runs", "v240_tests_full.txt")
def fail_block(test):
    m = re.search(r"_{3,} %s _{3,}\n(.*?)(?=\n_{3,} test_|\n=+ short test summary)" % re.escape(test), full, re.S)
    lines = [l for l in m.group(1).splitlines() if l.startswith(("E ", "E\t", ">")) or "Error" in l]
    return "\n".join(lines[-14:])
new = rd("runs", "v250_tests.txt")
def pass_line(test):
    return "\n".join(l for l in new.splitlines() if "::" + test + " " in l)

BUGS = [
 dict(id="bug1_dungeon_gen", tool="dungeon-gen", file="dungeon-gen/dungeon_gen.py",
  symptom="Building Ember Crypt floors: `gst dungeon-gen --mode bsp` -> `gst map-to-godot` produced a TileMapLayer with no cells, and the generated map had no room rectangles to place spawn, key and stairs objects in.",
  investigate=[
   "Open the generated f1.json: there is no `tilesets` key at all and only one layer (`dungeon`). Tiled and every kit consumer that maps GIDs to tiles need a tileset with firstgid.",
   "Read dungeon-gen/dungeon_gen.py (2.4.0) `to_tiled()` at line 109: it returns width/height/layers only; no tilesets, no layer ids, no nextlayerid/nextobjectid.",
   "`main()` line 128 calls `to_tiled(g)` without the `rooms` list that `bsp()` already returns, so room rectangles are computed and thrown away.",
   "map-to-godot resolves each GID through the map tilesets; with none it writes `0 cell(s)`."],
  cause="`to_tiled()` emitted a map without any tileset (and dropped the BSP rooms), so GIDs 1/2 resolved to nothing in map-to-godot and there was no room metadata for object placement.",
  note="Measured correction to the 2.5.0 CHANGELOG: map-reach and nav-to-godot treat walls the same on 2.4.0 and 2.5.0 for this map (352 of 748 tiles walkable with --solid-ids 2, all 748 without a solid flag on both versions). Neither tool reads the new solid=true tile property by default; the user-visible break was map-to-godot (0 vs 748 cells) and the missing rooms layer (0 vs 8 objects). The regression test comment says 2.4.0 wrote \"tilesets\": []; the measured 2.4.0 output has no tilesets key (KeyError).",
  tests=["test_dungeon_gen_json_is_a_usable_tiled_map"]),
 dict(id="bug2_atlas_to_godot", tool="atlas-to-godot", file="atlas-to-godot/atlas_to_godot.py",
  symptom="Ember Crypt actor animations packed with trimming jittered in Godot and their pivots moved: each frame shrank to its trimmed rect.",
  investigate=[
   "Run atlas-to-godot on a one-frame trimmed atlas (6x4 frame, spriteSourceSize 5,9 on a 16x16 sourceSize).",
   "The AtlasTexture sub-resource has only `region = Rect2(0, 0, 6, 4)`; no margin.",
   "Read atlas-to-godot/atlas_to_godot.py (2.4.0) `tres()` at line 63: line 116 writes `region` and nothing reads `spriteSourceSize` or `sourceSize`. `unpack_rotated()` (line 51) also returns the bare rotated crop.",
   "Godot AtlasTexture restores the untrimmed canvas through `margin = Rect2(left, top, extra_w, extra_h)`; loading the 2.4.0 .tres in Godot 4.7.2 reports the frame as 6x4."],
  cause="Trim data (spriteSourceSize / sourceSize) was ignored, so trimmed frames lost their offset and original canvas size.",
  tests=["test_atlas_to_godot_restores_trimmed_canvas", "test_atlas_to_godot_trimmed_frame_keeps_source_size_in_godot"]),
 dict(id="bug3_anim_from_folder", tool="anim-from-folder", file="anim-from-folder/anim_from_folder.py",
  symptom="Ember Crypt actor clips: build.sh line 130 passes `--fps 'player-walk-*=10,boss-charge=12' --once 'player-idle-*'` to anim-from-folder. On 2.4.0 a glob key does not match any clip (walk clips stay at --default-fps 8, idle clips keep looping, a WARN calls the glob an unknown clip), and a repeated --fps flag silently replaces the earlier one.",
  investigate=[
   "Run anim-from-folder with `--fps 'walk-*=10' --fps idle=4 --once 'idl*'` on 6 frames: walk clips come out at 8 fps (the default), idle loops, and a WARN names 'idl*' as unknown.",
   "Read anim-from-folder/anim_from_folder.py (2.4.0): `--fps` (line 102) and `--once` (line 104) are plain string options, so argparse keeps only the last occurrence.",
   "Line 116 parses fps into a dict keyed by literal names; `pack()` line 86 does `fps.get(k, default_fps)`, an exact-name lookup, so 'walk-*' never matches 'walk-down'."],
  cause="--fps/--once were single-value options looked up by exact clip name: repeated flags overwrote each other and glob keys never matched.",
  tests=["test_anim_from_folder_fps_accepts_globs_and_repeats"]),
 dict(id="bug4_asset_unused", tool="asset-unused", file="asset-unused/asset_unused.py",
  symptom="build.sh line 230 runs `gst asset-unused project --strict`. On the Ember Crypt project 2.4.0 listed project.godot itself and files it references (icon, main scene, autoloads, translations) plus the BMFont page PNGs as unused, so the --strict check failed on a clean project.",
  investigate=[
   "Run asset-unused on a 9-file mini project (project.godot -> main.tscn -> theme.tres -> f.fnt -> f.png, plus icon, autoload, translation, one orphan): 5 reported unused, only 1 is.",
   "Read asset-unused/asset_unused.py (2.4.0) `collect_refs()` at line 111: line 125 parses res:// refs only for .tscn/.tres/.gd/.shader/.gdshader, so project.godot (main scene, icon, autoloads, translations) is never read and is itself unreferenced.",
   "There is no branch for .fnt, so BMFont `page ... file=\"f.png\"` lines are never followed."],
  cause="The reference collector skipped project.godot/.cfg and BMFont .fnt files, so their outgoing references were never counted.",
  tests=["test_asset_unused_reads_project_godot_and_bmfont_pages"]),
 dict(id="bug5_nav_to_godot", tool="nav-to-godot", file="nav-to-godot/nav_to_godot.py",
  symptom="Ember Crypt floors are BSP rooms joined by corridors; enemies path on the NavigationRegion2D from nav-to-godot (build.sh line 112). Where a corridor met a room at a T-junction the two were separate islands and NavigationServer2D.map_get_path could not cross between them.",
  investigate=[
   "Build a 4x4 Tiled map with a 4-tile strip on row 0 and a corridor down column 0, run nav-to-godot, and query a path from (56,8) to (8,56) in Godot 4.7.2: it ends at (8,16), the strip edge.",
   "The scene has 8 vertices for 2 quads: (0,16) appears twice and the strip's bottom edge is 64->0 while the corridor's top edge is 0->16, so no edge has identical end vertices.",
   "Read nav-to-godot/nav_to_godot.py (2.4.0) `write_scene()` at line 239: lines 246-247 give every rectangle its own 4 vertices (`base = len(verts)`).",
   "Godot links navigation polygons in one region only across edges whose two vertices coincide, so both duplicate vertices and the T-junction (corridor corner at 16,16 lying inside the strip edge) leave islands."],
  cause="Rectangles got private vertices and T-junction corners were not inserted into neighbouring edges, so Godot saw no shared edge between touching walkable rects.",
  tests=["test_nav_to_godot_welds_t_junctions", "test_nav_to_godot_t_junction_path_in_godot"]),
 dict(id="bug6_gst_bundle", tool="gst bundle", file="gst",
  symptom="After `build.sh --movie` for Ember Crypt, `gst bundle` produced a 45 MB tarball: it packed examples/sample-topdown/work/ (the gitignored build scratch with the movie AVI and raw WAVs).",
  investigate=[
   "Bundle the real 2.5.0 tree (with the leftover 56 MB work/ folder) using the 2.4.0 gst and the 2.5.0 gst; measured below.",
   "Read gst (2.4.0) `cmd_bundle()` at line 499: line 508 walks ROOT with os.walk and prunes only BUNDLE_SKIP_DIRS (line 28: samples, __pycache__, .pytest_cache, .git, release-bundles, .godot); `work` is not in it.",
   "Adding `work` to BUNDLE_SKIP_DIRS would also drop any tool folder named work, so the skip must be scoped to examples/<game>/work."],
  cause="The bundle walker did not honour the examples/*/work gitignore rule, so build scratch was shipped.",
  real_scale=("Same 2.5.0 tree, 56 MB examples/sample-topdown/work present (bundle written to /tmp):\n"
              "2.4.0 gst bundle: 1517 files, 45093483 bytes, 408 files from examples/sample-topdown/work/\n"
              "2.5.0 gst bundle: 1045 files, 15700987 bytes, 0 files from examples/sample-topdown/work/"),
  tests=["test_bundle_skips_example_work_dirs"]),
]

recs, md = [], ["# Worked bug-fix transcripts, gamestudio-tools 2.5.0", "",
  "Generated by make_transcripts.py from measured runs (runs/) and git diffs (diffs/). Old code = worktree at f750fe6 (2.4.0), new = 7f6ae09 (2.5.0).", ""]
for b in BUGS:
    old, newo = rd("runs", b["id"] + "_240.txt"), rd("runs", b["id"] + "_250.txt")
    diff = rd("diffs", os.path.basename(b["file"]) + ".diff")
    t_old = "\n\n".join("%s (2.4.0): FAILED\n%s" % (t, fail_block(t)) for t in b["tests"])
    t_new = "\n".join(pass_line(t) for t in b["tests"])
    steps = [{"step": "symptom", "content": b["symptom"]},
             {"step": "reproduce", "command": "GST_ROOT=<2.4.0 worktree> bash repro/%s.sh" % b["id"], "output": old}]
    if b.get("real_scale"):
        steps.append({"step": "reproduce_real_scale", "output": b["real_scale"]})
    steps += [{"step": "investigate", "n": i + 1, "content": s} for i, s in enumerate(b["investigate"])]
    steps += [{"step": "root_cause", "content": b["cause"]},
              {"step": "fix", "command": "git diff f750fe6 7f6ae09 -- " + b["file"], "diff": diff},
              {"step": "regression_test", "file": "tests/test_v25.py", "tests": b["tests"]},
              {"step": "test_on_2.4.0", "command": "pytest tests/test_v25.py -k <test> (in the 2.4.0 worktree)", "output": t_old},
              {"step": "test_on_2.5.0", "command": "pytest tests/test_v25.py -k <test>", "output": t_new},
              {"step": "verify_fix", "command": "GST_ROOT=<2.5.0 checkout> bash repro/%s.sh" % b["id"], "output": newo}]
    if b.get("note"):
        steps.append({"step": "measured_note", "content": b["note"]})
    recs.append({"id": b["id"], "tool": b["tool"], "kit_version_broken": "2.4.0", "kit_version_fixed": "2.5.0",
                 "commit_broken": "f750fe6", "commit_fixed": "7f6ae09", "file": b["file"], "steps": steps})
    md += ["## %s (`%s`)" % (b["id"], b["tool"]), ""]
    for s in steps:
        md.append("**%s%s**" % (s["step"], " %d" % s["n"] if "n" in s else ""))
        if "content" in s: md += [s["content"], ""]
        if "command" in s: md += ["```", "$ " + s["command"], "```"]
        if "tests" in s: md += [", ".join(s["tests"]), ""]
        if "output" in s: md += ["```", s["output"], "```", ""]
        if "diff" in s: md += ["```diff", s["diff"], "```", ""]
with open(os.path.join(H, "bugfix_transcripts.jsonl"), "w") as f:
    for r in recs: f.write(json.dumps(r) + "\n")
open(os.path.join(H, "bugfix_transcripts.md"), "w").write("\n".join(md) + "\n")
print(len(recs), "transcripts")
