#!/usr/bin/env python3
"""atlas-to-godot: write a Godot 4 SpriteFrames `.tres` from an atlas JSON (atlas-pack / TexturePacker hash or array)
plus its sheet. Frames become AtlasTexture sub-resources; optional anim-meta / ase-json-import clips JSON groups them
into named animations (otherwise every frame is one `default` animation, or `--per-frame` writes one animation per
frame). Texture path is written as res://... (override with --res). Rotated frames (TexturePacker/Aseprite: packed 90° CW)
are unpacked by rotating the atlas region back and writing a sibling PNG, then referenced as an ExtResource
(Godot AtlasTexture has no rotation). The sheet must be readable. The input is never overwritten unless
`--in-place`. The `.tres` was loaded in official Godot 4.7.2.stable.official.ed1daf0bf.
"""
import argparse, os, json, sys
from pathlib import Path as P


def load_atlas(path):
    data = json.load(open(path, encoding="utf-8"))
    frames = data.get("frames")
    if frames is None: sys.exit("atlas JSON has no frames")
    if isinstance(frames, list):
        items = [(f.get("filename") or f.get("name") or f.get("id") or str(i), f) for i, f in enumerate(frames)]
    else:
        items = list(frames.items())
    return data, items


def rect(rec):
    fr = rec.get("frame") or rec
    return int(fr["x"]), int(fr["y"]), int(fr["w"]), int(fr["h"])


def load_clips(path):
    if not path: return None
    data = json.load(open(path, encoding="utf-8"))
    clips = data.get("clips") or data
    if not isinstance(clips, dict): sys.exit("clips JSON must have a `clips` object")
    return clips



def is_rotated(rec):
    v = rec.get("rotated")
    return v in (True, 1, "true", "True")


def open_sheet(sheet):
    if not sheet or not os.path.isfile(sheet):
        return None
    from PIL import Image
    return Image.open(sheet).convert("RGBA")


def unpack_rotated(im, rec):
    """Undo a TexturePacker/Aseprite 90° CW pack: crop the atlas rect and rotate 90° CCW."""
    x, y, w, h = rect(rec)
    crop = im.crop((x, y, x + w, y + h))
    return crop.transpose(__import__("PIL").Image.Transpose.ROTATE_90)


def safe_stem(name):
    stem = os.path.splitext(os.path.basename(str(name)))[0] or "frame"
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in stem)


def tres(items, res, clips, per_frame, default_fps, rotated_files=None):
    # one AtlasTexture per unique frame name used
    by = {n: rec for n, rec in items}

    def resolve(n):
        if n in by: return n
        if (n + ".png") in by: return n + ".png"
        stem = os.path.splitext(n)[0]
        if stem in by: return stem
        return None

    used = []  # atlas keys
    missing = []
    if clips:
        for c in clips.values():
            for n in c.get("frames") or []:
                r = resolve(n)
                if r is None: missing.append(n)
                elif r not in used: used.append(r)
    else:
        used = [n for n, _ in items]
    if missing: sys.exit("clip frame(s) not in the atlas: " + ", ".join(missing[:8]))
    rotated_files = rotated_files or {}
    rot_used = [n for n in used if is_rotated(by[n])]
    missing_rot = [n for n in rot_used if n not in rotated_files]
    if missing_rot:
        sys.exit("rotated frames need the atlas sheet so they can be unpacked (" + ", ".join(missing_rot[:8]) + ")")
    # ext resources: the main sheet plus one per unpacked rotated frame
    ext = [(res, "1_tex")]
    rot_res = {}
    for i, n in enumerate(rot_used):
        eid = f"{i + 2}_tex"
        ext.append((rotated_files[n]["res"], eid))
        rot_res[n] = eid
    load_steps = 1 + len(ext) + (len(used) - len(rot_used))  # ext + one AtlasTexture per unrotated frame
    lines = [f'[gd_resource type="SpriteFrames" load_steps={load_steps} format=3]', ""]
    for path, eid in ext:
        lines.append(f'[ext_resource type="Texture2D" path="{path}" id="{eid}"]')
    lines.append("")
    id_of = {}
    tex_ref = {}
    ai = 0
    for n in used:
        if n in rot_res:
            tex_ref[n] = f'ExtResource("{rot_res[n]}")'
            continue
        sid = f"AtlasTexture_{ai}"
        ai += 1
        id_of[n] = sid
        x, y, w, h = rect(by[n])
        lines += [
            f'[sub_resource type="AtlasTexture" id="{sid}"]',
            'atlas = ExtResource("1_tex")',
            f"region = Rect2({x}, {y}, {w}, {h})",
            "",
        ]
        tex_ref[n] = f'SubResource("{sid}")'
    anims = []
    if clips:
        for name, clip in clips.items():
            names = clip.get("frames") or []
            durs = clip.get("durations_ms")
            fps = float(clip.get("fps") or default_fps)
            frames = []
            for i, fn in enumerate(names):
                if durs and i < len(durs) and fps:
                    duration = max(durs[i] / (1000 / fps), 0.01)
                else:
                    duration = 1.0
                frames.append({"duration": duration, "texture": tex_ref[resolve(fn)]})
            anims.append({"frames": frames, "loop": bool(clip.get("loop", True)),
                          "name": f'&"{name}"', "speed": fps})
    elif per_frame:
        for n in used:
            anims.append({"frames": [{"duration": 1.0, "texture": tex_ref[n]}],
                          "loop": True, "name": f'&"{os.path.splitext(n)[0]}"', "speed": default_fps})
    else:
        frames = [{"duration": 1.0, "texture": tex_ref[n]} for n in used]
        anims.append({"frames": frames, "loop": True, "name": '&"default"', "speed": default_fps})

    def fmt_anim(a):
        fr = ", ".join("{ \"duration\": %s, \"texture\": %s }" % (f["duration"], f["texture"]) for f in a["frames"])
        loop = "true" if a["loop"] else "false"
        return "{ \"frames\": [%s], \"loop\": %s, \"name\": %s, \"speed\": %s }" % (fr, loop, a["name"], a["speed"])

    lines += ["[resource]", "animations = ["]
    for i, a in enumerate(anims):
        comma = "," if i < len(anims) - 1 else ""
        lines.append("  " + fmt_anim(a) + comma)
    lines += ["]", ""]
    return "\n".join(lines), len(used), len(anims)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 SpriteFrames .tres from an atlas JSON plus a sheet.")
    ap.add_argument("atlas"); ap.add_argument("-o", "--out", required=True, help="output .tres")
    ap.add_argument("--sheet", help="sheet path used only to fill res:// (default: meta.image or atlas stem .png)")
    ap.add_argument("--clips", help="anim-meta / ase-json-import clips JSON")
    ap.add_argument("--per-frame", action="store_true", help="one animation per frame when no --clips")
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--res", help="texture path written in the resource (default res://<sheet basename>)")
    ap.add_argument("--rotated-dir", help="directory for unpacked rotated-frame PNGs (default: next to --out)")
    ap.add_argument("--rotated-res", help="res:// prefix for unpacked rotated PNGs (default res://<basename>)")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.atlas) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    data, items = load_atlas(a.atlas)
    sheet = a.sheet or (data.get("meta") or {}).get("image") or (os.path.splitext(a.atlas)[0] + ".png")
    if sheet and not os.path.isabs(sheet) and not os.path.isfile(sheet):
        cand = os.path.join(os.path.dirname(os.path.abspath(a.atlas)), sheet)
        if os.path.isfile(cand):
            sheet = cand
    res = a.res or ("res://" + os.path.basename(sheet))
    clips = load_clips(a.clips)
    rot_dir = a.rotated_dir or os.path.dirname(os.path.abspath(a.out)) or "."
    rotated_files = {}
    need = [(n, rec) for n, rec in items if is_rotated(rec)]
    if need:
        im = open_sheet(sheet)
        if im is None:
            sys.exit("rotated frames need a readable atlas sheet (pass --sheet or set meta.image)")
        os.makedirs(rot_dir, exist_ok=True)
        for n, rec in need:
            img = unpack_rotated(im, rec)
            dest = os.path.join(rot_dir, safe_stem(n) + "_unrot.png")
            img.save(dest)
            rel = os.path.basename(dest)
            rpath = a.rotated_res.rstrip("/") + "/" + rel if a.rotated_res else "res://" + rel
            rotated_files[n] = {"path": dest, "res": rpath, "size": img.size}
    text, ntex, nanim = tres(items, res, clips, a.per_frame, a.fps, rotated_files)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(text)
    extra = f", {len(rotated_files)} rotated unpacked" if rotated_files else ""
    print(f"{ntex} texture(s), {nanim} animation(s){extra} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
