#!/usr/bin/env python3
"""wav-fade: apply a linear or equal-power (sine) fade-in and/or fade-out to a PCM WAV.
If the two fades would overlap, they are scaled down so they meet in the middle. Uses the
shared audio-tidy PCM reader (paths must be str()). Writes a new WAV; the input is never
overwritten unless `--in-place`.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import safe_out, audio_tidy  # noqa: E402


def fade_gains(n, fade_in, fade_out, shape):
    g = np.ones(n, dtype=np.float64)
    fi, fo = fade_in, fade_out
    if fi + fo > n and (fi + fo) > 0:
        s = n / (fi + fo)
        fi, fo = int(fi * s), int(fo * s)
        # spend leftover samples on the fade-out if possible
        leftover = n - fi - fo
        if leftover > 0:
            fo += leftover
    if fi > 0:
        t = np.linspace(0.0, 1.0, fi, endpoint=True)
        g[:fi] = t if shape == "linear" else np.sin(t * (np.pi / 2.0))
    if fo > 0:
        t = np.linspace(1.0, 0.0, fo, endpoint=True)
        g[n - fo:] = t if shape == "linear" else np.sin(t * (np.pi / 2.0))
    return g, fi, fo


def apply_fade(x, sr, in_s, out_s, shape):
    if x.ndim == 1:
        x = x[:, None]
    n = x.shape[0]
    fi = max(0, int(round(float(in_s) * sr)))
    fo = max(0, int(round(float(out_s) * sr)))
    g, fi, fo = fade_gains(n, fi, fo, shape)
    y = x * g[:, None]
    return y, fi, fo


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply a linear or equal-power fade-in and/or fade-out to a WAV.")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--in", dest="fade_in", type=float, default=0.0, help="fade-in length in seconds")
    ap.add_argument("--out-dur", dest="fade_out", type=float, default=0.0,
                    help="fade-out length in seconds (not to be confused with --out)")
    ap.add_argument("--fade-out", dest="fade_out", type=float, help="alias for --out-dur")
    ap.add_argument("--shape", choices=("linear", "equal-power"), default="linear")
    ap.add_argument("--bits", type=int, default=16, choices=(16, 24, 32))
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    if a.fade_in <= 0 and a.fade_out <= 0:
        sys.exit("pass a positive --in and/or --fade-out / --out-dur")
    x, sr = audio_tidy.read_wav(str(a.wav))
    y, fi, fo = apply_fade(x, sr, a.fade_in, a.fade_out, a.shape)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(str(a.out), y, sr, bits=a.bits)
    rec = {"sr": sr, "frames": int(y.shape[0]), "fade_in_frames": fi, "fade_out_frames": fo,
           "shape": a.shape, "out": a.out}
    print(f"fade {a.shape} in={fi} out={fo} frames @ {sr} Hz -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
