#!/usr/bin/env python3
"""anim-meta: turn frame names into animation clips. Frames named walk_01, walk_02, idle-1 ... (from atlas-pack /
atlas-convert JSON, or a folder of PNGs) are grouped by prefix and ordered by their number. Output:
  clips JSON   {"clips": {"walk": {"frames": [...], "fps": 12, "loop": true, "duration": 0.667}}}
  Phaser 3     {"anims": [{"key", "frames": [{"key": <atlas>, "frame": <name>}], "frameRate", "repeat"}]}  (-1 = loop)
Per-clip overrides: --fps walk=12,idle=4  --once attack,die (non looping). Gaps in numbering are reported.
"""
import argparse, os, json, re, sys

NUM = re.compile(r"^(.*?)[_\- ]*(\d+)$")


def names_from(path):
    if os.path.isdir(path): return sorted(os.path.splitext(f)[0] for f in os.listdir(path) if f.lower().endswith(".png"))
    fr = json.load(open(path))["frames"]
    return list(fr) if isinstance(fr, dict) else [f["filename"] for f in fr]


def group(names):
    clips, singles = {}, []
    for n in names:
        m = NUM.match(n)
        if not m or not m.group(1): singles.append(n); continue
        clips.setdefault(m.group(1), []).append((int(m.group(2)), n))
    return {k: sorted(v) for k, v in clips.items()}, singles


def build(names, default_fps=12.0, fps=None, once=(), min_frames=2):
    fps = fps or {}; groups, singles = group(names); clips, warn = {}, []
    for k, v in sorted(groups.items()):
        if len(v) < min_frames: singles.append(v[0][1]); continue
        nums = [n for n, _ in v]
        if len(set(nums)) != len(nums): warn.append(f"{k}: duplicate frame numbers")
        if nums != list(range(nums[0], nums[0] + len(nums))): warn.append(f"{k}: gaps in numbering {nums}")
        f = float(fps.get(k, default_fps))
        clips[k] = {"frames": [n for _, n in v], "fps": f, "loop": k not in once, "duration": round(len(v) / f, 4)}
    for k in list(fps) + list(once):
        if k not in clips: warn.append(f"override for unknown clip {k!r}")
    return clips, sorted(singles), warn


def phaser(clips, atlas_key):
    return {"anims": [{"key": k, "frames": [{"key": atlas_key, "frame": n} for n in c["frames"]], "frameRate": c["fps"], "repeat": -1 if c["loop"] else 0} for k, c in clips.items()]}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Group frames into animation clips.")
    ap.add_argument("source", help="atlas JSON or folder of PNGs"); ap.add_argument("--fps", default=""); ap.add_argument("--default-fps", type=float, default=12)
    ap.add_argument("--once", default=""); ap.add_argument("--atlas-key", default="atlas"); ap.add_argument("--clips"); ap.add_argument("--phaser")
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
    _src_keys = ('source',)
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

    fps = {k: float(v) for k, v in (x.split("=") for x in a.fps.split(",") if x)}
    clips, singles, warn = build(names_from(a.source), a.default_fps, fps, set(filter(None, a.once.split(","))))
    for k, c in clips.items(): print(f"{k}: {len(c['frames'])} frames @ {c['fps']:g} fps, {'loop' if c['loop'] else 'once'}, {c['duration']}s")
    if singles: print("not an animation (single frames):", ", ".join(singles))
    for w in warn: print("WARN", w)
    if a.clips: json.dump({"clips": clips, "single_frames": singles}, open(a.clips, "w"), indent=1)
    if a.phaser: json.dump(phaser(clips, a.atlas_key), open(a.phaser, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
