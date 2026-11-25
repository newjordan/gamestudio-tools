import json, os
import numpy as np
from PIL import Image
import atlas_pack, sprite_slice, pixelize, normal_bake, terrain_noise


def _sprites(tmp, n=12):
    d = tmp / "sprites"; d.mkdir()
    rng = np.random.default_rng(1)
    for i in range(n):
        w, h = rng.integers(8, 60, 2)
        im = Image.new("RGBA", (int(w) + 6, int(h) + 6), (0, 0, 0, 0))
        im.paste((255, i * 20, 0, 255), (3, 3, 3 + int(w), 3 + int(h)))
        im.save(d / f"s{i:02d}.png")
    return d


def test_atlas_pack_no_overlap_and_pixels(tmp_path):
    d = _sprites(tmp_path)
    out = str(tmp_path / "atlas")
    atlas_pack.main([str(d), "-o", out])
    meta = json.load(open(out + ".json"))
    atlas = Image.open(out + ".png")
    fr = [v["frame"] for v in meta["frames"].values()]
    assert len(fr) == 12
    for i, a in enumerate(fr):
        assert a["x"] + a["w"] <= atlas.width and a["y"] + a["h"] <= atlas.height
        for b in fr[i + 1:]:
            assert a["x"] + a["w"] <= b["x"] or b["x"] + b["w"] <= a["x"] or a["y"] + a["h"] <= b["y"] or b["y"] + b["h"] <= a["y"]
    # trimmed: frame equals opaque content; centre pixel opaque
    f0 = meta["frames"]["s00"]
    assert f0["trimmed"] and f0["spriteSourceSize"]["x"] == 3
    px = atlas.getpixel((f0["frame"]["x"] + f0["frame"]["w"] // 2, f0["frame"]["y"] + f0["frame"]["h"] // 2))
    assert px[3] == 255


def test_sprite_slice_grid_and_auto(tmp_path):
    sheet = Image.new("RGBA", (128, 32), (0, 0, 0, 0))
    for i in range(3):  # 3 of 4 cells filled
        sheet.paste((i * 80, 255, 0, 255), (i * 32 + 4, 4, i * 32 + 28, 28))
    p = tmp_path / "sheet.png"; sheet.save(p)
    out = tmp_path / "g"
    sprite_slice.main([str(p), "--grid", "32x32", "-o", str(out), "--gif", str(tmp_path / "a.gif")])
    assert len(json.load(open(out / "frames.json"))) == 3
    assert Image.open(tmp_path / "a.gif").n_frames == 3
    out2 = tmp_path / "a"
    sprite_slice.main([str(p), "--auto", "-o", str(out2)])
    idx = json.load(open(out2 / "frames.json"))
    assert len(idx) == 3 and idx[0]["w"] == 24 and idx[0]["x"] < idx[1]["x"]


def test_pixelize_palette(tmp_path):
    grad = np.tile(np.linspace(0, 255, 256, dtype=np.uint8), (128, 1))
    im = Image.fromarray(np.stack([grad, grad[:, ::-1], grad // 2], -1), "RGB")
    p = tmp_path / "in.png"; im.save(p)
    o = tmp_path / "px.png"
    pixelize.main([str(p), "-o", str(o), "-w", "32", "-p", "pico8", "--preview-scale", "4"])
    out = Image.open(o).convert("RGBA")
    assert out.size == (32, 16)
    pal = {tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) for c in pixelize.PALETTES["pico8"]}
    assert {tuple(v) for v in np.array(out)[..., :3].reshape(-1, 3).tolist()} <= pal
    assert os.path.exists(tmp_path / "px_x4.png")
    q = pixelize.pixelize(im, 32, None, 4)
    assert len({tuple(v) for v in np.array(q)[..., :3].reshape(-1, 3).tolist()}) <= 4


def test_normal_bake_flat_and_slope(tmp_path):
    flat = np.full((32, 32), 0.5, np.float32)
    n = np.asarray(normal_bake.normal_map(flat))
    assert abs(int(n[..., 0].mean()) - 127) <= 1 and n[..., 2].min() >= 254
    ramp = np.tile(np.linspace(0, 1, 32, dtype=np.float32), (32, 1))  # rises to the right
    n = np.asarray(normal_bake.normal_map(ramp, tile=False)).astype(int)
    assert n[16, 16, 0] < 127  # normal tilts left (-X) on a slope rising to +X
    src = Image.fromarray((ramp * 255).astype(np.uint8)); p = tmp_path / "t.png"; src.save(p)
    normal_bake.main([str(p), "-o", str(tmp_path / "o")])
    for s in ("height", "normal", "ao", "roughness"):
        assert os.path.exists(tmp_path / "o" / f"t_{s}.png")


def test_terrain_noise_deterministic_tileable(tmp_path):
    a = terrain_noise.fbm(128, seed=7)
    b = terrain_noise.fbm(128, seed=7)
    c = terrain_noise.fbm(128, seed=8)
    assert np.array_equal(a, b) and not np.array_equal(a, c)
    assert a.min() == 0 and a.max() == 1
    # tileable: wrap-around seam is no worse than interior neighbour differences
    seam = np.abs(a[:, 0] - a[:, -1]).mean()
    interior = np.abs(np.diff(a, axis=1)).mean()
    assert seam < interior * 3
    out = str(tmp_path / "t")
    terrain_noise.main(["-o", out, "--size", "65", "--island", "--seed", "3"])
    raw = np.fromfile(out + ".r16", "<u2")
    assert raw.size == 65 * 65
    isl = np.asarray(Image.open(out + "_8.png"))
    assert isl[0, 0] == 0 and isl[32, 32] > isl[0, 0]
    assert Image.open(out + "_splat.png").mode == "RGBA"
