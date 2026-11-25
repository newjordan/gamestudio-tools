#!/usr/bin/env python3
"""ase-to-godot: write a Godot 4 SpriteFrames `.tres` from a binary Aseprite file.

Decodes the `.ase` / `.aseprite` with ase-decode (no Aseprite app), writes PNG
frames, and builds clips from tags (or a single `default` clip when there are
no tags). Reverse, ping-pong and ping-pong-reverse tags are expanded into the frame
list, and a tag repeat count turns looping off. The input is
never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ase-decode"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim-to-godot"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402
import ase_decode  # noqa: E402
import anim_to_godot  # noqa: E402


from ase_tags import MAX_CLIP_FRAMES, expand_tag  # noqa: E402  (shared with ase-json-import)


def clips_from_doc(nframes, durations, tags, directions=True):
    def names(idx):
        return ["frame_%04d.png" % i for i in idx]

    if tags:
        clips = {}
        for tag in tags:
            if not isinstance(tag, dict) or not tag.get("name"):
                continue
            frm, to = int(tag.get("from") or 0), int(tag.get("to") or 0)
            if frm < 0 or to >= nframes or to < frm:
                raise GstInputError("Aseprite tag %r has a frame range outside the file" % tag.get("name"))
            direction = (tag.get("direction") or "forward") if directions else "forward"
            repeat = int(tag.get("repeat") or 0) if directions else 0
            idx, loop = expand_tag(frm, to, direction, repeat)
            clips[str(tag["name"])] = {"frames": names(idx), "durations_ms": [durations[i] for i in idx],
                                       "loop": loop, "direction": direction}
        if clips:
            return clips
    idx = list(range(nframes))
    return {"default": {"frames": names(idx), "durations_ms": [durations[i] for i in idx], "loop": True,
                        "direction": "forward"}}


def default_res(frames_dir):
    """res:// path of frames_dir: relative to the nearest project.godot above it, else assume the
    frames folder sits at the project root (2.3.1 and older wrote bare res://frame_NNNN.png)."""
    d = os.path.abspath(frames_dir)
    probe = d
    while True:
        if os.path.isfile(os.path.join(probe, "project.godot")):
            rel = os.path.relpath(d, probe).replace(os.sep, "/")
            return "res://" if rel == "." else "res://" + rel
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    sys.stderr.write("ase-to-godot: no project.godot above %s; frame textures use res://%s/ (pass --res to set)\n"
                     % (frames_dir, os.path.basename(d)))
    return "res://" + os.path.basename(d)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 SpriteFrames .tres from a binary Aseprite file.")
    ap.add_argument("ase")
    ap.add_argument("-o", "--out", required=True, help="output SpriteFrames .tres")
    ap.add_argument("--frames-dir", help="folder to write PNG frames (default: <out stem>_frames)")
    ap.add_argument("--res", default=None,
                    help="res:// folder of the frame PNGs (default: derived from the nearest project.godot above "
                         "the frames folder, else res://<frames folder name>)")
    ap.add_argument("--fps", type=float, default=12.0, help="fallback fps when converting durations")
    ap.add_argument("--ignore-direction", action="store_true",
                    help="play every tag forward and looping, whatever its direction and repeat")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.ase, a.out, a.in_place)
    frames_dir = a.frames_dir or (os.path.splitext(a.out)[0] + "_frames")
    safe_out.check(a.ase, frames_dir, a.in_place)
    if a.json:
        safe_out.check(a.ase, a.json, a.in_place)
    data = open(a.ase, "rb").read()
    if len(data) < 128:
        raise GstInputError("Aseprite file is truncated")
    header, layers, frames, tags, palette = ase_decode.parse(data)
    images = ase_decode.composite(header, layers, frames, palette)
    if not images:
        raise GstInputError("Aseprite file has no composited frames")
    os.makedirs(frames_dir, exist_ok=True)
    durations = [int(fr["duration"]) for fr in frames]
    written = []
    for i, im in enumerate(images):
        name = "frame_%04d.png" % i
        dest = os.path.join(frames_dir, name)
        im.save(dest)
        written.append(name)
    res = a.res if a.res is not None else default_res(frames_dir)
    clips = clips_from_doc(len(images), durations, tags, not a.ignore_direction)
    index = anim_to_godot.index_folder(frames_dir)
    text, ntex, nanim = anim_to_godot.write_tres(clips, index, res, a.fps)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    open(a.out, "w", encoding="utf-8").write(text)
    rec = {"out": a.out, "frames_dir": frames_dir, "frames": len(written),
           "animations": nanim, "tags": [t.get("name") for t in tags], "textures": ntex,
           "clips": {k: {"direction": v.get("direction"), "loop": v["loop"], "frames": len(v["frames"])}
                     for k, v in clips.items()}}
    print("%d frame(s), %d animation(s) -> %s" % (len(written), nanim, a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
