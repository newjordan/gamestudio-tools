#!/usr/bin/env python3
"""sfx-envelope: apply an ADSR (or a custom linearly interpolated envelope) plus optional edge fades to a folder of
WAVs, writing new files and a before/after peak report. Sustain sits between decay and release; if attack+decay+release
exceed the clip, the stages are scaled to fit. Inputs may be files or folders. The input path is never overwritten.
PCM only, via audio-tidy.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(".wav")))
        elif p.lower().endswith(".wav"):
            out.append(p)
        else:
            raise SystemExit(f"not a WAV or folder: {p}")
    return out


def dest_for(src, outdir, suffix):
    name = os.path.basename(src)
    if suffix:
        stem, ext = os.path.splitext(name); name = stem + suffix + ext
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def adsr_gain(n, sr, attack_ms, decay_ms, sustain, release_ms):
    if n <= 0: return np.zeros(0, np.float32)
    a = max(0, int(round(sr * attack_ms / 1000)))
    d = max(0, int(round(sr * decay_ms / 1000)))
    r = max(0, int(round(sr * release_ms / 1000)))
    total = a + d + r
    if total > n and total > 0:
        scale = n / total
        a, d, r = int(a * scale), int(d * scale), int(r * scale)
        # give leftover samples to sustain (or attack if nothing else)
        leftover = n - (a + d + r)
        if leftover > 0: a += leftover  # will be overwritten if we recompute sustain region; actually put leftover in sustain
        # recompute: leftover should be sustain, not attack. Fix:
        a = max(0, int(round(sr * attack_ms / 1000 * scale)))
        d = max(0, int(round(sr * decay_ms / 1000 * scale)))
        r = max(0, n - a - d)
        sustain_n = 0
    else:
        sustain_n = n - total
    g = np.ones(n, np.float32)
    i = 0
    if a:
        g[:a] = np.linspace(0, 1, a, endpoint=True, dtype=np.float32); i = a
    if d:
        g[i:i + d] = np.linspace(1, sustain, d, endpoint=True, dtype=np.float32); i += d
    if sustain_n:
        g[i:i + sustain_n] = sustain; i += sustain_n
    if r:
        start = g[i - 1] if i else sustain
        # release from current level (sustain, or last decay sample) down to 0
        g[i:] = np.linspace(start, 0, n - i, endpoint=True, dtype=np.float32)
    return g


def custom_gain(n, points):
    """points: list of (t_unit 0-1, level)."""
    pts = sorted(points)
    if pts[0][0] != 0: pts = [(0.0, pts[0][1])] + pts
    if pts[-1][0] != 1: pts = pts + [(1.0, pts[-1][1])]
    xs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    t = np.linspace(0, 1, n, endpoint=True) if n else np.zeros(0)
    return np.interp(t, xs, ys).astype(np.float32)


def fade_gain(n, sr, fade_ms):
    k = max(0, int(round(sr * fade_ms / 1000)))
    g = np.ones(n, np.float32)
    if k <= 0 or n == 0: return g
    k = min(k, n // 2 if n > 1 else n)
    if k:
        g[:k] *= np.linspace(0, 1, k, endpoint=True, dtype=np.float32)
        g[n - k:] *= np.linspace(1, 0, k, endpoint=True, dtype=np.float32)
    return g


def peak(x):
    return float(np.max(np.abs(x))) if len(x) else 0.0


def apply_one(path, gain, fade_ms, bits):
    x, sr = audio_tidy.read_wav(path)
    n = len(x)
    g = gain(n, sr)
    if fade_ms: g = g * fade_gain(n, sr, fade_ms)
    y = x * g[:, None]
    # avoid introducing clips beyond the input peak * 1 (envelope max is typically 1)
    rec = {"file": path, "rate": sr, "channels": x.shape[1], "duration_s": round(n / sr, 3),
           "peak_before": round(peak(x), 6), "peak_after": round(peak(y), 6)}
    return rec, y, sr


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply an ADSR or custom envelope plus fade to WAVs.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir"); ap.add_argument("--suffix", default="")
    ap.add_argument("--attack-ms", type=float, default=10)
    ap.add_argument("--decay-ms", type=float, default=30)
    ap.add_argument("--sustain", type=float, default=0.7)
    ap.add_argument("--release-ms", type=float, default=50)
    ap.add_argument("--adsr", help="shortcut A,D,S,R as ms,ms,level,ms")
    ap.add_argument("--envelope", help="custom envelope points t:level,t:level with t in 0-1")
    ap.add_argument("--fade-ms", type=float, default=0)
    ap.add_argument("--bits", type=int, choices=(16, 24, 32), default=16)
    ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.adsr:
        parts = [p.strip() for p in a.adsr.split(",")]
        if len(parts) != 4: sys.exit("--adsr needs attack,decay,sustain,release")
        a.attack_ms, a.decay_ms, a.sustain, a.release_ms = map(float, parts)
    if not 0 <= a.sustain <= 1: sys.exit("--sustain must be between 0 and 1")
    custom = None
    if a.envelope:
        custom = []
        for bit in a.envelope.split(","):
            t, _, lv = bit.partition(":")
            custom.append((float(t), float(lv)))
        if not custom: sys.exit("empty --envelope")
    files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
        sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
    if a.outdir and not a.dry_run: os.makedirs(a.outdir, exist_ok=True)

    def gain(n, sr):
        if custom is not None: return custom_gain(n, custom)
        return adsr_gain(n, sr, a.attack_ms, a.decay_ms, a.sustain, a.release_ms)

    rows = []
    for f in files:
        dest = dest_for(f, a.outdir, a.suffix)
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit(f"refusing to overwrite the input: {dest} or pass --in-place")
        rec, y, sr = apply_one(f, gain, a.fade_ms, a.bits)
        rec["out"] = dest
        if not a.dry_run:
            audio_tidy.write_wav(dest, y, sr, bits=a.bits)
        rows.append(rec)
        print(f"{os.path.basename(f)}: peak {rec['peak_before']:.3f} -> {rec['peak_after']:.3f}" + ("" if a.dry_run else f" -> {dest}"))
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv and rows:
        w = csv.DictWriter(open(a.csv, "w", newline=""), fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
