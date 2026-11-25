#!/usr/bin/env python3
"""wav-silence: write a silent PCM WAV, insert a silent gap into an existing
WAV, or zero a time range (`--replace START,END`). Generated or inserted
duration is `--duration` seconds. `smpl` loop markers are preserved (and
shifted when silence is inserted before them). The input is never overwritten
unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, audio_tidy, wav_loop_meta  # noqa: E402


def parse_range(s):
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 2 or parts[1] <= parts[0] or parts[0] < 0:
        raise SystemExit("--replace must be START,END in seconds, with END > START >= 0")
    return parts[0], parts[1]


def restore_loops(dest, loops):
    if not loops:
        return
    raw = open(dest, "rb").read()
    lp = loops[0]
    open(dest, "wb").write(wav_loop_meta.set_loop(raw, lp["start"], lp["end"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate, insert, or punch-in PCM silence.")
    ap.add_argument("input", nargs="?", help="existing WAV (omit to generate a silent file)")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--duration", type=float, help="silence length in seconds (generate or insert)")
    ap.add_argument("--at", type=float, default=None, help="insert point in seconds (requires an input and --duration)")
    ap.add_argument("--replace", help="zero the range START,END seconds in the input")
    ap.add_argument("--rate", type=int, default=44100)
    ap.add_argument("--channels", type=int, default=1)
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.replace and a.duration is not None:
        sys.exit("pass either --replace or --duration, not both")
    if a.input:
        safe_out.check(a.input, a.out, a.in_place)
        if a.json:
            safe_out.check(a.input, a.json, a.in_place)
        x, sr = audio_tidy.read_wav(a.input)
        loops = wav_loop_meta.read_loops(open(a.input, "rb").read())
        if a.replace:
            t0, t1 = parse_range(a.replace)
            i0 = int(round(t0 * sr))
            i1 = int(round(t1 * sr))
            y = np.array(x, dtype=np.float32, copy=True)
            y[i0:i1] = 0
            mode = "replace"
            dur = (i1 - i0) / sr
        else:
            if a.duration is None or a.duration < 0:
                sys.exit("inserting silence needs --duration >= 0")
            at = 0.0 if a.at is None else a.at
            if at < 0:
                sys.exit("--at must be >= 0")
            n = int(round(a.duration * sr))
            i = min(max(0, int(round(at * sr))), len(x))
            z = np.zeros((n,) + x.shape[1:], dtype=np.float32)
            y = np.concatenate([x[:i], z, x[i:]], axis=0)
            # shift loops that start at/after the insert point
            shifted = []
            for lp in loops:
                s, e = lp["start"], lp["end"]
                if s >= i:
                    s, e = s + n, e + n
                elif e > i:
                    e = e + n
                shifted.append({"start": s, "end": e})
            loops = shifted
            mode = "insert"
            dur = a.duration
        bits = a.bits
    else:
        if a.replace or a.at is not None:
            sys.exit("--replace / --at need an input WAV")
        if a.duration is None or a.duration < 0:
            sys.exit("generating silence needs --duration >= 0")
        if a.rate <= 0 or a.channels not in (1, 2):
            sys.exit("--rate must be > 0 and --channels 1 or 2")
        n = int(round(a.duration * a.rate))
        shape = (n,) if a.channels == 1 else (n, a.channels)
        y = np.zeros(shape, dtype=np.float32)
        sr = a.rate
        loops = []
        mode = "generate"
        dur = a.duration
        bits = a.bits
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(a.out, y, sr, bits=bits)
    restore_loops(a.out, loops)
    rec = {"out": a.out, "mode": mode, "duration": dur, "rate": sr,
           "frames": int(len(y)), "loop": (loops[0] if loops else None)}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{mode} {dur:g}s silence -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
