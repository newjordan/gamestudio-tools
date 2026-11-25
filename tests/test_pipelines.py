"""End-to-end pipeline integration tests (fixtures built in tmp; no samples/ dependency)."""
import csv, json, os

import numpy as np
import pytest
from PIL import Image

import atlas_pack, atlas_unpack, sheet_pad, atlas_to_godot, sprite_stack, sprite_canvas, anim_from_folder, sprite_recolor
import tmx_props_lint, map_clean, map_crop, tilemap_stats, tmx_embed_tileset, map_layer_merge, nav_grid, map_auto_layer, tmx_object_types, tmx_layer_opacity, map_rotate, map_fill, map_mirror, map_scale, tmx_encode
import dialogue_extract, voice_slate, wav_dc_remove, wav_trim, wav_loud_apply, audio_tidy, wav_fade, wav_pad, sfx_reverse, wav_loop_snap, sfx_normalize, wav_chan_swap
import obj_to_glb, gltf_strip, glb_rename_nodes, mesh_pivot_fix, material_audit, obj_triangulate, obj_normals, obj_bounds, glb_split, obj_merge, glb_uv_transform, obj_split
import loc_missing, loc_placeholder_lint, loc_check, loc_plurals, loc_icu_extract, loc_sort, loc_key_lint, loc_merge
import tileset_gen, tileset_wang, godot_tileset, tileset_merge, tileset_split


def _sprite(path, color):
    im = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    for y in range(8):
        for x in range(8):
            im.putpixel((x, y), color)
    im.save(path)


def test_pipeline_sprite_to_godot(tmp_path):
    src = tmp_path / "sprites"; src.mkdir()
    _sprite(src / "walk_01.png", (255, 0, 0, 255))
    _sprite(src / "walk_02.png", (0, 255, 0, 255))
    _sprite(src / "idle_01.png", (0, 0, 255, 255))
    assert anim_from_folder.main([str(src), "-o", str(tmp_path / "clips.json"),
                                  "--pattern", "{clip}_{frame}.png", "--default-fps", "10",
                                  "--fps", "idle=6"]) == 0
    work = tmp_path / "out"; work.mkdir()
    assert atlas_pack.main([str(src), "-o", str(work / "atlas"), "--padding", "0", "--no-pot"]) == 0
    assert (work / "atlas.png").exists() and (work / "atlas.json").exists()
    unpacked = work / "unpacked"
    assert atlas_unpack.main([str(work / "atlas.json"), "-o", str(unpacked), "--untrim"]) == 0
    assert Image.open(unpacked / "walk_01.png").tobytes() == Image.open(src / "walk_01.png").tobytes()
    assert sheet_pad.main([str(work / "atlas.png"), str(work / "atlas.json"),
                           "-o", str(work / "padded.png"), "--atlas-out", str(work / "padded.json"),
                           "--pad", "2", "--keep-layout"]) == 0
    pad = Image.open(work / "padded.png")
    raw = Image.open(work / "atlas.png")
    assert pad.width > raw.width and pad.height > raw.height
    assert json.load(open(work / "padded.json"))["frames"]
    assert atlas_to_godot.main([str(work / "padded.json"), "-o", str(work / "hero.tres"),
                                "--clips", str(tmp_path / "clips.json"),
                                "--res", "res://art/padded.png"]) == 0
    text = open(work / "hero.tres").read()
    assert '[gd_resource type="SpriteFrames"' in text
    assert 'path="res://art/padded.png"' in text
    assert '&"walk"' in text and '&"idle"' in text

    # sprite-stack + sprite-canvas sit naturally in front of a pack
    parts = tmp_path / "parts"; parts.mkdir()
    _sprite(parts / "hero.body.png", (255, 0, 0, 255))
    _sprite(parts / "hero.shadow.png", (0, 0, 0, 128))
    stacked = tmp_path / "stacked"
    assert sprite_stack.main([str(parts), "-o", str(stacked), "--layers", "shadow,body"]) == 0
    canvased = tmp_path / "canvased"
    assert sprite_canvas.main([str(stacked), "-o", str(canvased), "--size", "16x16",
                               "--anchor", "feet"]) == 0
    assert Image.open(canvased / "hero.png").size == (16, 16)
    recolored = tmp_path / "recolored"
    assert sprite_recolor.main([str(canvased), "-o", str(recolored), "--map", "ff0000:3366ff"]) == 0
    assert Image.open(recolored / "hero.png").size == (16, 16)


def test_pipeline_tiled_map_hygiene(tmp_path):
    m = {
        "type": "map", "width": 8, "height": 6, "tilewidth": 16, "tileheight": 16,
        "tilesets": [
            {"name": "dungeon", "firstgid": 1, "tilecount": 8},
            {"name": "unused", "firstgid": 20, "tilecount": 4},
        ],
        "layers": [
            {"type": "tilelayer", "name": "fg_ground", "width": 8, "height": 6, "visible": True,
             "data": [0] * 32 + [0, 0, 1, 2, 0, 0, 0, 0] + [0, 0, 3, 4, 0, 0, 0, 0]},
            {"type": "tilelayer", "name": "empty_hidden", "width": 8, "height": 6, "visible": False,
             "data": [0] * 48},
            {"type": "objectgroup", "name": "objs", "objects": [
                {"id": 1, "name": "door", "type": "Door", "x": 32, "y": 64, "width": 16, "height": 16,
                 "properties": [{"name": "dest", "type": "string", "value": "hall"}]}
            ]},
        ],
    }
    json.dump(m, open(tmp_path / "level.json", "w"))
    json.dump({"objects": {"Door": {"required": ["dest"], "types": {"dest": "string"}}}},
              open(tmp_path / "schema.json", "w"))
    assert tmx_props_lint.main([str(tmp_path / "level.json"), "--schema", str(tmp_path / "schema.json")]) == 0
    assert map_clean.main([str(tmp_path / "level.json"), "-o", str(tmp_path / "clean.json"), "--pretty"]) == 0
    clean = json.load(open(tmp_path / "clean.json"))
    names = [l["name"] for l in clean["layers"]]
    assert "empty_hidden" not in names and "fg_ground" in names
    assert all(t.get("name") != "unused" for t in clean["tilesets"])
    assert map_crop.main([str(tmp_path / "clean.json"), "-o", str(tmp_path / "crop.json"),
                          "--margin", "1", "--pretty"]) == 0
    crop = json.load(open(tmp_path / "crop.json"))
    assert crop["width"] < m["width"] or crop["height"] < m["height"]
    assert tilemap_stats.main([str(tmp_path / "crop.json"), "--json", str(tmp_path / "stats.json"),
                               "--fail-on-unused-tileset"]) == 0
    stats = json.load(open(tmp_path / "stats.json"))
    assert stats  # non-empty report
    assert map_layer_merge.main([str(tmp_path / "crop.json"), "-o", str(tmp_path / "flat.json"),
                                 "--drop-sources", "--name", "ground", "--pretty"]) == 0
    flat = json.load(open(tmp_path / "flat.json"))
    assert [l["name"] for l in flat["layers"] if l.get("type") == "tilelayer"] == ["ground"]
    assert nav_grid.main([str(tmp_path / "flat.json"), "-o", str(tmp_path / "nav.png"),
                          "--ground-layer", "ground", "--scale", "4"]) == 0
    assert (tmp_path / "nav.png").exists()
    types = {"Door": {"properties": {"dest": {"type": "string", "default": ""},
                                     "locked": {"type": "bool", "default": False}}}}
    json.dump(types, open(tmp_path / "types.json", "w"))
    assert tmx_object_types.main(["apply", str(tmp_path / "flat.json"), "--types", str(tmp_path / "types.json"),
                                  "-o", str(tmp_path / "typed.json")]) == 0
    assert tmx_object_types.main(["lint", str(tmp_path / "typed.json"), "--types", str(tmp_path / "types.json")]) == 0
    rules = {"source": "ground", "name": "auto", "match": "solid",
             "rules": [{"center": [1, 2, 3, 4], "gid": 8}]}
    json.dump(rules, open(tmp_path / "rules.json", "w"))
    assert map_auto_layer.main([str(tmp_path / "typed.json"), "--rules", str(tmp_path / "rules.json"),
                                "-o", str(tmp_path / "deco.json")]) == 0
    assert any(l.get("name") == "auto" for l in json.load(open(tmp_path / "deco.json"))["layers"])
    assert tmx_layer_opacity.main([str(tmp_path / "deco.json"), "-o", str(tmp_path / "faded.json"),
                                   "--set", "auto=0.5"]) == 0
    assert map_fill.main([str(tmp_path / "faded.json"), "-o", str(tmp_path / "filled.json"),
                          "--layer", "ground", "--rect", "0,0,1,1", "--gid", "1"]) == 0
    assert map_rotate.main([str(tmp_path / "filled.json"), "-o", str(tmp_path / "rot.json"),
                            "--degrees", "90"]) == 0
    rot = json.load(open(tmp_path / "rot.json"))
    assert rot["width"] == json.load(open(tmp_path / "filled.json"))["height"]
    assert map_mirror.main([str(tmp_path / "rot.json"), "-o", str(tmp_path / "mh.json"), "--axis", "h"]) == 0
    assert map_mirror.main([str(tmp_path / "mh.json"), "-o", str(tmp_path / "mh2.json"), "--axis", "h"]) == 0
    assert json.load(open(tmp_path / "mh2.json"))["layers"][0]["data"] == json.load(open(tmp_path / "rot.json"))["layers"][0]["data"]
    assert map_scale.main([str(tmp_path / "mh2.json"), "-o", str(tmp_path / "scaled.json"), "--factor", "2"]) == 0
    assert json.load(open(tmp_path / "scaled.json"))["tilewidth"] == 2 * json.load(open(tmp_path / "mh2.json"))["tilewidth"]
    assert tmx_encode.main([str(tmp_path / "scaled.json"), "-o", str(tmp_path / "enc.json"),
                            "--encoding", "csv"]) == 0
    assert json.load(open(tmp_path / "enc.json"))["layers"][0].get("encoding") == "csv"


def test_pipeline_vo_slate_to_loudness(tmp_path):
    yarn = tmp_path / "intro.yarn"
    yarn.write_text("title: Intro\n---\nAva: Hello there, captain. #line:l1\nAva: We should get moving. #line:l2\n===\n")
    assert dialogue_extract.main([str(yarn), "-o", str(tmp_path / "lines.csv")]) == 0
    rows = list(csv.DictReader(open(tmp_path / "lines.csv")))
    assert len(rows) == 2 and all(r.get("text") for r in rows)
    assert voice_slate.main([str(tmp_path / "lines.csv"), "-o", str(tmp_path / "slate")]) == 0
    assert (tmp_path / "slate" / "slate.md").exists() and (tmp_path / "slate" / "summary.json").exists()
    # synthesise takes named after slate targets
    takes = tmp_path / "takes"; takes.mkdir()
    slate_rows = list(csv.DictReader(open(tmp_path / "slate" / "ava.csv")))
    assert slate_rows and all(r["target"].endswith(".wav") for r in slate_rows)
    sr = 8000
    n = int(sr * 0.8)
    t = np.linspace(0, 0.8, n, endpoint=False)
    tone = 0.2 * np.sin(2 * np.pi * 220 * t)
    # leading silence, then tone, plus a whole-file DC so wav-dc-remove has work to do
    x = np.zeros(n, dtype=np.float64)
    x[int(sr * 0.15):] = tone[int(sr * 0.15):]
    x = x + 0.25
    for r in slate_rows:
        audio_tidy.write_wav(str(takes / r["target"]), x.reshape(-1, 1), sr, bits=16)
    assert wav_dc_remove.main([str(takes), "-o", str(tmp_path / "dc")]) == 0
    assert wav_trim.main([str(tmp_path / "dc"), "-o", str(tmp_path / "trim")]) == 0
    # trimmed files should be shorter than the originals
    for r in slate_rows:
        a, _ = audio_tidy.read_wav(str(takes / r["target"]))
        b, _ = audio_tidy.read_wav(str(tmp_path / "trim" / r["target"]))
        assert len(b) < len(a)
    assert wav_loud_apply.main([str(tmp_path / "trim"), "-o", str(tmp_path / "loud"),
                                "--target", "-16", "--json", str(tmp_path / "loud.json")]) == 0
    rec = json.load(open(tmp_path / "loud.json"))
    assert rec and (tmp_path / "loud" / slate_rows[0]["target"]).exists()
    take = slate_rows[0]["target"]
    faded = tmp_path / "faded"; faded.mkdir()
    assert wav_fade.main([str(tmp_path / "loud" / take), "-o", str(faded / take),
                          "--in", "0.01", "--fade-out", "0.02"]) == 0
    padded = tmp_path / "padded"; padded.mkdir()
    assert wav_pad.main([str(faded / take), "-o", str(padded / take), "--to-duration", "1.0"]) == 0
    y, sr = audio_tidy.read_wav(str(padded / take))
    assert len(y) >= sr
    rev = tmp_path / "rev"; rev.mkdir()
    assert sfx_reverse.main([str(padded / take), "-o", str(rev / take)]) == 0
    n = len(audio_tidy.read_wav(str(rev / take))[0])
    assert wav_loop_snap.main([str(rev / take), "-o", str(tmp_path / "snapped.wav"),
                               "--start", "0", "--end", str(n - 1)]) == 0
    assert (tmp_path / "snapped.wav").stat().st_size > 0
    assert sfx_normalize.main([str(tmp_path / "snapped.wav"), "-o", str(tmp_path / "norm.wav"), "--peak", "-1"]) == 0
    assert (tmp_path / "norm.wav").stat().st_size > 0
    # stereo swap on a duplicated mono take
    x, sr = audio_tidy.read_wav(str(tmp_path / "norm.wav"))
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
        audio_tidy.write_wav(str(tmp_path / "st.wav"), x, sr, bits=16)
        assert wav_chan_swap.main([str(tmp_path / "st.wav"), "-o", str(tmp_path / "sw.wav"), "--swap"]) == 0


def test_pipeline_gltf_cleanup(tmp_path):
    obj = tmp_path / "prop.obj"
    obj.write_text(
        "o Prop\n"
        "v 10 4 0\nv 14 4 0\nv 14 8 0\nv 10 8 0\n"
        "v 10 4 4\nv 14 4 4\nv 14 8 4\nv 10 8 4\n"
        "vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n"
        "usemtl wood\ng body\n"
        "f 1/1 2/2 3/3 4/4\nf 5/1 8/4 7/3 6/2\nf 1/1 5/4 6/3 2/2\nf 4/1 3/2 7/3 8/4\nf 1/1 4/2 8/3 5/4\nf 2/1 6/2 7/3 3/4\n"
    )
    lid = tmp_path / "lid.obj"
    lid.write_text("o Lid\nv 10 8 0\nv 14 8 0\nv 14 8 4\nv 10 8 4\nvt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\nusemtl wood\ng lid\nf 1/1 2/2 3/3 4/4\n")
    assert obj_split.main([str(obj), "-o", str(tmp_path / "obj-parts"), "--by", "o"]) == 0
    assert list((tmp_path / "obj-parts").glob("*.obj"))
    assert obj_merge.main([str(obj), str(lid), "-o", str(tmp_path / "merged.obj")]) == 0
    assert obj_triangulate.main([str(tmp_path / "merged.obj"), "-o", str(tmp_path / "prop_tri.obj")]) == 0
    assert obj_normals.main([str(tmp_path / "prop_tri.obj"), "-o", str(tmp_path / "prop_n.obj"),
                             "--mode", "smooth"]) == 0
    assert obj_bounds.main([str(tmp_path / "prop_n.obj"), "-o", str(tmp_path / "bounds.json")]) == 0
    assert obj_to_glb.main([str(tmp_path / "prop_n.obj"), "-o", str(tmp_path / "glb")]) == 0
    src = tmp_path / "glb" / "prop_n.glb"
    assert src.exists()
    assert gltf_strip.main([str(src), "-o", str(tmp_path / "strip.glb"), "--drop-extras"]) == 0
    assert glb_rename_nodes.main([str(tmp_path / "strip.glb"), "-o", str(tmp_path / "named.glb"),
                                  "--prefix", "Prop_", "--json", str(tmp_path / "renames.json")]) == 0
    assert mesh_pivot_fix.main([str(tmp_path / "named.glb"), "-o", str(tmp_path / "pivot.glb"),
                                "--mode", "center"]) == 0
    assert glb_uv_transform.main([str(tmp_path / "pivot.glb"), "-o", str(tmp_path / "uv.glb"),
                                  "--flip-v"]) == 0
    # continue the pipeline from the UV-transformed file
    assert material_audit.main([str(tmp_path / "uv.glb"), "--json", str(tmp_path / "audit.json")]) == 0
    assert (tmp_path / "uv.glb").stat().st_size > 0
    audit = json.load(open(tmp_path / "audit.json"))
    assert audit
    assert glb_split.main([str(tmp_path / "uv.glb"), "-o", str(tmp_path / "parts"),
                           "--by", "mesh"]) == 0
    assert list((tmp_path / "parts").glob("*.glb"))


def test_pipeline_loc_pass(tmp_path):
    ok = tmp_path / "ok.csv"
    ok.write_text("id,en,fr,de\nhello,Hello {name},Bonjour {name},Hallo {name}\nbye,Bye,Au revoir,Tschüss\n")
    gap = tmp_path / "gap.csv"
    gap.write_text("id,en,fr,de\nhello,Hello {name},Bonjour {name},Hallo {name}\nbye,Bye,,Tschüss\n")
    assert loc_missing.main([str(ok)]) == 0
    assert loc_placeholder_lint.main([str(ok)]) == 0
    assert loc_check.main([str(ok), "--source", "en"]) == 0
    assert loc_plurals.main([str(ok)]) == 0
    assert loc_missing.main([str(gap)]) == 1
    plur = tmp_path / "plur.csv"
    plur.write_text(
        "id,en,de\n"
        "apples,\"{n, plural, one {# apple} other {# apples}}\","
        "\"{n, plural, one {# Apfel} other {# Aepfel}}\"\n"
        "hello,Hello,Hallo\n"
        "zeta,Z,Z\n"
        "alpha,A,A\n"
    )
    assert loc_icu_extract.main([str(plur), "-o", str(tmp_path / "icu.csv")]) == 0
    rows = list(__import__("csv").DictReader(open(tmp_path / "icu.csv")))
    assert any(r["style"] == "icu" and r["key"] == "apples" for r in rows)
    assert loc_sort.main([str(plur), "-o", str(tmp_path / "sorted.csv"), "--no-fail"]) == 0
    keys = [r["id"] for r in __import__("csv").DictReader(open(tmp_path / "sorted.csv"))]
    assert keys == sorted(keys)
    assert loc_key_lint.main([str(ok), "--separator", "", "--json", str(tmp_path / "keys.json")]) == 0
    assert loc_key_lint.main([str(tmp_path / "sorted.csv"), "--separator", "", "--no-fail"]) == 0
    extra = tmp_path / "extra.csv"
    extra.write_text("id,en,es\nhello,Hello {name},Hola {name}\n")
    assert loc_merge.main([str(ok), str(extra), "-o", str(tmp_path / "merged.csv"), "--no-fail"]) == 0
    assert "es" in (tmp_path / "merged.csv").read_text().splitlines()[0]


def test_pipeline_tileset_to_godot(tmp_path):
    base = tmp_path / "grass"
    assert tileset_gen.main(["-o", str(base), "--tile", "8", "--inner", "#4a8f3c", "--outer", "#8a6a3f"]) == 0
    assert (tmp_path / "grass.png").exists() and (tmp_path / "grass.json").exists()
    assert tileset_wang.main([str(tmp_path / "grass.json"), "-o", str(tmp_path / "grass.tsj"), "--pretty"]) == 0
    tsj = json.load(open(tmp_path / "grass.tsj"))
    assert tsj.get("wangsets") or tsj.get("wang") or "tilecount" in tsj
    # one-tile companion tileset, same tile size, merged before the Godot export
    from PIL import Image
    Image.new("RGBA", (int(tsj["tilewidth"]), int(tsj["tileheight"])), (80, 80, 80, 255)).save(tmp_path / "dirt.png")
    dirt = {"name": "dirt", "tilewidth": tsj["tilewidth"], "tileheight": tsj["tileheight"],
            "tilecount": 1, "columns": 1, "image": "dirt.png"}
    json.dump(dirt, open(tmp_path / "dirt.tsj", "w"))
    assert tileset_merge.main([str(tmp_path / "grass.tsj"), str(tmp_path / "dirt.tsj"),
                               "-o", str(tmp_path / "terrain.tsj")]) == 0
    terrain = json.load(open(tmp_path / "terrain.tsj"))
    assert terrain["tilecount"] == tsj["tilecount"] + 1
    assert tileset_split.main([str(tmp_path / "terrain.tsj"), "-o", str(tmp_path / "split" / "t"),
                               "--at", str(tsj["tilecount"])]) == 0
    assert (tmp_path / "split" / "t_a.tsj").exists() and (tmp_path / "split" / "t_b.tsj").exists()
    assert godot_tileset.main([str(tmp_path / "terrain.tsj"), "-o", str(tmp_path / "grass.tres"),
                               "--res", "res://art/terrain.png"]) == 0
    text = open(tmp_path / "grass.tres").read()
    assert "TileSet" in text and "res://art/terrain.png" in text
