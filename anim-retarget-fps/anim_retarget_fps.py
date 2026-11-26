#!/usr/bin/env python3
"""anim-retarget-fps: rewrite animation clip frame durations to a new fps grid while keeping each clip's total time.
Reads a list of clips, or {"clips"|"animations"|"anims": [...]} , or the anim-meta
dict {"clips": {"walk": {"frames", "fps", ...}}}. Dict clips are written back as a dict.
Each frame duration is snapped to a whole number of ticks of 1000/fps milliseconds (at least one tick). Any remainder
is added to the last frame so the clip total matches the original as closely as one tick allows. The clip's fps field
is updated. Writes a new JSON; refuses to overwrite the input.
"""
import argparse, os, json, math, sys


def clips_of(data):
    """Return (clip dicts, kind). kind is 'list' when the container is a list (mutated in
    place) or ('dict', key) when anim-meta stored clips as a name -> clip object map."""
    if isinstance(data, list):
        return data, "list"
    if isinstance(data, dict):
        for k in ("clips", "animations", "anims"):
            v = data.get(k)
            if isinstance(v, list):
                return v, "list"
            if isinstance(v, dict) and v and all(isinstance(c, dict) for c in v.values()):
                clips = []
                for name, clip in v.items():
                    c = dict(clip)
                    c.setdefault("name", name)
                    clips.append(c)
                return clips, ("dict", k)
    raise SystemExit("no clips/animations array found")


def durations_of(clip):
    if "frames" in clip and clip["frames"] and isinstance(clip["frames"][0], dict) and "duration" in clip["frames"][0]:
        return [int(f["duration"]) for f in clip["frames"]], "frames.duration"
    if "durations" in clip: return [int(d) for d in clip["durations"]], "durations"
    if "frameDurations" in clip: return [int(d) for d in clip["frameDurations"]], "frameDurations"
    n = clip.get("frame") and 0
    # list of frame names plus a uniform fps
    fps = clip.get("fps") or 10
    n = len(clip.get("frames") or clip.get("frameNames") or [])
    if n: return [int(round(1000 / fps))] * n, "uniform"
    raise SystemExit(f"clip {clip.get('name')!r} has no frame durations")


def apply_durs(clip, durs, kind):
    if kind == "frames.duration":
        for f, d in zip(clip["frames"], durs): f["duration"] = d
    elif kind == "durations": clip["durations"] = durs
    elif kind == "frameDurations": clip["frameDurations"] = durs
    # uniform: promote to per-frame durations and keep frames
    else: clip["durations"] = durs


def retarget(durs, fps):
    tick = 1000.0 / fps
    total = sum(durs)
    if not durs: return [], 0, tick
    # nearest whole ticks, at least 1, then fix remainder on the last frame
    ticks = [max(1, int(round(d / tick))) for d in durs]
    target_ticks = max(len(durs), int(round(total / tick)))
    diff = target_ticks - sum(ticks)
    ticks[-1] = max(1, ticks[-1] + diff)
    out = [int(round(t * tick)) for t in ticks]
    return out, sum(out), tick


def main(argv=None):
    ap = argparse.ArgumentParser(description="Retarget clip durations to a new fps, keeping total time.")
    ap.add_argument("input"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--fps", type=float, required=True); ap.add_argument("--json-report")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.fps <= 0: sys.exit("--fps must be positive")
    if os.path.abspath(a.out) == os.path.abspath(a.input) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    data = json.load(open(a.input)); clips, shape = clips_of(data)
    report = []
    for c in clips:
        durs, kind = durations_of(c)
        new, total, tick = retarget(durs, a.fps)
        apply_durs(c, new, kind); c["fps"] = a.fps
        rec = {"name": c.get("name") or c.get("key"), "frames": len(durs), "old_ms": sum(durs), "new_ms": total, "tick_ms": tick}
        report.append(rec)
        print(f"{rec['name']}: {rec['frames']} frame(s), {rec['old_ms']} ms -> {rec['new_ms']} ms at {a.fps:g} fps")
    if isinstance(shape, tuple):
        data[shape[1]] = {(c.get("name") or c.get("key") or "clip"): c for c in clips}
    json.dump(data, open(a.out, "w"), indent=1)
    if a.json_report: json.dump(report, open(a.json_report, "w"), indent=1)
    print(f"{len(clips)} clip(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
