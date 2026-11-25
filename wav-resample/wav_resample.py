#!/usr/bin/env python3
"""wav-resample: change a WAV's sample rate with linear interpolation (via
audio-tidy). `smpl` loop markers are scaled by the rate ratio and clamped to the
new length. PCM only; other RIFF chunks except a restored `smpl` loop are
dropped. Writes next to the source with `--suffix` or under `--outdir`. The input
is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx-normalize"))
import safe_out, audio_tidy, wav_loop_meta, sfx_normalize  # noqa: E402


def scale_loop(start, end, old_sr, new_sr, n_out):
    s = int(round(start * new_sr / old_sr))
    e = int(round(end * new_sr / old_sr))
    s = max(0, min(s, max(0, n_out - 1)))
    e = max(s + 1, min(e, n_out))
    return s, e


def process(path, dest, rate, bits):
    x, sr = audio_tidy.read_wav(path)
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    y = audio_tidy.resample(x, sr, rate)
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    audio_tidy.write_wav(dest, y, rate, bits=bits)
    rec = {"file": path, "out": dest, "rate_in": sr, "rate_out": rate,
           "frames_in": int(len(x)), "frames_out": int(len(y)), "loop": None}
    if loops:
        lp = loops[0]
        s, e = scale_loop(lp["start"], lp["end"], sr, rate, len(y))
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), s, e)
        open(dest, "wb").write(patched)
        rec["loop"] = {"start": s, "end": e}
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Resample PCM WAV files to a new sample rate.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--rate", type=int, required=True, help="target sample rate in Hz")
    ap.add_argument("-o", "--out", help="output WAV (single file) or ignored when many inputs")
    ap.add_argument("--outdir", help="directory for outputs")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.rate < 1:
        sys.exit("--rate must be a positive integer")
    paths = sfx_normalize.collect(a.inputs)
    if len(paths) > 1 and a.out and a.out.lower().endswith(".wav"):
        sys.exit("-o as a WAV path is only valid for a single input; use --outdir")
    if not a.outdir and a.suffix == "" and not a.out and not a.in_place:
        sys.exit("pass --outdir, --suffix, -o, or --in-place so inputs are not overwritten")
    out_file = a.out if (a.out and len(paths) == 1 and a.out.lower().endswith(".wav")) else None
    if a.out and not out_file and not a.outdir:
        a.outdir = a.out
    recs = []
    for p in paths:
        dest = sfx_normalize.dest_of(p, a.outdir, a.suffix, out_file)
        safe_out.check(p, dest, a.in_place)
        if a.json:
            safe_out.check(p, a.json, a.in_place)
        recs.append(process(p, dest, a.rate, a.bits))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "rate": a.rate}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} file(s) resampled to {a.rate} Hz")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
