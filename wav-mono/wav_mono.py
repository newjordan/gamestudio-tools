#!/usr/bin/env python3
"""wav-mono: fold a WAV (or a folder of WAVs) to mono. `--mode mix` (default)
averages the channels; `left` / `right` keep one channel. Already-mono files are
copied. `smpl` loop markers are preserved. Writes next to the source with
`--suffix` or under `--outdir`. The input is never overwritten unless
`--in-place`. Already-mono files and `--mode left` / `right` copy integer PCM
(bit-exact at the same width). `--mode mix` on a multi-channel file averages.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx-normalize"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out, audio_tidy, wav_loop_meta, sfx_normalize, pcm_frames  # noqa: E402


def fold(x, mode):
    if x.ndim == 1:
        x = x[:, None]
    ch = x.shape[1]
    if ch == 1:
        return x, "already-mono"
    if mode == "mix":
        return x.mean(axis=1, keepdims=True).astype(x.dtype), "ok"
    if mode == "left":
        return x[:, 0:1], "ok"
    if mode == "right":
        return x[:, min(1, ch - 1):min(2, ch)], "ok"
    raise SystemExit(f"unknown mode {mode}")


def _integer_pick(samples, mode):
    """Copy a channel. None means the caller should average in float."""
    ch = samples.shape[1]
    if ch == 1:
        return samples, "already-mono"
    if mode == "left":
        return samples[:, 0:1], "ok"
    if mode == "right":
        return samples[:, 1:2], "ok"
    return None


def process(path, dest, mode, bits):
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    samples, sr, src_bits = pcm_frames.read_frames(path)
    picked = _integer_pick(samples, mode)
    if picked is not None:
        y, status = picked
        y, bits = pcm_frames.to_bits(y, src_bits, bits)
        pcm_frames.write_frames(dest, y, sr, bits)
        ch_in = int(samples.shape[1])
    else:
        x, sr = audio_tidy.read_wav(path)
        y, status = fold(x, mode)
        os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
        audio_tidy.write_wav(dest, y, sr, bits=bits)
        ch_in = int(x.shape[1] if x.ndim > 1 else 1)
    if loops:
        lp = loops[0]
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), lp["start"], lp["end"])
        open(dest, "wb").write(patched)
    return {"file": path, "out": dest, "rate": sr, "channels_in": ch_in,
            "channels_out": 1, "status": status, "mode": mode,
            "loop": ({"start": loops[0]["start"], "end": loops[0]["end"]} if loops else None)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Fold PCM WAV files to mono.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", help="output WAV (single file) or directory")
    ap.add_argument("--outdir")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--mode", choices=("mix", "left", "right"), default="mix")
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
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
        recs.append(process(p, dest, a.mode, a.bits))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "mode": a.mode}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} file(s) folded to mono ({a.mode})")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
