#!/usr/bin/env python3
"""anim-from-folder: build an anim-meta clips JSON from a folder of frames and a name pattern.
`--pattern` uses `{clip}` and `{frame}` placeholders (e.g. `{clip}_{frame}.png`). Repeatable
`--clip NAME=GLOB` gathers one named clip from a glob (frames sorted by the number in the
filename). Output matches anim-meta: `{"clips": {"walk": {"frames": [...], "fps": 12, "loop": true,
"duration": ...}}}`. Frame names are stems (no extension) so they drop into atlas-to-godot /
anim-hold / anim-rename. Writes a new JSON; the input folder is never overwritten unless
`--in-place` (only relevant if `-o` points at a file inside the folder with the same path).
"""
import fnmatch
import argparse, os, json, re, sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402

NUM = re.compile(r"(\d+)")


def pattern_re(pat):
    out, i = [], 0
    while i < len(pat):
        if pat.startswith("{clip}", i):
            out.append("(?P<clip>.+?)")
            i += 6
        elif pat.startswith("{frame}", i):
            out.append(r"(?P<frame>\d+)")
            i += 7
        else:
            out.append(re.escape(pat[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def stem(name):
    return os.path.splitext(name)[0]


def list_pngs(folder):
    return sorted(p.name for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in (".png", ".webp", ".tga", ".bmp"))


def from_pattern(names, pat):
    rx = pattern_re(pat)
    groups, warn, unused = {}, [], []
    for n in names:
        m = rx.match(n)
        if not m:
            unused.append(n)
            continue
        clip, frame = m.group("clip"), int(m.group("frame"))
        groups.setdefault(clip, []).append((frame, stem(n)))
    clips = {}
    for k, v in groups.items():
        v = sorted(v)
        nums = [num for num, _ in v]
        if len(set(nums)) != len(nums):
            warn.append(f"{k}: duplicate frame numbers")
        if nums != list(range(nums[0], nums[0] + len(nums))):
            warn.append(f"{k}: gaps in numbering {nums}")
        clips[k] = [name for _, name in v]
    return clips, unused, warn


def from_globs(folder, specs):
    clips, warn = {}, []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit(f"--clip must be NAME=GLOB, got {spec!r}")
        name, glob = spec.split("=", 1)
        paths = sorted(Path(folder).glob(glob))
        frames = []
        for p in paths:
            if not p.is_file():
                continue
            nums = [int(x) for x in NUM.findall(p.stem)]
            frames.append((nums[-1] if nums else 0, stem(p.name)))
        if not frames:
            warn.append(f"{name}: no files matched {glob!r}")
        clips[name] = [n for _, n in sorted(frames)]
    return clips, warn


def _lookup(table, clip, default):
    """Exact clip name first, then the first fnmatch glob key (walk-*, *_idle) that matches."""
    if clip in table:
        return table[clip]
    for k, v in table.items():
        if any(ch in k for ch in "*?[") and fnmatch.fnmatchcase(clip, k):
            return v
    return default


def pack(clips, default_fps, fps, once):
    out, warn = {}, []
    once_t = {k: True for k in once}
    for k, frames in clips.items():
        f = float(_lookup(fps, k, default_fps))
        out[k] = {"frames": frames, "fps": f, "loop": not _lookup(once_t, k, False),
                  "duration": round((len(frames) / f) if f else 0.0, 4)}
    for k in list(fps) + list(once):
        if not any(k == c or fnmatch.fnmatchcase(c, k) for c in out):
            warn.append(f"override for unknown clip {k!r}")
    return out, warn


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build an anim-meta clips JSON from a folder and a name pattern.")
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pattern", help="filename pattern with {clip} and {frame}, e.g. {clip}_{frame}.png")
    ap.add_argument("--clip", action="append", default=[], metavar="NAME=GLOB",
                    help="repeatable: gather one clip from a glob (sorted by the number in the name)")
    ap.add_argument("--fps", action="append", default=[],
                    help="per-clip fps, walk=12,idle=4; keys may be globs (walk-*=10); repeatable")
    ap.add_argument("--default-fps", type=float, default=12)
    ap.add_argument("--once", action="append", default=[],
                    help="comma-separated clips (or globs) that should not loop; repeatable")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if not a.pattern and not a.clip:
        sys.exit("pass --pattern and/or --clip NAME=GLOB")
    if not os.path.isdir(a.folder):
        sys.exit(f"not a folder: {a.folder}")
    safe_out.check(a.folder, a.out, a.in_place)
    if a.json:
        safe_out.check(a.folder, a.json, a.in_place)
        safe_out.check(a.out, a.json, a.in_place)
    fps = {}
    for x in ",".join(a.fps).split(","):
        if x.strip():
            if "=" not in x:
                sys.exit(f"--fps entries are CLIP=FPS, got {x!r}")
            k, v = x.rsplit("=", 1)
            fps[k.strip()] = float(v)
    once = set(filter(None, (x.strip() for x in ",".join(a.once).split(","))))
    warn, unused = [], []
    clips = {}
    if a.pattern:
        names = list_pngs(a.folder)
        clips, unused, w = from_pattern(names, a.pattern)
        warn.extend(w)
    if a.clip:
        more, w = from_globs(a.folder, a.clip)
        warn.extend(w)
        for k, frames in more.items():
            if k in clips:
                warn.append(f"{k}: defined by both --pattern and --clip; --clip wins")
            clips[k] = frames
    packed, w = pack(clips, a.default_fps, fps, once)
    warn.extend(w)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    payload = {"clips": packed, "unused": [stem(n) if "." in n else n for n in unused]}
    json.dump(payload, open(a.out, "w"), indent=1)
    for k, c in packed.items():
        print(f"{k}: {len(c['frames'])} frames @ {c['fps']:g} fps, {'loop' if c['loop'] else 'once'}, {c['duration']}s")
    if unused:
        print("unused:", ", ".join(unused))
    for msg in warn:
        print("WARN", msg)
    rec = {"clips": {k: len(c["frames"]) for k, c in packed.items()}, "unused": unused, "warn": warn, "out": a.out}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
