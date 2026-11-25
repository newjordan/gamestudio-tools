#!/usr/bin/env python3
"""anim-splice: extract a frame range from an anim-meta clip, or concatenate named clips,
into a new clip JSON. Matching duration lists are sliced or joined the same way. fps and
loop flags are taken from the first source clip unless overridden. Writes a new JSON; the
input is never overwritten unless `--in-place`.
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


def slice_list(seq, start, end):
    n = len(seq)
    if start < 0 or end < start or end > n:
        raise SystemExit(f"range {start}:{end} is outside 0..{n}")
    return list(seq[start:end])


def extract(clip, start, end):
    c = dict(clip)
    frames = list(c.get("frames") or [])
    c["frames"] = slice_list(frames, start, end)
    for key in DUR_KEYS:
        if key in c and isinstance(c[key], list):
            c[key] = slice_list(c[key], start, end)
    durs = c.get("durations_ms")
    if durs:
        c["duration"] = round(sum(durs) / 1000, 4)
    elif "duration" in c and frames:
        old = len(frames) or 1
        try:
            c["duration"] = round(float(c["duration"]) * len(c["frames"]) / old, 4)
        except (TypeError, ValueError):
            pass
    return c


def concat(clips, names, loop=None, fps=None):
    if not clips:
        raise SystemExit("no clips to concatenate")
    out = dict(clips[0])
    frames, durs = [], {k: [] for k in DUR_KEYS if any(k in c and isinstance(c.get(k), list) for c in clips)}
    for c in clips:
        frames.extend(list(c.get("frames") or []))
        for k in durs:
            if k in c and isinstance(c[k], list):
                durs[k].extend(c[k])
            else:
                durs[k].extend([None] * len(c.get("frames") or []))
    out["frames"] = frames
    for k, v in durs.items():
        if any(x is None for x in v):
            out.pop(k, None)
        else:
            out[k] = v
    if out.get("durations_ms"):
        out["duration"] = round(sum(out["durations_ms"]) / 1000, 4)
    if loop is not None:
        out["loop"] = loop
    if fps is not None:
        out["fps"] = fps
    out["spliced_from"] = names
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract or concatenate anim-meta clip frame ranges.")
    ap.add_argument("clips")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clip", help="source clip for --from/--to extract (default: the only clip, or required)")
    ap.add_argument("--from", dest="start", type=int, default=None, help="start index (inclusive)")
    ap.add_argument("--to", dest="end", type=int, default=None, help="end index (exclusive)")
    ap.add_argument("--concat", help="comma-separated clip names to concatenate, in order")
    ap.add_argument("--name", help="name of the new / replacement clip (default: the source clip, or 'spliced')")
    ap.add_argument("--only", action="store_true", help="write a file containing only the new clip")
    ap.add_argument("--loop", type=int, choices=(0, 1), help="override loop flag (0/1)")
    ap.add_argument("--fps", type=float, help="override fps")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.clips, a.out, a.in_place)
    if a.json:
        safe_out.check(a.clips, a.json, a.in_place)
    if a.concat and (a.start is not None or a.end is not None):
        sys.exit("use either --concat or --from/--to, not both")
    if not a.concat and a.start is None and a.end is None:
        sys.exit("pass --from/--to to extract, or --concat NAMES to join clips")
    data = load(a.clips)
    clips = data["clips"]
    if a.concat:
        names = [n.strip() for n in a.concat.split(",") if n.strip()]
        missing = [n for n in names if n not in clips]
        if missing:
            sys.exit("unknown clip(s): " + ", ".join(missing))
        new = concat([clips[n] for n in names], names,
                     loop=None if a.loop is None else bool(a.loop), fps=a.fps)
        dest_name = a.name or "spliced"
    else:
        if a.clip:
            if a.clip not in clips:
                sys.exit(f"unknown clip: {a.clip}")
            name = a.clip
        elif len(clips) == 1:
            name = next(iter(clips))
        else:
            sys.exit("pass --clip when the file has more than one clip")
        start = 0 if a.start is None else a.start
        end = len(clips[name].get("frames") or []) if a.end is None else a.end
        new = extract(clips[name], start, end)
        if a.loop is not None:
            new["loop"] = bool(a.loop)
        if a.fps is not None:
            new["fps"] = a.fps
        dest_name = a.name or name
    if a.only:
        out = dict(data)
        out["clips"] = {dest_name: new}
    else:
        out = dict(data)
        out["clips"] = dict(clips)
        out["clips"][dest_name] = new
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"clip": dest_name, "frames": len(new.get("frames") or []), "out": a.out}
    print(f"{dest_name}: {rec['frames']} frame(s) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
