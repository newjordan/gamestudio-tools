#!/usr/bin/env python3
"""anim-to-godot: write a Godot 4 SpriteFrames `.tres` from an anim-meta clips JSON plus a folder of frames.

Each clip becomes a SpriteFrames animation; each frame is an ExtResource to a
PNG in the folder (matched by name, with or without `.png`). Use
atlas-to-godot when the frames already live on a packed sheet. `--fps`
fills in clips that omit it. The input is never overwritten unless
`--in-place`.
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402

IMG_EXTS = {".png", ".webp", ".jpg", ".jpeg"}


def load_clips(path):
    doc = gst_read.require_object(gst_read.load_json(path, "anim-meta JSON"), "anim-meta JSON")
    clips = doc.get("clips") if isinstance(doc.get("clips"), dict) else doc
    if not isinstance(clips, dict) or not clips:
        raise GstInputError("anim-meta JSON has no clips")
    return clips


def index_folder(folder):
    if not os.path.isdir(folder):
        raise GstInputError("frames folder is not a directory: %s" % folder)
    by = {}
    for fn in os.listdir(folder):
        stem, ext = os.path.splitext(fn)
        if ext.lower() in IMG_EXTS:
            by[fn] = os.path.join(folder, fn)
            by[stem] = os.path.join(folder, fn)
    if not by:
        raise GstInputError("no images in %s" % folder)
    return by


def resolve(name, index):
    if name in index:
        return index[name]
    stem, ext = os.path.splitext(name)
    if stem in index:
        return index[stem]
    if (name + ".png") in index:
        return index[name + ".png"]
    return None


def write_tres(clips, index, res_prefix, default_fps):
    # unique files in first-seen order
    used, missing = [], []
    for clip in clips.values():
        if not isinstance(clip, dict):
            raise GstInputError("anim-meta clip is not an object")
        for n in clip.get("frames") or []:
            if resolve(n, index) is None:
                missing.append(n)
            else:
                path = resolve(n, index)
                if path not in used:
                    used.append(path)
    if missing:
        raise GstInputError("clip frame(s) not in the frames folder: %s" % ", ".join(missing[:8]))
    if not used:
        raise GstInputError("clips list no frames")
    ext = []
    id_of = {}
    for i, path in enumerate(used, 1):
        eid = "%d_tex" % i
        res = res_prefix.rstrip("/") + "/" + os.path.basename(path)
        if not res.startswith("res://"):
            res = "res://" + os.path.basename(path)
        ext.append((res, eid))
        id_of[path] = eid
    load_steps = 1 + len(ext)
    lines = ['[gd_resource type="SpriteFrames" load_steps=%d format=3]' % load_steps, ""]
    for res, eid in ext:
        lines.append('[ext_resource type="Texture2D" path="%s" id="%s"]' % (res, eid))
    lines.append("")
    anims = []
    for name, clip in clips.items():
        if not isinstance(clip, dict):
            continue
        names = clip.get("frames") or []
        durs = clip.get("durations_ms")
        fps = float(clip.get("fps") or default_fps)
        frames = []
        for i, fn in enumerate(names):
            path = resolve(fn, index)
            tex = 'ExtResource("%s")' % id_of[path]
            if durs and i < len(durs) and fps:
                duration = max(float(durs[i]) / (1000.0 / fps), 0.01)
            else:
                duration = 1.0
            frames.append((duration, tex))
        anims.append((name, frames, bool(clip.get("loop", True)), fps))
    def fmt(a):
        name, frames, loop, fps = a
        fr = ", ".join('{ "duration": %s, "texture": %s }' % (d, t) for d, t in frames)
        return '{ "frames": [%s], "loop": %s, "name": &"%s", "speed": %s }' % (
            fr, "true" if loop else "false", name, fps)
    lines += ["[resource]", "animations = ["]
    for i, a in enumerate(anims):
        comma = "," if i < len(anims) - 1 else ""
        lines.append("  " + fmt(a) + comma)
    lines += ["]", ""]
    return "\n".join(lines), len(used), len(anims)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 SpriteFrames .tres from anim-meta clips plus a frame folder.")
    ap.add_argument("clips", help="anim-meta / ase-json-import clips JSON")
    ap.add_argument("--frames", required=True, help="folder of frame PNGs")
    ap.add_argument("-o", "--out", required=True, help="output .tres")
    ap.add_argument("--fps", type=float, default=12.0, help="fallback fps when a clip omits it")
    ap.add_argument("--res", default="res://", help="res:// prefix for frame textures")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.clips, a.out, a.in_place)
    safe_out.check(a.frames, a.out, a.in_place)
    if a.json:
        safe_out.check(a.clips, a.json, a.in_place)
    clips = load_clips(a.clips)
    index = index_folder(a.frames)
    text, ntex, nanim = write_tres(clips, index, a.res, a.fps)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(text)
    rec = {"out": a.out, "textures": ntex, "animations": nanim}
    print("%d texture(s), %d animation(s) -> %s" % (ntex, nanim, a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
