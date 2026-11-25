#!/usr/bin/env python3
"""wav-gate: apply a noise gate to a PCM WAV. Samples below --thresh-db are
faded toward silence with optional attack, hold and release. Length and sample
rate are unchanged; the first smpl loop is preserved. The input is never
overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, audio_tidy, wav_loop_meta  # noqa: E402


def gate(x, sr, thresh_db, attack_ms, hold_ms, release_ms):
    x = np.asarray(x, dtype=np.float64)
    mono = np.max(np.abs(x), axis=1) if x.ndim == 2 else np.abs(x)
    thresh = 10.0 ** (thresh_db / 20.0)
    attack = max(1, int(round(attack_ms * 0.001 * sr)))
    release = max(1, int(round(release_ms * 0.001 * sr)))
    hold = max(0, int(round(hold_ms * 0.001 * sr)))
    att_s = 1.0 / attack
    rel_s = 1.0 / release
    env = np.zeros(len(mono), dtype=np.float64)
    open_env = 0.0
    held = 0
    open_flag = False
    for i, mag in enumerate(mono):
        if mag >= thresh:
            open_flag = True
            held = hold
        elif held > 0:
            held -= 1
            open_flag = True
        else:
            open_flag = False
        target = 1.0 if open_flag else 0.0
        step = att_s if target > open_env else rel_s
        if open_env < target:
            open_env = min(target, open_env + step)
        else:
            open_env = max(target, open_env - step)
        env[i] = open_env
    if x.ndim == 2:
        y = x * env[:, None]
    else:
        y = x * env
    closed = float(np.mean(env < 0.5)) if len(env) else 0.0
    return y.astype(np.float32), closed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Noise-gate a PCM WAV (length unchanged, smpl loop kept).")
    ap.add_argument("input")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--thresh-db", type=float, default=-40.0)
    ap.add_argument("--attack-ms", type=float, default=5.0)
    ap.add_argument("--hold-ms", type=float, default=20.0)
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
    y, sr = audio_tidy.read_wav(a.input)
    out, closed = gate(y, sr, a.thresh_db, a.attack_ms, a.hold_ms, a.release_ms)
    bits = a.bits or 16
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(a.out, out, sr, bits=bits)
    if loops:
        data = open(a.out, "rb").read()
        L = loops[0]
        open(a.out, "wb").write(wav_loop_meta.set_loop(data, L["start"], L["end"]))
    rec = {
        "out": a.out,
        "rate": sr,
        "frames": int(len(out) if out.ndim == 1 else len(out)),
        "thresh_db": a.thresh_db,
        "closed_fraction": round(closed, 4),
        "loop_kept": bool(loops),
    }
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print("gated %s (closed %.1f%%) -> %s" % (a.input, closed * 100.0, a.out))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
