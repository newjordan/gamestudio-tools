#!/usr/bin/env python3
"""sfx-variants: turn one recorded/generated sound into N natural-sounding variations so repeated
footsteps, hits and pickups do not sound machine-gunned. Each variant gets a seeded random pitch shift
(resampling, so duration changes with pitch like a tape), gain, optional tiny start offset, and a short
fade; peaks are limited to --peak dBFS. Same seed -> same variants. Mono or stereo 8/16/24/32-bit PCM WAV in,
16-bit WAV out.
"""
import argparse, json, os, wave
import numpy as np
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


def read_wav(path):
    return audio_tidy.read_wav(path)


def write_wav(path, x, sr):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(x.shape[1]); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def variant(x, sr, rng, semitones=1.5, gain_db=2.0, offset_ms=0.0, fade_ms=3.0, peak_db=-1.0):
    st = rng.uniform(-semitones, semitones); factor = 2 ** (st / 12)          # >1 = higher and shorter
    n = max(2, int(round(len(x) / factor)))
    old, new = np.arange(len(x)), np.linspace(0, len(x) - 1, n)
    y = np.stack([np.interp(new, old, x[:, c]) for c in range(x.shape[1])], 1).astype(np.float32)
    if offset_ms:
        off = int(rng.uniform(0, offset_ms) * sr / 1000); y = np.concatenate([np.zeros((off, y.shape[1]), np.float32), y])
    g = rng.uniform(-gain_db, gain_db); y *= 10 ** (g / 20)
    nf = min(int(sr * fade_ms / 1000), len(y) // 2)
    if nf:
        r = np.linspace(0, 1, nf)[:, None]; y[:nf] *= r; y[-nf:] *= r[::-1]
    lim = 10 ** (peak_db / 20); pk = np.abs(y).max()
    if pk > lim: y *= lim / pk
    return y, {"semitones": round(float(st), 3), "gain_db": round(float(g), 3)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Make seeded variations of a WAV sound effect.")
    ap.add_argument("input"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("-n", "--count", type=int, default=5)
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--semitones", type=float, default=1.5)
    ap.add_argument("--gain-db", type=float, default=2.0); ap.add_argument("--offset-ms", type=float, default=0.0)
    ap.add_argument("--fade-ms", type=float, default=3.0); ap.add_argument("--peak", type=float, default=-1.0)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('input',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    x, sr = read_wav(a.input); os.makedirs(a.outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(a.input))[0]; meta = []
    for i in range(a.count):
        y, p = variant(x, sr, np.random.default_rng(a.seed + i), a.semitones, a.gain_db, a.offset_ms, a.fade_ms, a.peak)
        name = f"{base}_v{i + 1:02d}.wav"; write_wav(os.path.join(a.outdir, name), y, sr); meta.append({"file": name, "seconds": round(len(y) / sr, 4), **p})
    json.dump(meta, open(os.path.join(a.outdir, f"{base}_variants.json"), "w"), indent=1)
    print(f"wrote {a.count} variant(s) of {a.input} to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
