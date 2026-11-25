#!/usr/bin/env python3
"""wav-loop-snap: trim or pad a PCM WAV to a loop region taken from the file's `smpl` chunk
(first loop) or from `--start` / `--end` (inclusive sample indices, smpl convention). If the
region starts before 0 or ends past the last sample, silence is padded; then the file is sliced
to `[start, end]` inclusive. A new `smpl` loop covering the whole output (0..n-1) is written
unless `--no-meta`. Uses the shared audio-tidy PCM reader (paths must be str()). Writes a new
WAV; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys, wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, audio_tidy, wav_loop_meta  # noqa: E402


def wav_bits(path):
    with wave.open(path, "rb") as wf:
        return wf.getsampwidth() * 8


def snap(x, start, end):
    if x.ndim == 1:
        x = x[:, None]
    n, ch = x.shape
    start, end = int(start), int(end)
    if start > end:
        raise SystemExit(f"loop start {start} is after end {end}")
    padded = 0
    if start < 0:
        head = -start
        x = np.concatenate([np.zeros((head, ch), dtype=x.dtype), x], axis=0)
        end += head
        start = 0
        n = x.shape[0]
        padded += head
    if end >= n:
        tail = end - n + 1
        x = np.concatenate([x, np.zeros((tail, ch), dtype=x.dtype)], axis=0)
        n = x.shape[0]
        padded += tail
    y = x[start:end + 1].copy()
    return y, start, end, padded


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trim or pad a WAV to a smpl loop region or given start/end samples.")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--start", type=int, help="first sample of the region (overrides smpl start)")
    ap.add_argument("--end", type=int, help="last sample of the region, inclusive (overrides smpl end)")
    ap.add_argument("--no-meta", action="store_true", help="do not write a smpl chunk on the output")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32),
                    help="output bit depth (default: same as the input, 16 if unknown)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    raw = open(a.wav, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    if a.start is None or a.end is None:
        if not loops:
            sys.exit("no smpl loop in the file; pass --start and --end")
        lp = loops[0]
        start = a.start if a.start is not None else int(lp["start"])
        end = a.end if a.end is not None else int(lp["end"])
    else:
        start, end = a.start, a.end
    x, sr = audio_tidy.read_wav(str(a.wav))
    y, start, end, padded = snap(x, start, end)
    bits = a.bits or wav_bits(str(a.wav))
    if bits not in (16, 24, 32):
        bits = 16
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(str(a.out), y, sr, bits=bits)
    n = int(y.shape[0])
    loop_out = None
    if not a.no_meta:
        if n < 2:
            raise SystemExit("output is shorter than 2 samples; cannot write a smpl loop")
        patched = wav_loop_meta.set_loop(open(a.out, "rb").read(), 0, n - 1)
        open(a.out, "wb").write(patched)
        loop_out = {"start": 0, "end": n - 1}
    rec = {"sr": sr, "frames_in": int(x.shape[0]), "frames_out": n, "region": [start, end],
           "padded": padded, "loop": loop_out, "out": a.out}
    print(f"{rec['frames_in']} -> {n} frames @ {sr} Hz (region {start}..{end}" +
          (f", padded {padded}" if padded else "") + f") -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
