#!/usr/bin/env python3
"""wav-pad: pad a PCM WAV with leading and/or trailing silence. `--head` / `--tail` add
seconds of silence; `--to-duration` extends the tail (or, with `--center`, splits the
extra silence on both sides) so the file lasts at least that many seconds. Already-long
files are left at their current length. Uses the shared audio-tidy PCM reader (paths must
be str()). Writes a new WAV; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import safe_out, audio_tidy  # noqa: E402


def pad(x, sr, head_s=0.0, tail_s=0.0, to_duration=None, center=False):
    if x.ndim == 1:
        x = x[:, None]
    n, ch = x.shape
    head = max(0, int(round(float(head_s or 0) * sr)))
    tail = max(0, int(round(float(tail_s or 0) * sr)))
    y = np.concatenate([
        np.zeros((head, ch), dtype=x.dtype),
        x,
        np.zeros((tail, ch), dtype=x.dtype),
    ], axis=0)
    if to_duration is not None:
        want = max(0, int(round(float(to_duration) * sr)))
        if len(y) < want:
            extra = want - len(y)
            if center:
                a, b = extra // 2, extra - extra // 2
                y = np.concatenate([np.zeros((a, ch), dtype=x.dtype), y, np.zeros((b, ch), dtype=x.dtype)], axis=0)
            else:
                y = np.concatenate([y, np.zeros((extra, ch), dtype=x.dtype)], axis=0)
    return y, head, tail


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pad a WAV with leading/trailing silence or out to a target duration.")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--head", type=float, default=0.0, help="leading silence in seconds")
    ap.add_argument("--tail", type=float, default=0.0, help="trailing silence in seconds")
    ap.add_argument("--to-duration", type=float, help="pad so the file lasts at least this many seconds")
    ap.add_argument("--center", action="store_true", help="with --to-duration, split extra silence both sides")
    ap.add_argument("--bits", type=int, default=16, choices=(16, 24, 32))
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    if a.head <= 0 and a.tail <= 0 and a.to_duration is None:
        sys.exit("pass --head, --tail and/or --to-duration")
    x, sr = audio_tidy.read_wav(str(a.wav))
    y, head, tail = pad(x, sr, a.head, a.tail, a.to_duration, a.center)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(str(a.out), y, sr, bits=a.bits)
    rec = {"sr": sr, "frames_in": int(x.shape[0] if x.ndim > 0 else 0), "frames_out": int(y.shape[0]),
           "head_frames": head, "tail_frames": int(y.shape[0] - x.shape[0] - head), "out": a.out}
    print(f"{rec['frames_in']} -> {rec['frames_out']} frames @ {sr} Hz -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
