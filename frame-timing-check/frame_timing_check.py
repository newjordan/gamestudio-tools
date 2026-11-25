#!/usr/bin/env python3
"""frame-timing-check: validate animation clip timings against a target fps grid before they ship. Reads:
  - anim-meta / ase-json-import clips JSON ({"clips": {"walk": {"frames", "fps", "duration", "durations_ms"?}}})
  - Aseprite sheet JSON (meta.frameTags plus per-frame duration)
  - Phaser 3 anims JSON ({"anims": [{"key", "frameRate", "frames", "repeat"}]})
  - a frames.json from gif-to-frames or a sheet JSON with a "frames" array of {duration_ms} (treated as one clip)
Flags: a frame duration that is not a multiple of 1000/fps (within --tolerance-ms), mixed durations in a clip that
claims a constant fps, clips whose stored fps does not match the durations, frames shorter than --min-ms or longer than
--max-ms, empty or single-frame looping clips, and (optional) total duration outside --min-clip / --max-clip seconds.
--allow-variable silences the mixed-duration warning (Aseprite tags often have hold frames). Text and JSON; exit 1 on
errors (warnings too with --strict).
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ase-json-import"))
import ase_json_import  # noqa: E402


def load_clips(data, path=""):
    """Return {name: {"frames": [names], "durations_ms": [int], "fps": float|None, "loop": bool|None, "duration": float|None}}."""
    if "clips" in data:
        out = {}
        for k, c in data["clips"].items():
            n = len(c.get("frames") or [])
            durs = list(c.get("durations_ms") or [])
            if not durs and c.get("fps") and n: durs = [int(round(1000 / float(c["fps"])))] * n
            if not durs and c.get("duration") and n: durs = [int(round(1000 * float(c["duration"]) / n))] * n
            out[k] = {"frames": list(c.get("frames") or []), "durations_ms": durs, "fps": c.get("fps"), "loop": c.get("loop"), "duration": c.get("duration")}
        return out
    if "anims" in data:
        out = {}
        for a in data["anims"]:
            frames = a.get("frames") or []; n = len(frames); fps = a.get("frameRate") or a.get("fps")
            names = [f.get("frame") if isinstance(f, dict) else str(f) for f in frames]
            durs = [int(round(1000 / float(fps)))] * n if fps and n else []
            out[a.get("key") or a.get("name") or "anim"] = {"frames": names, "durations_ms": durs, "fps": fps, "loop": (a.get("repeat", 0) == -1), "duration": n / fps if fps and n else None}
        return out
    if isinstance(data.get("meta"), dict) and (data["meta"].get("frameTags") is not None or "frames" in data) and "image" in (data.get("meta") or {}):
        _, clips, _ = ase_json_import.convert(data, sheet=os.path.splitext(os.path.basename(path))[0] or "sprite")
        return load_clips({"clips": clips})
    if "frames" in data and isinstance(data["frames"], list) and data["frames"] and "duration_ms" in data["frames"][0]:
        durs = [int(f["duration_ms"]) for f in data["frames"]]; names = [f.get("file") or f.get("filename") or str(f.get("index", i)) for i, f in enumerate(data["frames"])]
        return {"all": {"frames": names, "durations_ms": durs, "fps": data.get("fps"), "loop": data.get("loop"), "duration": data.get("total_ms", sum(durs)) / 1000}}
    raise SystemExit("unrecognised animation JSON (want clips, Phaser anims, Aseprite sheet JSON, or a frames list with duration_ms)")


def nearest_grid(ms, step):
    if step <= 0: return ms, 0.0
    n = max(1, int(round(ms / step))); return n * step, abs(ms - n * step)


def check(clips, fps=None, tolerance_ms=1.0, min_ms=0, max_ms=0, allow_variable=False, min_clip=0, max_clip=0):
    findings = []
    def add(sev, clip, code, msg): findings.append({"severity": sev, "clip": clip, "code": code, "message": msg})
    for name, c in clips.items():
        durs, n = c["durations_ms"], len(c["frames"])
        if n == 0: add("error", name, "empty", "clip has no frames"); continue
        if n == 1 and c.get("loop"): add("warning", name, "single-loop", "a 1-frame clip is marked looping (it will look frozen)")
        if not durs or len(durs) != n:
            add("error", name, "no-timing", f"cannot derive {n} frame duration(s)"); continue
        total = sum(durs)
        if min_clip and total / 1000 < min_clip: add("error", name, "short-clip", f"clip is {total / 1000:.3f}s, shorter than --min-clip {min_clip}")
        if max_clip and total / 1000 > max_clip: add("error", name, "long-clip", f"clip is {total / 1000:.3f}s, longer than --max-clip {max_clip}")
        if c.get("duration") is not None and abs(c["duration"] - total / 1000) > 0.02: add("warning", name, "duration-mismatch", f"stored duration {c['duration']}s != sum of frames {total / 1000:.4f}s")
        implied = 1000 * n / total if total else 0
        target = fps or c.get("fps")
        if target and implied and abs(implied - float(target)) > 0.15 and len(set(durs)) == 1:
            add("warning", name, "fps-mismatch", f"stored fps {float(target):g} but durations imply {implied:.3g}")
        grid = 1000.0 / float(target) if target else None
        if grid:
            for i, d in enumerate(durs):
                _, err = nearest_grid(d, grid)
                if err > tolerance_ms: add("error", name, "off-grid", f"frame {i} is {d} ms, not a multiple of {grid:.3f} ms (fps {float(target):g}) by {err:.2f} ms")
        uniq = sorted(set(durs))
        if not allow_variable and len(uniq) > 1: add("warning", name, "variable", f"mixed durations {uniq} ms in a clip" + (f" that claims {float(c['fps']):g} fps" if c.get("fps") else ""))
        if min_ms:
            for i, d in enumerate(durs):
                if d < min_ms: add("error", name, "too-short", f"frame {i} is {d} ms, under --min-ms {min_ms}")
        if max_ms:
            for i, d in enumerate(durs):
                if d > max_ms: add("error", name, "too-long", f"frame {i} is {d} ms, over --max-ms {max_ms}")
        if any(d <= 0 for d in durs): add("error", name, "zero", "a frame has duration <= 0 (browsers often treat 0 as 100 ms)")
    return findings


def main(argv=None):
    ap = argparse.ArgumentParser(description="Check animation clip timings against a target fps grid.")
    ap.add_argument("input"); ap.add_argument("--fps", type=float, help="target fps grid (default: each clip's own fps, if stored)")
    ap.add_argument("--tolerance-ms", type=float, default=1.0); ap.add_argument("--min-ms", type=int, default=0); ap.add_argument("--max-ms", type=int, default=0)
    ap.add_argument("--min-clip", type=float, default=0); ap.add_argument("--max-clip", type=float, default=0)
    ap.add_argument("--allow-variable", action="store_true"); ap.add_argument("--strict", action="store_true"); ap.add_argument("--report", help="write a JSON report")
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
    _src_keys = ('input',)
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

    clips = load_clips(json.load(open(a.input)), a.input)
    F = check(clips, a.fps, a.tolerance_ms, a.min_ms, a.max_ms, a.allow_variable, a.min_clip, a.max_clip)
    for f in F: print(f"{f['severity'].upper():<7} {f['clip']:<16} {f['code']:<18} {f['message']}")
    e = sum(f["severity"] == "error" for f in F); w = len(F) - e
    print(f"{len(clips)} clip(s), {e} error(s), {w} warning(s)")
    if a.report: json.dump({"clips": {k: {"frames": len(v["frames"]), "durations_ms": v["durations_ms"], "fps": v.get("fps")} for k, v in clips.items()}, "findings": F}, open(a.report, "w"), indent=1)
    return 1 if e or (a.strict and w) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
