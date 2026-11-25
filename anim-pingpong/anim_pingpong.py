#!/usr/bin/env python3
"""anim-pingpong: expand anim-meta / ase-json-import clip JSON to a ping-pong frame list
(and matching duration lists). Looping clips become `[f0..fn, fn-1..f1]` so a wrap back to
f0 stays smooth; non-looping clips include the return to f0: `[f0..fn, fn-1..f0]`. Loop flags
and fps are left as they were; total `duration` is recomputed from per-frame durations when
present. `--clips` limits the work to named clips. Writes a new JSON; the input is never
overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

DUR_KEYS = ("durations_ms", "durations", "times")


def load(path):
    data = json.load(open(path, encoding="utf-8"))
    if "clips" not in data or not isinstance(data["clips"], dict):
        sys.exit("expected anim-meta JSON with a `clips` object")
    return data


def expand_list(seq, loop):
    seq = list(seq)
    if len(seq) <= 1:
        return seq
    if loop:
        return seq + list(reversed(seq[1:-1]))  # f0..fn + fn-1..f1
    return seq + list(reversed(seq[:-1]))       # f0..fn + fn-1..f0


def pingpong_clip(clip):
    c = dict(clip)
    frames = list(c.get("frames") or [])
    loop = bool(c.get("loop", False))
    c["frames"] = expand_list(frames, loop)
    for key in DUR_KEYS:
        if key in c and isinstance(c[key], list):
            c[key] = expand_list(c[key], loop)
    durs = c.get("durations_ms")
    if durs:
        c["duration"] = round(sum(durs) / 1000, 4)
    elif "duration" in c and frames:
        # scale total duration by the new / old frame count
        old, new = len(frames) or 1, len(c["frames"]) or 1
        try:
            c["duration"] = round(float(c["duration"]) * new / old, 4)
        except (TypeError, ValueError):
            pass
    c["pingpong"] = True
    return c, {"loop": loop, "frames_in": len(frames), "frames_out": len(c["frames"])}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Expand anim-meta clips to a ping-pong frame list.")
    ap.add_argument("clips")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clips", dest="only", action="append", default=[],
                    help="clip name to expand (repeatable; default: all)")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.clips, a.out, a.in_place)
    if a.json:
        safe_out.check(a.clips, a.json, a.in_place)
    data = load(a.clips)
    only = set(a.only)
    missing = sorted(only - set(data["clips"]))
    if missing:
        sys.exit("unknown clip(s): " + ", ".join(missing))
    recs = []
    out_clips = {}
    for name, clip in data["clips"].items():
        if only and name not in only:
            out_clips[name] = clip
            recs.append({"clip": name, "pingpong": False, "frames": len(clip.get("frames") or [])})
            continue
        out_clips[name], info = pingpong_clip(clip)
        recs.append({"clip": name, "pingpong": True, **info})
    data = dict(data)
    data["clips"] = out_clips
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(data, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    n = sum(1 for r in recs if r["pingpong"])
    print(f"{n} clip(s) ping-ponged -> {a.out}")
    if a.json:
        json.dump({"expanded": n, "clips": recs, "out": a.out}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
