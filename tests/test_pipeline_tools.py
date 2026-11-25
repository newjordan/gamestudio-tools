import base64, csv, io, json, struct, wave
import numpy as np
from PIL import Image
import asset_lint, gltf_inspect, dialogue_extract


def test_asset_lint(tmp_path):
    root = tmp_path / "assets"; (root / "ui").mkdir(parents=True)
    Image.new("RGBA", (256, 256)).save(root / "good_tex.png")
    Image.new("RGB", (300, 200)).save(root / "BadName.png")
    Image.new("RGB", (64, 64)).save(root / "ui" / "button.png")      # missing alpha
    Image.new("RGB", (4096, 4096)).save(root / "huge.png")
    with wave.open(str(root / "sfx_22k.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(22050); wf.writeframes(b"\0\0" * 100)
    (root / "art.psd").write_bytes(b"8BPS")
    res = asset_lint.lint(str(root), asset_lint.DEFAULT_RULES["rules"])
    by = {}
    for r in res:
        by.setdefault(r["file"], []).append(r["msg"])
    assert "good_tex.png" not in by
    assert any("name" in m for m in by["BadName.png"]) and any("power-of-two" in m for m in by["BadName.png"])
    assert any("alpha" in m for m in by["ui/button.png"])
    assert any("exceeds" in m for m in by["huge.png"])
    assert any("sample rate" in m for m in by["sfx_22k.wav"])
    assert "art.psd" in by
    assert asset_lint.main([str(root)]) == 1
    rules = tmp_path / "r.json"
    asset_lint.main([str(root), "--write-default-rules", str(rules)])
    assert json.load(open(rules))["rules"]


def _make_glb(path, with_normals=False):
    # one triangle, indexed, plus an embedded 8x4 PNG
    pos = np.array([[0, 0, 0], [1, 0, 0], [0, 2, 0]], np.float32).tobytes()
    idx = np.array([0, 1, 2], np.uint16).tobytes() + b"\0\0"
    buf = io.BytesIO(); Image.new("RGB", (8, 4)).save(buf, "PNG"); png = buf.getvalue()
    png += b"\0" * (-len(png) % 4)
    bin_ = pos + idx + png
    gltf = {"asset": {"version": "2.0", "generator": "test"}, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}],
            "meshes": [{"name": "tri", "primitives": [{"attributes": {"POSITION": 0}, "indices": 1, "material": 0}]}],
            "materials": [{"name": "m"}], "images": [{"bufferView": 2, "mimeType": "image/png"}],
            "buffers": [{"byteLength": len(bin_)}],
            "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 36},
                            {"buffer": 0, "byteOffset": 36, "byteLength": 6},
                            {"buffer": 0, "byteOffset": 44, "byteLength": len(png)}],
            "accessors": [{"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [0, 0, 0], "max": [1, 2, 0]},
                          {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"}]}
    js = json.dumps(gltf).encode(); js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(bin_)
    with open(path, "wb") as f:
        f.write(struct.pack("<4sII", b"glTF", 2, total))
        f.write(struct.pack("<I4s", len(js), b"JSON")); f.write(js)
        f.write(struct.pack("<I4s", len(bin_), b"BIN\x00")); f.write(bin_)


def test_gltf_inspect(tmp_path):
    p = tmp_path / "tri.glb"; _make_glb(p)
    r = gltf_inspect.inspect(str(p), max_tris=0, max_tex=4)
    assert r["totals"] == {"vertices": 3, "triangles": 1}
    assert r["textures"][0]["size"] == (8, 4)
    assert r["bounds"]["size"] == [1, 2, 0]
    w = " ".join(r["warnings"])
    assert "NORMAL" in w and "TEXCOORD_0" in w and "exceeds 4" in w and "budget" in w
    assert gltf_inspect.main([str(p), "--fail-on-warn"]) == 1


YARN = """title: Start
tags: intro
---
Ava: Hey, you made it! #line:a1b2c3
Ava: Got the {$item}? #mood:happy
-> Yes
    Ben: Here it is.
-> Not yet
<<jump End>>
// comment
===
"""

INK = """VAR gold = 0
== tavern ==
Barkeep: What'll it be? #vo
* [Ale] Ale, please. -> drink
* Water.
- Barkeep: Coming right up.
= drink
You drink <> deeply.
-> END
"""


def test_dialogue_extract(tmp_path):
    y = tmp_path / "a.yarn"; y.write_text(YARN)
    k = tmp_path / "b.ink"; k.write_text(INK)
    out = tmp_path / "lines.csv"
    dialogue_extract.main([str(y), str(k), "-o", str(out)])
    rows = list(csv.DictReader(open(out)))
    texts = [r["text"] for r in rows]
    assert "Hey, you made it!" in texts and "Got the ?" in texts and "Here it is." in texts
    assert rows[0]["id"] == "a1b2c3" and rows[0]["speaker"] == "Ava"
    assert any(r["tags"] == "mood:happy" for r in rows)
    assert any(r["kind"] == "choice" and r["text"] == "Yes" for r in rows)
    ink = [r for r in rows if r["file"] == "b.ink"]
    assert ink[0]["speaker"] == "Barkeep" and ink[0]["node"] == "tavern"
    assert any(r["text"] == "Ale, please." for r in ink)
    assert any(r["text"] == "You drink deeply." and r["node"] == "tavern.drink" for r in ink)
    assert not any("VAR" in t or "END" in t for t in texts)
    # ids stable across runs, and tag-in-place writes them back
    dialogue_extract.main([str(y), "-o", str(tmp_path / "l2.csv"), "--tag-in-place"])
    assert y.read_text().count("#line:") == len([r for r in rows if r["file"] == "a.yarn"])
    rows2 = list(csv.DictReader(open(tmp_path / "l2.csv")))
    assert [r["id"] for r in rows2] == [r["id"] for r in rows if r["file"] == "a.yarn"]
