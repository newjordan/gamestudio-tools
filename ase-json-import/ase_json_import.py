#!/usr/bin/env python3
"""ase-json-import: turn an Aseprite sprite-sheet export (File > Export Sprite Sheet, "JSON Data", array or hash
layout, with Tags enabled) into the atlas JSON this kit uses (atlas-pack / atlas-convert / atlas-validate) and an
animation clips JSON (same shape as anim-meta: frames, fps, loop, duration) built from the Aseprite tags.
Per-frame durations are kept (`durations_ms`); `fps` is the mean-duration fps. Tag directions forward, reverse,
pingpong and pingpong_reverse are expanded into the frame order that actually plays, with the same code ase-to-godot
uses (lib/ase_tags.py). A tag with an Aseprite `repeat` of N plays N cycles and does not loop; other tags loop unless
listed in `--once`. `--ignore-direction` plays every tag forward and forever. Frame names come from the
export's filename field; array exports without one get `<sheet>_<index>`. Rotated frames are kept (`rotated: true` in the atlas JSON) so atlas-to-godot
can unpack them. Slices, including nine-slice `center` insets and `pivot`, are
written as `<out>.slices.json` plus a Godot 4 scene (`<out>.slices.tscn`) with
those values as metadata; nine-slice slices also get a StyleBoxTexture `.tres`.
When the sheet image is available, each slice is cropped in canvas space
(rotated frames are un-packed first) so the Godot resources point at a usable
PNG. Original code; no Aseprite code is used.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "nine-slice-to-godot"))
import anim_meta  # noqa: E402
from ase_tags import expand_tag  # noqa: E402  (the same expansion ase-to-godot uses)
from gst_errors import GstInputError  # noqa: E402
import godot_text  # noqa: E402
import nine_slice_to_godot  # noqa: E402


def frame_list(data, sheet="sprite"):
    fr = data["frames"]
    if isinstance(fr, dict): items = list(fr.items())
    else: items = [(f.get("filename") or f"{sheet}_{i}", f) for i, f in enumerate(fr)]
    return items


def expand(frames, direction):
    """One cycle of `frames` in `direction` (kept for callers; uses the shared expansion)."""
    f = list(frames)
    if not f: return f
    idx, _ = expand_tag(0, len(f) - 1, direction, 0)
    return [f[i] for i in idx]



def _num_box(d, required=True):
    if d is None:
        if required:
            raise GstInputError("slice is missing bounds")
        return None
    if not isinstance(d, dict):
        raise GstInputError("slice box is not an object")
    return {"x": float(d.get("x") or 0), "y": float(d.get("y") or 0),
            "w": float(d.get("w") or 0), "h": float(d.get("h") or 0)}


def _insets(bounds, center):
    return {
        "left": center["x"],
        "top": center["y"],
        "right": max(bounds["w"] - (center["x"] + center["w"]), 0.0),
        "bottom": max(bounds["h"] - (center["y"] + center["h"]), 0.0),
    }


def parse_slices(raw):
    out = []
    for s in raw or []:
        if not isinstance(s, dict):
            raise GstInputError("slice entry is not an object")
        name = s.get("name") or "slice"
        keys = []
        for k in s.get("keys") or []:
            if not isinstance(k, dict):
                raise GstInputError("slice key is not an object")
            bounds = _num_box(k.get("bounds"), required=True)
            if bounds["w"] <= 0 or bounds["h"] <= 0:
                raise GstInputError("slice %r has an empty bounds" % name)
            rec = {"frame": int(k.get("frame") or 0), "bounds": bounds}
            if k.get("center"):
                center = _num_box(k.get("center"), required=True)
                rec["center"] = center
                rec["insets"] = _insets(bounds, center)
            if k.get("pivot") is not None:
                pv = k.get("pivot")
                if not isinstance(pv, dict):
                    raise GstInputError("slice %r pivot is not an object" % name)
                rec["pivot"] = {"x": float(pv.get("x") or 0), "y": float(pv.get("y") or 0)}
            keys.append(rec)
        item = {"name": str(name), "keys": keys}
        if s.get("color") is not None:
            item["color"] = s.get("color")
        out.append(item)
    return out


def sanitize(name, used):
    raw = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(name or "slice")) or "slice"
    n, i = raw, 0
    while n in used:
        i += 1
        n = "%s_%d" % (raw, i)
    used.add(n)
    return n


def is_rotated(rec):
    v = rec.get("rotated")
    return v in (True, 1, "true", "True")


def slice_image(sheet_im, frame_rec, bounds):
    """Crop a slice from the packed sheet in canvas (unrotated) space.

    Aseprite slice bounds are in the original sprite canvas. Rotated frames
    are packed 90° CW; they are rotated back before pasting into the canvas.
    """
    from PIL import Image
    fr = frame_rec["frame"]
    ss = frame_rec.get("spriteSourceSize") or {"x": 0, "y": 0, "w": fr["w"], "h": fr["h"]}
    src = frame_rec.get("sourceSize") or {"w": ss.get("w", fr["w"]), "h": ss.get("h", fr["h"])}
    cw, ch = int(src["w"]), int(src["h"])
    if cw <= 0 or ch <= 0:
        return None
    packed = sheet_im.crop((int(fr["x"]), int(fr["y"]), int(fr["x"]) + int(fr["w"]), int(fr["y"]) + int(fr["h"])))
    if is_rotated(frame_rec):
        packed = packed.transpose(Image.Transpose.ROTATE_90)
    canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canvas.paste(packed, (int(ss.get("x") or 0), int(ss.get("y") or 0)))
    bx, by, bw, bh = int(bounds["x"]), int(bounds["y"]), int(bounds["w"]), int(bounds["h"])
    # pad if the bounds sit partly outside the canvas
    left, top = min(max(bx, 0), cw), min(max(by, 0), ch)
    right, bottom = min(max(bx + bw, 0), cw), min(max(by + bh, 0), ch)
    if right <= left or bottom <= top:
        return None
    cropped = canvas.crop((left, top, right, bottom))
    if (left, top) != (bx, by) or cropped.size != (bw, bh):
        out = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
        out.paste(cropped, (left - bx, top - by))
        return out
    return cropped


def write_slices_godot(out_base, slices, frame_recs, image_name, res_prefix, sheet_im=None):
    """Write slices.json, slices.tscn, and StyleBoxTexture + PNG for nine-slices.

    Returns a report dict. Slice bounds stay in canvas space; when a sheet is
    given, a PNG is cropped for each key that has bounds so Godot resources
    do not depend on a packed/rotated atlas rect.
    """
    report = {"slices": [], "tres": [], "pngs": [], "scene": None, "json": None}
    if not slices:
        return report
    used = set()
    nodes = []
    ext = []  # (res, id)
    ext_ids = {}

    def tex_id(res):
        if res not in ext_ids:
            ext_ids[res] = "tex_%d" % (len(ext_ids) + 1)
            ext.append((res, ext_ids[res]))
        return ext_ids[res]

    def sb_id(res):
        if res not in ext_ids:
            ext_ids[res] = "sb_%d" % (len(ext_ids) + 1)
            ext.append((res, ext_ids[res]))
        return ext_ids[res]

    out_dir = os.path.dirname(os.path.abspath(out_base)) or "."
    stem = os.path.basename(out_base)
    for sl in slices:
        node = sanitize(sl["name"], used)
        keys_out = []
        # Godot scene uses the first key for the node
        first = sl["keys"][0] if sl["keys"] else None
        png_res = None
        tres_res = None
        for i, key in enumerate(sl["keys"]):
            rec = dict(key)
            fr_i = key["frame"]
            frame_rec = frame_recs[fr_i] if 0 <= fr_i < len(frame_recs) else None
            png_path = None
            if sheet_im is not None and frame_rec is not None:
                img = slice_image(sheet_im, frame_rec, key["bounds"])
                if img is not None:
                    suffix = "" if i == 0 else ("_f%d" % fr_i)
                    png_name = "%s_%s%s.png" % (stem, node, suffix)
                    png_path = os.path.join(out_dir, png_name)
                    img.save(png_path)
                    rec["png"] = png_path
                    report["pngs"].append(png_path)
                    if i == 0:
                        png_res = godot_text.res_path(res_prefix, png_name)
            if key.get("insets") is not None and (png_res or png_path):
                tres_name = "%s_%s%s.tres" % (stem, node, "" if i == 0 else ("_f%d" % fr_i))
                tres_path = os.path.join(out_dir, tres_name)
                this_res = godot_text.res_path(res_prefix, os.path.basename(png_path) if png_path else os.path.basename(image_name or "sheet.png"))
                ins = key["insets"]
                nine_slice_to_godot.write_tres(tres_path, this_res, ins["left"], ins["top"], ins["right"], ins["bottom"])
                rec["tres"] = tres_path
                report["tres"].append(tres_path)
                if i == 0:
                    tres_res = godot_text.res_path(res_prefix, tres_name)
            keys_out.append(rec)
        entry = {"name": sl["name"], "node": node, "keys": keys_out}
        if sl.get("color") is not None:
            entry["color"] = sl["color"]
        report["slices"].append(entry)

        block = ['[node name="%s" type="Node2D" parent="."]' % node]
        if first:
            b = first["bounds"]
            block.append("metadata/bounds = Rect2(%s, %s, %s, %s)" % (
                godot_text.num(b["x"]), godot_text.num(b["y"]), godot_text.num(b["w"]), godot_text.num(b["h"])))
            block.append("metadata/key_frame = %d" % first["frame"])
            if first.get("pivot"):
                pv = first["pivot"]
                block.append("metadata/pivot = Vector2(%s, %s)" % (godot_text.num(pv["x"]), godot_text.num(pv["y"])))
            if first.get("insets"):
                ins = first["insets"]
                block.append("metadata/insets = Vector4(%s, %s, %s, %s)" % (
                    godot_text.num(ins["left"]), godot_text.num(ins["top"]),
                    godot_text.num(ins["right"]), godot_text.num(ins["bottom"])))
                block.append("metadata/nine_slice = true")
                if first.get("center"):
                    c = first["center"]
                    block.append("metadata/center = Rect2(%s, %s, %s, %s)" % (
                        godot_text.num(c["x"]), godot_text.num(c["y"]), godot_text.num(c["w"]), godot_text.num(c["h"])))
        if tres_res:
            # StyleBox is an ExtResource; store its path as metadata too
            block.append('metadata/stylebox = "%s"' % tres_res)
        block.append("")
        if png_res:
            sid = tex_id(png_res)
            block.append('[node name="Sprite" type="Sprite2D" parent="%s"]' % node)
            block.append('texture = ExtResource("%s")' % sid)
            block.append("centered = false")
            if first and first.get("pivot"):
                pv = first["pivot"]
                block.append("offset = Vector2(%s, %s)" % (godot_text.num(-pv["x"]), godot_text.num(-pv["y"])))
            block.append("")
        nodes.append(block)

    sj = out_base + ".slices.json"
    json.dump({"slices": report["slices"], "image": image_name or ""}, open(sj, "w"), indent=1)
    report["json"] = sj

    load_steps = 1 + len(ext)
    lines = ['[gd_scene load_steps=%d format=3]' % load_steps, ""]
    for res, eid in ext:
        typ = "StyleBox" if eid.startswith("sb_") else "Texture2D"
        lines.append('[ext_resource type="%s" path="%s" id="%s"]' % (typ, res, eid))
    if ext:
        lines.append("")
    lines.append('[node name="Slices" type="Node2D"]')
    lines.append("")
    for b in nodes:
        lines.extend(b)
    scene = out_base + ".slices.tscn"
    open(scene, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    report["scene"] = scene
    return report


def convert(data, sheet="sprite", once=(), directions=True):
    try:
        return _convert(data, sheet, once, directions)
    except (KeyError, TypeError, ValueError, AttributeError, IndexError, OverflowError, ZeroDivisionError) as e:
        raise GstInputError("not a usable Aseprite sheet export: %s: %s" % (type(e).__name__, e)) from e


def _convert(data, sheet, once, directions):
    if not isinstance(data, dict) or "frames" not in data:
        raise GstInputError("not an Aseprite sheet export (no frames)")
    items = frame_list(data, sheet); names = [n for n, _ in items]
    if len(set(names)) != len(names): raise GstInputError("duplicate frame names in the Aseprite export; export with a unique {frame} in the filename")
    frames = {}
    for n, f in items:
        r = f["frame"]; ss = f.get("spriteSourceSize") or {"x": 0, "y": 0, "w": r["w"], "h": r["h"]}; src = f.get("sourceSize") or {"w": r["w"], "h": r["h"]}
        rec = {"frame": {"x": r["x"], "y": r["y"], "w": r["w"], "h": r["h"]}, "trimmed": bool(f.get("trimmed", False)),
               "spriteSourceSize": {"x": ss["x"], "y": ss["y"], "w": ss["w"], "h": ss["h"]}, "sourceSize": {"w": src["w"], "h": src["h"]}}
        if is_rotated(f):
            rec["rotated"] = True
        frames[n] = rec
    m = data.get("meta", {}); size = m.get("size", {})
    atlas = {"frames": frames, "meta": {"image": m.get("image", ""), "size": {"w": size.get("w", 0), "h": size.get("h", 0)}, "app": "gst ase-json-import", "format": "RGBA8888"}}
    dur = {n: int(f.get("duration", 100)) for n, f in items}
    tags = m.get("frameTags", [])
    clips = {}
    for t in tags:
        a, b = int(t["from"]), int(t["to"])
        if not (0 <= a <= b < len(names)): raise GstInputError(f"tag {t['name']!r} range {a}..{b} is outside the {len(names)} frames")
        direction = (t.get("direction") or "forward") if directions else "forward"
        repeat = int(t.get("repeat") or 0) if directions else 0
        idx, loops = expand_tag(a, b, direction, repeat)
        order = [names[i] for i in idx]; ms = [dur[n] for n in order]
        total = sum(ms)
        clips[t["name"]] = {"frames": order, "durations_ms": ms, "fps": round(1000 * len(order) / total, 3) if total else 0, "loop": loops and t["name"] not in once, "duration": round(total / 1000, 4), "direction": direction}
    if not tags:                                              # no tags: one clip with every frame
        ms = [dur[n] for n in names]; clips["all"] = {"frames": names, "durations_ms": ms, "fps": round(1000 * len(ms) / sum(ms), 3) if sum(ms) else 0, "loop": True, "duration": round(sum(ms) / 1000, 4)}
    return atlas, clips, parse_slices(m.get("slices") or [])


def _load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as e:
        raise GstInputError("cannot read Aseprite JSON %s: %s" % (path, e)) from e


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aseprite sheet JSON to atlas + clips JSON.")
    ap.add_argument("json"); ap.add_argument("-o", "--out", required=True, help="basename: writes <out>.json (atlas) and <out>.clips.json")
    ap.add_argument("--once", default="", help="comma list of tags that do not loop"); ap.add_argument("--phaser", help="also write Phaser 3 anims JSON"); ap.add_argument("--atlas-key", default="atlas")
    ap.add_argument("--ignore-direction", action="store_true", help="play every tag forward and forever (ignore direction and repeat)")
    ap.add_argument("--sheet", help="sprite-sheet image (default: meta.image next to the JSON) used to crop slice PNGs")
    ap.add_argument("--res", default="res://", help="res:// prefix for slice textures and StyleBoxTexture resources")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('json',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    for dest in (a.out + ".json", a.out + ".clips.json"):
        if os.path.abspath(dest) == os.path.abspath(a.json) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    data = _load(a.json)
    sheet_name = os.path.splitext(os.path.basename(a.json))[0]
    atlas, clips, slices = convert(data, sheet_name, set(filter(None, a.once.split(","))), not a.ignore_direction)
    json.dump(atlas, open(a.out + ".json", "w"), indent=1); json.dump({"clips": clips}, open(a.out + ".clips.json", "w"), indent=1)
    if a.phaser: json.dump(anim_meta.phaser(clips, a.atlas_key), open(a.phaser, "w"), indent=1)
    items = frame_list(data, sheet_name)
    frame_recs = []
    for n, _f in items:
        frame_recs.append(atlas["frames"][n])
    sheet_path = a.sheet
    if not sheet_path:
        image = atlas["meta"].get("image")
        if isinstance(image, str) and image:
            cand = image if os.path.isabs(image) else os.path.join(os.path.dirname(os.path.abspath(a.json)), image)
            if os.path.isfile(cand):
                sheet_path = cand
    sheet_im = None
    if sheet_path:
        try:
            from PIL import Image
            sheet_im = Image.open(sheet_path).convert("RGBA")
        except (OSError, ValueError, TypeError) as e:
            raise GstInputError("cannot read sprite sheet %s: %s" % (sheet_path, e)) from e
    image_name = atlas["meta"].get("image") if isinstance(atlas["meta"].get("image"), str) else ""
    try:
        sl_report = write_slices_godot(a.out, slices, frame_recs, image_name, a.res, sheet_im)
    except (OSError, ValueError, TypeError, KeyError, AttributeError, IndexError, OverflowError) as e:
        raise GstInputError("not a usable Aseprite slice list (%s: %s)" % (type(e).__name__, e)) from e
    msg = f"{len(atlas['frames'])} frame(s), {len(clips)} clip(s) -> {a.out}.json, {a.out}.clips.json"
    if slices:
        bits = [sl_report["json"], sl_report["scene"]]
        if sl_report["tres"]:
            bits.append("%d StyleBoxTexture(s)" % len(sl_report["tres"]))
        msg += "; %d slice(s) -> %s" % (len(slices), ", ".join(b for b in bits if b))
    print(msg)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
