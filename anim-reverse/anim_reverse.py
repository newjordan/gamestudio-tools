#!/usr/bin/env python3
"""anim-reverse: reverse anim-meta / ase-json-import clip JSON (frame order and matching duration lists).
`--clips` limits the work to named clips; others are copied through. Loop flags and fps stay put; total `duration`
is recomputed from per-frame durations when present. Writes a new JSON; the input is never overwritten.
"""
import argparse, os, json, sys


def load(path):
    data = json.load(open(path, encoding="utf-8"))
    if "clips" not in data or not isinstance(data["clips"], dict):
        sys.exit("expected anim-meta JSON with a `clips` object")
    return data


def reverse_clip(clip):
    c = dict(clip)
    frames = list(c.get("frames") or [])
    c["frames"] = list(reversed(frames))
    for key in ("durations_ms", "durations", "times"):
        if key in c and isinstance(c[key], list):
            c[key] = list(reversed(c[key]))
    durs = c.get("durations_ms")
    if durs:
        c["duration"] = round(sum(durs) / 1000, 4)
    elif "duration" in c and frames:
        # keep total duration; only the order flipped
        pass
    return c


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reverse anim-meta clip JSON (frame order and timings).")
    ap.add_argument("clips")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clips", dest="only", action="append", default=[],
                    help="clip name to reverse (repeatable; default: all)")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.clips) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    data = load(a.clips)
    only = set(a.only)
    missing = sorted(only - set(data["clips"]))
    if missing: sys.exit("unknown clip(s): " + ", ".join(missing))
    recs = []
    out_clips = {}
    for name, clip in data["clips"].items():
        if only and name not in only:
            out_clips[name] = clip
            recs.append({"clip": name, "reversed": False, "frames": len(clip.get("frames") or [])})
            continue
        out_clips[name] = reverse_clip(clip)
        recs.append({"clip": name, "reversed": True, "frames": len(out_clips[name].get("frames") or [])})
    data = dict(data); data["clips"] = out_clips
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(data, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    n = sum(1 for r in recs if r["reversed"])
    print(f"{n} clip(s) reversed -> {a.out}")
    if a.json: json.dump({"reversed": n, "clips": recs, "out": a.out}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
