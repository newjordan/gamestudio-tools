#!/usr/bin/env python3
"""wav-batch-meta: loudness and technical report for many WAV files, checked against a target, with a CI exit code.
Per file: duration, rate, channels, bit depth, sample peak, true peak (4x oversampled), RMS, crest factor, DC offset, clipped
samples, leading/trailing silence, and integrated loudness in LUFS per ITU-R BS.1770-4 (K-weighting, 400 ms blocks with 75%
overlap, -70 LUFS absolute and -10 LU relative gates), plus maximum momentary (400 ms) loudness. Files shorter than 400 ms have no
gating block: the whole file is measured as one block and flagged "short". Channels beyond stereo are weighted 1.0 (no
surround weights). Targets can be per folder: --rule "music/*=-16" --rule "sfx/*=-18". The suggested gain is the dB needed to
hit the target, capped so the true peak stays under --max-true-peak. PCM WAV only (8/16/24/32-bit integer).
"""
import argparse, os, csv, fnmatch, glob, json, math, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402


def k_filters(fs):
    """BS.1770 K-weighting as two biquads, designed for any sample rate (b, a each)."""
    G, Q, fc = 3.99984385397, 0.7071752369554193, 1681.9744509555319
    K = math.tan(math.pi * fc / fs); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416; a0 = 1 + K / Q + K * K
    s1 = ([(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0], [1.0, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0])
    Q2, fc2 = 0.5003270373238773, 38.13547087613982; K = math.tan(math.pi * fc2 / fs); a0 = 1 + K / Q2 + K * K
    s2 = ([1.0, -2.0, 1.0], [1.0, 2 * (K * K - 1) / a0, (1 - K / Q2 + K * K) / a0])
    return s1, s2


def k_weight(x, fs):
    """Apply the K filters to x (n,) by multiplying with the biquads' frequency response on a zero-padded FFT (no SciPy needed).
    The padding is long enough for the 38 Hz high-pass tail to die away, so this equals running the IIR filters sample by sample."""
    n = len(x); m = 1 << int(math.ceil(math.log2(n + int(fs * 1.0) + 1)))
    w = np.exp(-2j * np.pi * np.arange(m // 2 + 1) / m); H = np.ones(m // 2 + 1, complex)
    for b, a in k_filters(fs):
        H *= (b[0] + b[1] * w + b[2] * w * w) / (a[0] + a[1] * w + a[2] * w * w)
    return np.fft.irfft(np.fft.rfft(x, m) * H, m)[:n]


def lufs(x, fs):
    """x: (n, ch) float. -> (integrated LUFS or None, max momentary LUFS or None, short_flag)."""
    if not fs or fs < 1 or fs > 768000:
        raise GstInputError("WAV sample rate is invalid")
    try:
        return _lufs(x, fs)
    except MemoryError as e:
        raise GstInputError("WAV is too large or has an invalid header") from e


def _lufs(x, fs):
    n = len(x); blk = int(round(0.4 * fs)); hop = int(round(0.1 * fs))
    if n == 0: return None, None, False
    zs = np.stack([np.square(k_weight(x[:, c].astype(np.float64), fs)) for c in range(x.shape[1])], 1)      # (n, ch)
    short = n < blk
    if short: starts = [0]; ends = [n]
    else: starts = list(range(0, n - blk + 1, hop)); ends = [s + blk for s in starts]
    cs = np.vstack([np.zeros((1, zs.shape[1])), np.cumsum(zs, 0)])
    z = np.array([(cs[e] - cs[s]).sum() / (e - s) for s, e in zip(starts, ends)])       # channel-summed mean square per block (weights 1.0)
    with np.errstate(divide="ignore"): l = -0.691 + 10 * np.log10(z)
    mom = float(l.max()) if np.isfinite(l.max()) else None
    g1 = z[l > -70]
    if len(g1) == 0: return None, mom, short
    rel = -0.691 + 10 * math.log10(g1.mean()) - 10; g2 = z[(l > -70) & (l > rel)]
    if len(g2) == 0: return None, mom, short
    return float(-0.691 + 10 * math.log10(g2.mean())), mom, short


def true_peak_db(x, over=4):
    if x.size == 0: return -120.0
    best = 0.0
    for c in range(x.shape[1]):
        v = x[:, c].astype(np.float64); n = len(v); F = np.fft.rfft(v); G = np.zeros(n * over // 2 + 1, complex); k = min(len(F), len(G)); G[:k] = F[:k]
        best = max(best, float(np.abs(np.fft.irfft(G, n * over) * over).max()))
    return audio_tidy.db(best)


def measure(path):
    with __import__("wave").open(path, "rb") as wf: sw = wf.getsampwidth()
    x, sr = audio_tidy.read_wav(path); n, ch = x.shape
    ints, mom, short = lufs(x, sr)
    ax = np.abs(x); peak = float(ax.max()) if n else 0.0; rms = float(np.sqrt(np.mean(x.astype(np.float64) ** 2))) if n else 0.0
    loud = np.where(ax.max(1) > 10 ** (-60 / 20))[0]
    lead = (loud[0] / sr * 1000) if len(loud) else n / sr * 1000; trail = ((n - 1 - loud[-1]) / sr * 1000) if len(loud) else n / sr * 1000
    tp = true_peak_db(x)
    return {"file": path, "duration_s": round(n / sr, 3), "rate": sr, "channels": ch, "bits": sw * 8, "peak_db": round(audio_tidy.db(peak), 2), "true_peak_db": round(tp, 2),
            "rms_db": round(audio_tidy.db(rms), 2), "crest_db": round(audio_tidy.db(peak) - audio_tidy.db(rms), 2) if rms > 0 else 0.0,
            "dc_offset": round(float(np.abs(x.mean(0)).max()), 5) if n else 0.0, "clipped": int((ax >= 0.9999).sum()),
            "lead_silence_ms": round(float(lead)), "trail_silence_ms": round(float(trail)),
            "lufs": None if ints is None else round(ints, 2), "momentary_max_lufs": None if mom is None else round(mom, 2), "short": short, "silent": peak == 0.0}


def judge(m, target, tol, max_tp):
    flags = []
    if m["silent"]: flags.append("SILENT")
    if m["clipped"] > 0: flags.append("CLIPPED")
    if m["dc_offset"] > 0.01: flags.append("DC")
    if m["short"]: flags.append("SHORT")
    if m["true_peak_db"] > max_tp: flags.append("TP_OVER")
    gain = None
    if target is not None and m["lufs"] is not None:
        gain = round(target - m["lufs"], 2)
        if abs(gain) > tol: flags.append("OFF_TARGET")
        m["suggested_gain_db"] = round(min(gain, max_tp - m["true_peak_db"]), 2)
    m["target"] = target; m["flags"] = flags
    return not any(f in ("OFF_TARGET", "TP_OVER", "CLIPPED", "SILENT") for f in flags)


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p): out += sorted(glob.glob(os.path.join(p, "**", "*.wav"), recursive=True) + glob.glob(os.path.join(p, "**", "*.WAV"), recursive=True))
        else: out += sorted(glob.glob(p)) or [p]
    return list(dict.fromkeys(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Loudness (BS.1770) and technical report for WAV files, with CI exit code.")
    ap.add_argument("inputs", nargs="+", help="WAV files, globs or folders"); ap.add_argument("--target", type=float, help="target integrated loudness (LUFS)")
    ap.add_argument("--rule", action="append", default=[], help='per-path target, e.g. "music/*=-16" (matched on the path relative to the input folder); first match wins')
    ap.add_argument("--tolerance", type=float, default=1.0, help="allowed deviation in LU (default 1.0)"); ap.add_argument("--max-true-peak", type=float, default=-1.0)
    ap.add_argument("--csv"); ap.add_argument("--json"); ap.add_argument("--quiet", action="store_true")
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
    _src_keys = ('inputs',)
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

    rules = []
    for r in a.rule:
        if "=" not in r: sys.exit(f"bad --rule {r!r} (want pattern=LUFS)")
        pat, val = r.rsplit("=", 1); rules.append((pat, float(val)))
    roots = [p for p in a.inputs if os.path.isdir(p)]; files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    rows, bad = [], 0
    for f in files:
        try: m = measure(f)
        except Exception as e:
            print(f"ERR  {f}: {e}"); bad += 1; continue
        rel = os.path.relpath(f, roots[0]) if roots and os.path.commonpath([os.path.abspath(f), os.path.abspath(roots[0])]) == os.path.abspath(roots[0]) else os.path.basename(f)
        tgt = next((v for pat, v in rules if fnmatch.fnmatch(rel.replace(os.sep, "/"), pat)), a.target)
        ok = judge(m, tgt, a.tolerance, a.max_true_peak); m["ok"] = ok; rows.append(m); bad += 0 if ok else 1
        if not a.quiet:
            L = "-inf" if m["lufs"] is None else f"{m['lufs']:7.2f}"
            print(f"{'ok  ' if ok else 'FAIL'} {rel:<36} {L} LUFS  tp {m['true_peak_db']:6.2f}  rms {m['rms_db']:6.2f}  {m['duration_s']:6.2f}s  " + " ".join(m["flags"]) + (f"  gain {m['suggested_gain_db']:+.1f} dB" if "suggested_gain_db" in m else ""))
    print(f"{len(rows)} file(s) measured, {bad} failing")
    if a.csv and rows:
        cols = [k for k in rows[0] if k != "flags"] + ["flags"]
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows([dict(r, flags=" ".join(r["flags"])) for r in rows])
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
