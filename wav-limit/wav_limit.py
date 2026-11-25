#!/usr/bin/env python3
"""wav-limit: apply a peak limiter to a PCM WAV so no sample exceeds
`--ceiling-db`. A simple envelope follower with attack and release reduces
gain when the signal would go over the ceiling; sample rate and length stay
the same and the first smpl loop is preserved. The input is never overwritten
unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, audio_tidy, wav_loop_meta  # noqa: E402


def limit(x, sr, ceiling_db, attack_ms, release_ms):
    x = np.asarray(x, dtype=np.float64)
    mono = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    ceiling = 10.0 ** (ceiling_db / 20.0)
    if ceiling <= 0:
        raise SystemExit("--ceiling-db is too low")
    attack = max(1, int(round(attack_ms * 0.001 * sr)))
    release = max(1, int(round(release_ms * 0.001 * sr)))
    att_s = 1.0 / attack
    rel_s = 1.0 / release
    g = 1.0
    out_g = np.empty(len(mono), dtype=np.float64)
    for i, mag in enumerate(mono):
        wanted = 1.0 if mag <= 0 else min(1.0, ceiling / mag)
        if wanted < g:
            g = max(wanted, g - att_s)
        else:
            g = min(1.0, g + rel_s)
            if g > wanted and mag > ceiling:
                g = wanted
        out_g[i] = g
    if x.ndim == 2:
        y = x * out_g[:, None]
    else:
        y = x * out_g
    y = np.clip(y, -ceiling, ceiling)
    peak = float(np.max(np.abs(y))) if y.size else 0.0
    limited = float(np.mean(out_g < 0.999)) if out_g.size else 0.0
    return y.astype(np.float32), peak, limited


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Peak-limit a PCM WAV to a ceiling (dBFS).")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--ceiling-db", type=float, default=-0.1)
    ap.add_argument("--attack-ms", type=float, default=1.0)
    ap.add_argument("--release-ms", type=float, default=50.0)
    ap.add_argument("--bits", type=int, choices=(16, 24, 32))
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.input, a.out, a.in_place)
    if a.json:
        safe_out.check(a.input, a.json, a.in_place)

    raw = open(a.input, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    x, sr = audio_tidy.read_wav(a.input)
    bits = a.bits or 16
    y, peak, limited = limit(x, sr, a.ceiling_db, a.attack_ms, a.release_ms)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(a.out, y, sr, bits=bits)
    if loops:
        data = open(a.out, "rb").read()
        L = loops[0]
        open(a.out, "wb").write(wav_loop_meta.set_loop(data, L["start"], L["end"]))
    rec = {"out": a.out, "rate": sr, "ceiling_db": a.ceiling_db, "peak": peak,
           "limited_fraction": limited, "frames": int(len(y))}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("limited peak=%.4f (ceiling %.2f dBFS) -> %s" % (peak, a.ceiling_db, a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
