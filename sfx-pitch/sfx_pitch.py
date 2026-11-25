#!/usr/bin/env python3
"""sfx-pitch: pitch-shift a WAV by resampling. Duration changes with pitch (a +12 semitone
shift is half as long); there is no time-stretch or formant preservation. Linear interpolation,
sample rate unchanged. Writes a new WAV; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import safe_out, audio_tidy  # noqa: E402


def ratio_of(semitones=None, ratio=None):
    if semitones is not None and ratio is not None:
        raise SystemExit("pass either --semitones or --ratio, not both")
    if semitones is None and ratio is None:
        raise SystemExit("pass --semitones or --ratio")
    if ratio is not None:
        if ratio <= 0:
            raise SystemExit("--ratio must be positive")
        return float(ratio)
    return float(2 ** (semitones / 12.0))


def pitch_shift(x, ratio):
    if x.ndim == 1:
        x = x[:, None]
    n_in = x.shape[0]
    n_out = max(int(round(n_in / ratio)), 1)
    t_old = np.linspace(0.0, 1.0, n_in, endpoint=False)
    t_new = np.linspace(0.0, 1.0, n_out, endpoint=False)
    cols = [np.interp(t_new, t_old, x[:, c]) for c in range(x.shape[1])]
    return np.stack(cols, 1)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pitch-shift a WAV by resampling (duration follows pitch).")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--semitones", type=float, help="pitch change in semitones (positive = higher / shorter)")
    ap.add_argument("--ratio", type=float, help="playback ratio (>1 = higher / shorter); alternative to --semitones")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32), default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    ratio = ratio_of(a.semitones, a.ratio)
    x, sr = audio_tidy.read_wav(str(a.wav))
    y = pitch_shift(x, ratio)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(str(a.out), y, sr, a.bits)
    rec = {"ratio": ratio, "semitones": a.semitones, "frames_in": int(x.shape[0]),
           "frames_out": int(y.shape[0]), "rate": int(sr), "out": a.out}
    print(f"{rec['frames_in']} -> {rec['frames_out']} frames @ {sr} Hz (ratio {ratio:.4g}) -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
