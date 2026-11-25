"""Optional integration test: load kit Godot emitters in a real Godot 4 editor.

Runs only when GODOT_BIN is set to a Godot 4 editor (or headless) binary. Official
verification used Godot 4.7.2.stable.official.ed1daf0bf (Linux x86_64) with
`--headless --import` then `-s res://verify.gd`. Skipped in default CI / tarball
runs where the binary is not on PATH.
"""
import json, os, shutil, subprocess, sys, textwrap

import numpy as np
import pytest
from PIL import Image

import atlas_pack, atlas_to_godot, audio_tidy, godot_import_presets, godot_tileset, tileset_gen

VERIFY_GD = textwrap.dedent("""\
	extends SceneTree

	func _init() -> void:
		var failed: PackedStringArray = PackedStringArray()
		_check_sprite_frames(failed)
		_check_tileset(failed)
		_check_rich_tileset(failed)
		_check_rotated_frames(failed)
		_check_texture(failed, "res://art/hero_atlas.png", "atlas texture")
		_check_texture(failed, "res://art/grass.png", "tileset texture")
		_check_texture(failed, "res://art/rich.png", "rich tileset texture")
		_check_texture(failed, "res://art/walk_01_unrot.png", "unpacked rotated frame")
		_check_wav(failed)
		if failed.size() > 0:
			for e in failed:
				push_error("GST_VERIFY_FAIL: " + e)
			print("GST_VERIFY_FAIL count=", failed.size())
			quit(1)
		else:
			print("GST_VERIFY_OK version=", Engine.get_version_info())
			quit(0)

	func _check_sprite_frames(failed: PackedStringArray) -> void:
		var sf = load("res://hero_frames.tres")
		if sf == null:
			failed.append("SpriteFrames load returned null")
			return
		if not (sf is SpriteFrames):
			failed.append("expected SpriteFrames, got %s" % sf)
			return
		var frames: SpriteFrames = sf
		var names: PackedStringArray = frames.get_animation_names()
		print("SpriteFrames animations=", names)
		if names.size() == 0:
			failed.append("SpriteFrames has no animations")
			return
		var i: int = 0
		while i < names.size():
			var n: StringName = names[i]
			var c: int = frames.get_frame_count(n)
			print("  anim ", n, " frames=", c, " loop=", frames.get_animation_loop(n), " speed=", frames.get_animation_speed(n))
			if c < 1:
				failed.append("animation %s has no frames" % n)
			else:
				var tex = frames.get_frame_texture(n, 0)
				if tex == null:
					failed.append("animation %s frame 0 texture is null" % n)
			i += 1

	func _check_tileset(failed: PackedStringArray) -> void:
		var ts = load("res://grass_tiles.tres")
		if ts == null:
			failed.append("TileSet load returned null")
			return
		if not (ts is TileSet):
			failed.append("expected TileSet, got %s" % ts)
			return
		var tileset: TileSet = ts
		print("TileSet tile_size=", tileset.tile_size, " sources=", tileset.get_source_count())
		if tileset.get_source_count() < 1:
			failed.append("TileSet has no sources")
			return
		var src = tileset.get_source(tileset.get_source_id(0))
		if src is TileSetAtlasSource:
			var atlas: TileSetAtlasSource = src
			print("  atlas tiles=", atlas.get_tiles_count(), " region=", atlas.texture_region_size, " tex=", atlas.texture)
			if atlas.get_tiles_count() < 1:
				failed.append("TileSetAtlasSource has no tiles")
			if atlas.texture == null:
				failed.append("TileSetAtlasSource texture is null")
		else:
			failed.append("source 0 is not a TileSetAtlasSource")

	func _check_rich_tileset(failed: PackedStringArray) -> void:
		var ts = load("res://rich_tiles.tres")
		if ts == null:
			failed.append("rich TileSet load returned null")
			return
		if not (ts is TileSet):
			failed.append("rich: expected TileSet, got %s" % ts)
			return
		var tileset: TileSet = ts
		print("rich TileSet tile_size=", tileset.tile_size, " sources=", tileset.get_source_count(),
			" physics_layers=", tileset.get_physics_layers_count(),
			" terrain_sets=", tileset.get_terrain_sets_count())
		if tileset.get_physics_layers_count() < 1:
			failed.append("rich TileSet has no physics layers")
		if tileset.get_terrain_sets_count() < 1:
			failed.append("rich TileSet has no terrain sets")
			return
		var mode: int = tileset.get_terrain_set_mode(0)
		var tname: String = tileset.get_terrain_name(0, 0)
		print("  terrain_set 0 mode=", mode, " terrain_0=", tname)
		if mode != 2:
			failed.append("rich terrain set mode want 2 (MATCH_SIDES), got %s" % mode)
		if tname != "dirt":
			failed.append("rich terrain 0 name want dirt, got %s" % tname)
		if tileset.get_source_count() < 1:
			failed.append("rich TileSet has no sources")
			return
		var src = tileset.get_source(tileset.get_source_id(0))
		if not (src is TileSetAtlasSource):
			failed.append("rich source 0 is not a TileSetAtlasSource")
			return
		var atlas: TileSetAtlasSource = src
		print("  rich atlas tiles=", atlas.get_tiles_count(), " region=", atlas.texture_region_size)
		if atlas.get_tiles_count() != 2:
			failed.append("rich atlas tiles want 2 (anim origin + standalone), got %s" % atlas.get_tiles_count())
		var origin := Vector2i(0, 0)
		if not atlas.has_tile(origin):
			failed.append("rich missing animation origin tile 0:0")
			return
		var cols: int = atlas.get_tile_animation_columns(origin)
		var nframes: int = atlas.get_tile_animation_frames_count(origin)
		var speed: float = atlas.get_tile_animation_speed(origin)
		var d0: float = atlas.get_tile_animation_frame_duration(origin, 0)
		var d1: float = atlas.get_tile_animation_frame_duration(origin, 1)
		print("  anim columns=", cols, " frames=", nframes, " speed=", speed, " dur=", d0, ",", d1)
		if cols != 2 or nframes != 2:
			failed.append("rich animation want 2 columns / 2 frames, got %s / %s" % [cols, nframes])
		if abs(speed - 10.0) > 0.01:
			failed.append("rich animation speed want 10, got %s" % speed)
		if abs(d0 - 1.0) > 0.01 or abs(d1 - 2.0) > 0.01:
			failed.append("rich animation durations want 1 and 2, got %s and %s" % [d0, d1])
		if atlas.has_tile(Vector2i(1, 0)):
			# animation frame cells must not also be standalone tiles
			failed.append("rich animation frame cell 1:0 should not be a standalone tile")
		if not atlas.has_tile(Vector2i(2, 0)):
			failed.append("rich missing standalone tile 2:0")
		var td: TileData = atlas.get_tile_data(origin, 0)
		var npoly: int = td.get_collision_polygons_count(0)
		print("  collision polygons=", npoly, " terrain_set=", td.terrain_set, " terrain=", td.terrain)
		if npoly < 1:
			failed.append("rich tile 0:0 has no collision polygons")
		else:
			var pts: PackedVector2Array = td.get_collision_polygon_points(0, 0)
			print("  polygon0=", pts)
			if pts.size() < 3:
				failed.append("rich collision polygon has fewer than 3 points")
			# bottom-half box in 8x8 tile centre space: y from 0 to 4, x from -4 to 4
			var xs: Array = []
			var ys: Array = []
			var i: int = 0
			while i < pts.size():
				xs.append(pts[i].x)
				ys.append(pts[i].y)
				i += 1
			xs.sort()
			ys.sort()
			if abs(xs[0] + 4) > 0.2 or abs(xs[xs.size() - 1] - 4) > 0.2:
				failed.append("rich collision x range want -4..4, got %s..%s" % [xs[0], xs[xs.size() - 1]])
			if abs(ys[0] - 0) > 0.2 or abs(ys[ys.size() - 1] - 4) > 0.2:
				failed.append("rich collision y range want 0..4, got %s..%s" % [ys[0], ys[ys.size() - 1]])
		if td.terrain_set != 0 or td.terrain != 0:
			failed.append("rich tile 0:0 terrain want set 0 terrain 0, got %s / %s" % [td.terrain_set, td.terrain])
		var right: int = td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_RIGHT_SIDE)
		var left: int = td.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_LEFT_SIDE)
		print("  peering right=", right, " left=", left)
		if right != 0 or left != 0:
			failed.append("rich peering want right=0 left=0, got %s / %s" % [right, left])

	func _check_rotated_frames(failed: PackedStringArray) -> void:
		var sf = load("res://rot_frames.tres")
		if sf == null:
			failed.append("rotated SpriteFrames load returned null")
			return
		if not (sf is SpriteFrames):
			failed.append("rotated: expected SpriteFrames, got %s" % sf)
			return
		var frames: SpriteFrames = sf
		var names: PackedStringArray = frames.get_animation_names()
		print("rotated SpriteFrames animations=", names)
		if names.size() < 1:
			failed.append("rotated SpriteFrames has no animations")
			return
		var n: StringName = names[0]
		if frames.get_frame_count(n) < 1:
			failed.append("rotated animation %s has no frames" % n)
			return
		var tex = frames.get_frame_texture(n, 0)
		if tex == null:
			failed.append("rotated frame 0 texture is null")
			return
		print("  rotated frame tex size=", tex.get_size(), " class=", tex.get_class())
		if tex.get_width() != 8 or tex.get_height() != 12:
			failed.append("rotated frame texture size want 8x12, got %sx%s" % [tex.get_width(), tex.get_height()])
		var png = load("res://art/walk_01_unrot.png")
		if png == null or not (png is Texture2D):
			failed.append("unpacked rotated PNG did not load as Texture2D")
			return
		var t: Texture2D = png
		if t.get_width() != 8 or t.get_height() != 12:
			failed.append("unpacked PNG size want 8x12, got %sx%s" % [t.get_width(), t.get_height()])

	func _check_texture(failed: PackedStringArray, path: String, label: String) -> void:
		var tex = load(path)
		if tex == null:
			failed.append("%s load returned null (%s)" % [label, path])
			return
		if not (tex is Texture2D):
			failed.append("%s is not Texture2D: %s" % [label, tex])
			return
		var t: Texture2D = tex
		print(label, " size=", t.get_size(), " class=", tex.get_class())
		if t.get_width() < 1 or t.get_height() < 1:
			failed.append("%s has empty size" % label)

	func _check_wav(failed: PackedStringArray) -> void:
		var s = load("res://sfx/hit.wav")
		if s == null:
			failed.append("WAV load returned null")
			return
		if not (s is AudioStreamWAV):
			failed.append("expected AudioStreamWAV, got %s" % s)
			return
		var w: AudioStreamWAV = s
		print("WAV mix_rate=", w.mix_rate, " format=", w.format, " data_bytes=", w.data.size(), " loop=", w.loop_mode)
		if w.data.size() < 1:
			failed.append("WAV has no sample data")
""")


def godot_bin():
    p = os.environ.get("GODOT_BIN") or ""
    return p if p and os.path.isfile(p) and os.access(p, os.X_OK) else ""


def _run(bin_, args, env, cwd=None, timeout=60):
    r = subprocess.run([bin_, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       env=env, cwd=cwd, timeout=timeout, text=True)
    return r.returncode, r.stdout


def _isolate(tmp_path):
    home = tmp_path / "home"
    (home / ".config").mkdir(parents=True)
    (home / ".local" / "share").mkdir(parents=True)
    (home / ".cache").mkdir(parents=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_DATA_HOME"] = str(home / ".local" / "share")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    return env


def _build_project(proj):
    art = proj / "art"
    frames = proj / "frames"
    sfx = proj / "sfx"
    art.mkdir(parents=True)
    frames.mkdir()
    sfx.mkdir()
    for i, c in enumerate([(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)]):
        Image.new("RGBA", (8, 8), c).save(frames / f"walk_{i + 1:02d}.png")
    assert tileset_gen.main(["-o", str(art / "grass"), "--tile", "8",
                             "--inner", "#4a8f3c", "--outer", "#8a6a3f"]) == 0
    sr = 8000
    t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
    x = (0.2 * np.sin(2 * np.pi * 440 * t)).reshape(-1, 1)
    audio_tidy.write_wav(str(sfx / "hit.wav"), x, sr, bits=16)
    (proj / "project.godot").write_text(
        "; Engine configuration file.\nconfig_version=5\n\n"
        "[application]\n\nconfig/name=\"gst-godot-verify\"\n"
        "config/features=PackedStringArray(\"4.7\")\n\n"
        "[rendering]\n\ntextures/canvas_textures/default_texture_filter=0\n"
    )
    assert atlas_pack.main([str(frames), "-o", str(art / "hero_atlas"),
                            "--padding", "1", "--no-pot"]) == 0
    json.dump({"clips": {"walk": {"frames": ["walk_01", "walk_02", "walk_03"],
                                  "fps": 10, "loop": True}}},
              open(art / "clips.json", "w"))
    assert atlas_to_godot.main([str(art / "hero_atlas.json"), "-o", str(proj / "hero_frames.tres"),
                                "--clips", str(art / "clips.json"),
                                "--res", "res://art/hero_atlas.png"]) == 0
    assert godot_tileset.main([str(art / "grass.json"), "-o", str(proj / "grass_tiles.tres"),
                               "--res", "res://art/grass.png"]) == 0
    # rich tileset: 3x1 8px, animation 0->1, bottom-half collider, edge wang on tile 0
    rich = Image.new("RGBA", (24, 8), (80, 140, 60, 255))
    for i, col in enumerate([(80, 140, 60, 255), (40, 90, 200, 255), (140, 90, 40, 255)]):
        for y in range(8):
            for x in range(8):
                rich.putpixel((i * 8 + x, y), col)
    rich.save(art / "rich.png")
    json.dump({
        "name": "rich", "tilewidth": 8, "tileheight": 8, "tilecount": 3, "columns": 3,
        "image": str(art / "rich.png"),
        "tiles": [
            {"id": 0,
             "animation": [{"tileid": 0, "duration": 100}, {"tileid": 1, "duration": 200}],
             "objectgroup": {"objects": [{"x": 0, "y": 4, "width": 8, "height": 4}]}},
        ],
        "wangsets": [{
            "name": "path", "type": "edge",
            "colors": [{"name": "dirt", "color": "#996633"}],
            "wangtiles": [{"tileid": 0, "wangid": [0, 0, 1, 0, 0, 0, 1, 0]}],
        }],
    }, open(art / "rich.tsj", "w"))
    assert godot_tileset.main([str(art / "rich.tsj"), "-o", str(proj / "rich_tiles.tres"),
                               "--res", "res://art/rich.png"]) == 0
    # rotated atlas frame: 8x12 upright packed 90° CW as 12x8
    upright = Image.new("RGBA", (8, 12), (0, 0, 0, 0))
    for y in range(12):
        upright.putpixel((0, y), (255, 0, 0, 255))
        upright.putpixel((7, y), (0, 0, 255, 255))
    packed = upright.transpose(Image.Transpose.ROTATE_270)
    rot_sheet = Image.new("RGBA", (12, 8), (0, 0, 0, 0))
    rot_sheet.paste(packed, (0, 0))
    rot_sheet.save(art / "rot_sheet.png")
    json.dump({"frames": {
        "walk_01.png": {"frame": {"x": 0, "y": 0, "w": 12, "h": 8}, "rotated": True},
    }, "meta": {"image": "rot_sheet.png", "size": {"w": 12, "h": 8}}},
              open(art / "rot_atlas.json", "w"))
    assert atlas_to_godot.main([str(art / "rot_atlas.json"), "-o", str(proj / "rot_frames.tres"),
                                "--sheet", str(art / "rot_sheet.png"),
                                "--res", "res://art/rot_sheet.png",
                                "--rotated-dir", str(art),
                                "--rotated-res", "res://art"]) == 0
    json.dump({"rules": [{"glob": "art/**/*.png", "preset": "pixel"},
                         {"glob": "sfx/**/*.wav", "preset": "wav-oneshot"}]},
              open(proj / "import_rules.json", "w"))
    assert godot_import_presets.main([str(proj), "-r", str(proj / "import_rules.json")]) == 0
    (proj / "verify.gd").write_text(VERIFY_GD.replace("\t", "\t"))


@pytest.mark.skipif(not godot_bin(), reason="GODOT_BIN is not set to an executable Godot binary")
def test_godot_loads_kit_emitters(tmp_path):
    bin_ = godot_bin()
    env = _isolate(tmp_path)
    code, ver_out = _run(bin_, ["--headless", "--version"], env, timeout=30)
    assert code == 0, ver_out
    version_line = ver_out.strip().splitlines()[-1].strip()
    print("GODOT_BIN version:", version_line)
    proj = tmp_path / "proj"
    _build_project(proj)
    assert (proj / "art" / "hero_atlas.png.import").exists()
    assert (proj / "art" / "grass.png.import").exists()
    assert (proj / "sfx" / "hit.wav.import").exists()
    code, imp = _run(bin_, ["--headless", "--path", str(proj), "--import", "--quit"],
                     env, timeout=90)
    assert code == 0, imp
    assert "error" not in imp.lower() or "SCRIPT ERROR" not in imp
    code, out = _run(bin_, ["--headless", "--path", str(proj), "-s", "res://verify.gd"],
                     env, timeout=60)
    print(out)
    assert code == 0, out
    assert "GST_VERIFY_OK" in out
    assert "SpriteFrames animations=" in out
    assert "atlas tiles=47" in out
    assert "WAV mix_rate=8000" in out
    assert "rich TileSet" in out
    assert "physics_layers=" in out
    assert "terrain_sets=" in out
    assert "anim columns=" in out
    assert "collision polygons=" in out
    assert "rotated SpriteFrames animations=" in out
    assert "rotated frame tex size=" in out
    # record the exact version string Godot printed
    assert "4." in version_line
