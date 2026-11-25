#!/usr/bin/env python3
"""loop-xfade: make a WAV loop without a click by crossfading the end of the loop into the audio that precedes the loop start.
For a loop start..end (frames, end inclusive) and a fade of L frames, the last L frames of the loop are blended into the L frames
just before `start`, so the last sample equals the sample that naturally precedes `start` and the wrap is continuous. The file keeps
its length and bit depth; only the tail of the loop changes (the music before `start` is the pre-roll, so it must be at least L frames).
Fades are equal-power by default (good for uncorrelated material) or --linear (good for the same waveform, e.g. a pad). Loop points come
from --start/--end or the file's own smpl chunk; the result gets a smpl loop chunk. Reports the size of the jump at the wrap, before
and after, as a multiple of the file's typical sample-to-sample change. Other chunks (cue, list, ...) are dropped; PCM WAV only.
"""
import argparse, os, sys

import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(here, "..", "audio-tidy")); sys.path.insert(0, os.path.join(here, "..", "wav-loop-meta"))
import audio_tidy, wav_loop_meta  # noqa: E402


def wrap_jump(x, start, end):
    """Size of the step across the loop wrap relative to the typical step inside the loop (RMS of sample differences)."""
    seg = x[start:end + 1]; d = np.diff(seg, axis=0); typ = float(np.sqrt(np.mean(d ** 2))) if len(d) else 0.0
    jump = float(np.abs(seg[0] - seg[-1]).max())
    return jump / typ if typ > 0 else (0.0 if jump == 0 else float("inf"))


def crossfade(x, start, end, length, linear=False):
    n = len(x)
    if not (0 <= start < end < n): raise SystemExit(f"loop {start}..{end} is outside the file (0..{n - 1})")
    if length < 1: raise SystemExit("fade length must be at least 1 frame")
    if length > start: raise SystemExit(f"fade of {length} frames needs {length} frames before the loop start, but start is {start}")
    if length > (end - start + 1) // 2: raise SystemExit(f"fade of {length} frames is longer than half the loop ({end - start + 1} frames)")
    y = x.copy(); t = (np.arange(length) + 1) / length                       # 1/L .. 1: the last sample is fully the pre-roll sample
    if linear: wa, wb = 1 - t, t
    else: wa, wb = np.cos(t * np.pi / 2), np.sin(t * np.pi / 2)
    tail = slice(end - length + 1, end + 1); pre = slice(start - length, start)
    y[tail] = x[tail] * wa[:, None] + x[pre] * wb[:, None]
    return y


def main(argv=None):
    ap = argparse.ArgumentParser(description="Crossfade a WAV loop so it wraps without a click.")
    ap.add_argument("wav"); ap.add_argument("-o", "--out", required=True); ap.add_argument("--start", type=int); ap.add_argument("--end", type=int)
    ap.add_argument("--fade-ms", type=float, default=50.0); ap.add_argument("--fade-frames", type=int); ap.add_argument("--linear", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.wav) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    data = open(a.wav, "rb").read(); sr_h, frames_h = wav_loop_meta.info(data)
    start, end = a.start, a.end
    if start is None or end is None:
        loops = wav_loop_meta.read_loops(data)
        if not loops: sys.exit("no --start/--end given and the file has no smpl loop")
        start, end = loops[0]["start"], loops[0]["end"]
    x, sr = audio_tidy.read_wav(a.wav); bits = next(int.from_bytes(p[14:16], "little") for c, p in wav_loop_meta.chunks(data) if c == b"fmt ")
    L = a.fade_frames or max(1, int(round(sr * a.fade_ms / 1000)))
    before = wrap_jump(x, start, end); y = crossfade(x, start, end, L, a.linear); after = wrap_jump(y, start, end)
    if before < 1.5: print("NOTE: this loop already wraps about as smoothly as the audio itself; a crossfade is probably not needed")
    audio_tidy.write_wav(a.out, y, sr, bits); out = wav_loop_meta.set_loop(open(a.out, "rb").read(), start, end); open(a.out, "wb").write(out)
    print(f"loop {start}..{end} ({(end - start + 1) / sr:.2f}s), {'linear' if a.linear else 'equal-power'} fade of {L} frames ({L / sr * 1000:.0f} ms); wrap jump {before:.1f}x -> {after:.1f}x typical step -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
