#!/usr/bin/env python3
"""anim-hold: pad an anim-meta clip to a target duration by extending the last frame's
duration, or by repeating the last frame. `--add-frames N` appends the last frame N times
first. Matching `durations_ms` (or `durations` / `times`) lists are kept in lockstep; `fps`
and `loop` pass through. Writes a new clip JSON; the input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim-splice"))
import safe_out, anim_splice  # noqa: E402


def duration_of(clip, frames=None, durs=None):
    frames = list(clip.get("frames") or []) if frames is None else frames
    if durs is None and clip.get("durations_ms") is not None:
        durs = list(clip["durations_ms"])
    if durs:
        return sum(durs) / 1000.0
    if "duration" in clip and frames and clip.get("frames"):
        # 'duration' is the whole clip; if we already changed the frame list, scale
        old = len(clip.get("frames") or [])
        if old:
            return float(clip["duration"]) * (len(frames) / old)
    fps = float(clip.get("fps") or 12)
    return (len(frames) / fps) if frames else 0.0


def apply_hold(clip, to_duration=None, add_frames=0, mode="extend"):
    c = json.loads(json.dumps(clip))
    frames = list(c.get("frames") or [])
    if not frames:
        raise SystemExit("clip has no frames")
    durs = list(c["durations_ms"]) if c.get("durations_ms") is not None else None
    if durs is not None and len(durs) != len(frames):
        raise SystemExit("durations_ms length must match frames")
    if add_frames:
        if add_frames < 0:
            raise SystemExit("--add-frames must be >= 0")
        last = frames[-1]
        frames.extend([last] * add_frames)
        if durs is not None:
            last_d = durs[-1]
            durs.extend([last_d] * add_frames)
    if to_duration is not None:
        if to_duration < 0:
            raise SystemExit("--to-duration must be >= 0")
        cur = duration_of(c, frames, durs)
        if cur < to_duration - 1e-12:
            need = to_duration - cur
            if mode == "extend" and durs is not None:
                durs[-1] = durs[-1] + int(round(need * 1000))
            elif mode == "extend" and "duration" in c and durs is None:
                # keep existing frames, just stretch the clip duration
                # after add_frames the duration_of already scaled; set absolute target
                pass  # set below
            else:
                fps = float(c.get("fps") or 12)
                n = max(1, int(math_round_frames(need, fps)))
                frames.extend([frames[-1]] * n)
                if durs is not None:
                    total_ms = int(round(need * 1000))
                    slot = total_ms // n
                    parts = [slot] * n
                    parts[-1] += total_ms - sum(parts)
                    durs.extend(parts)
        if mode == "extend" and durs is None and "duration" in c:
            c["duration"] = max(float(duration_of(c, frames, durs)), float(to_duration))
    c["frames"] = frames
    if durs is not None:
        c["durations_ms"] = durs
        c["duration"] = round(sum(durs) / 1000.0, 4)
    elif "duration" in c and to_duration is not None:
        c["duration"] = max(float(c["duration"]), float(to_duration))
    elif "duration" in c and add_frames:
        old = len(clip.get("frames") or [])
        if old:
            c["duration"] = round(float(clip["duration"]) * len(frames) / old, 4)
    return c


def math_round_frames(need, fps):
    return max(1, int(round(need * fps)))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pad an anim-meta clip by holding or repeating the last frame.")
    ap.add_argument("clips")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--clip", help="clip to pad (default: the only clip)")
    ap.add_argument("--to-duration", type=float, help="pad so the clip lasts at least this many seconds")
    ap.add_argument("--add-frames", type=int, default=0, help="append the last frame N times")
    ap.add_argument("--mode", choices=("extend", "repeat"), default="extend",
                    help="extend: stretch the last duration (or the duration field); repeat: append frames")
    ap.add_argument("--name", help="name of the written clip (default: the source clip)")
    ap.add_argument("--only", action="store_true", help="write a file containing only the padded clip")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.clips, a.out, a.in_place)
    if a.json:
        safe_out.check(a.clips, a.json, a.in_place)
    if a.to_duration is None and not a.add_frames:
        sys.exit("pass --to-duration and/or --add-frames")
    data = anim_splice.load(a.clips)
    clips = data["clips"]
    if a.clip:
        if a.clip not in clips:
            sys.exit(f"unknown clip: {a.clip}")
        name = a.clip
    elif len(clips) == 1:
        name = next(iter(clips))
    else:
        sys.exit("pass --clip when the file has more than one clip")
    new = apply_hold(clips[name], to_duration=a.to_duration, add_frames=a.add_frames, mode=a.mode)
    dest = a.name or name
    if a.only:
        out = dict(data)
        out["clips"] = {dest: new}
    else:
        out = dict(data)
        out["clips"] = dict(clips)
        out["clips"][dest] = new
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    rec = {"clip": dest, "frames": len(new.get("frames") or []),
           "duration": new.get("duration", duration_of(new)), "out": a.out, "mode": a.mode}
    print(f"{dest}: {rec['frames']} frame(s), {rec['duration']}s -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
