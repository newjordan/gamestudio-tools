#!/usr/bin/env python3
"""audio-concat: stitch WAV files into one review reel (voice-over sessions, music beds, variation sets) with optional
gaps and a cue list. Files are taken in the order given, or in natural order from a folder. Every file is resampled to
--rate (default: the first file's rate) and mixed to --channels (default: the widest input, max 2). --gap-ms of silence
is inserted between files; --slate-ms of silence plus a short marker beep can be placed before each file so an editor can
see the cuts. The mix is scaled so the peak stays at or under --peak-db. Writes the WAV, a cue CSV/JSON (file, start_s,
end_s) and, with --cues-wav, a sidecar list in the same order. PCM WAV in; 16/24/32-bit out.
"""
import argparse, os, csv, glob, json, re, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


def natural(s): return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p): out += sorted(glob.glob(os.path.join(p, "*.wav")) + glob.glob(os.path.join(p, "*.WAV")), key=natural)
        else: out += [p]
    if not out: raise SystemExit("no WAV files found")
    return out


def to_ch(x, ch):
    if x.shape[1] == ch: return x
    if ch == 1: return x.mean(1, keepdims=True)
    if x.shape[1] == 1: return np.repeat(x, ch, 1)
    return x[:, :ch]


def beep(sr, ch, ms=40, freq=1000, amp=0.3):
    n = max(1, int(round(sr * ms / 1000))); t = np.arange(n) / sr
    env = np.sin(np.pi * np.arange(n) / max(n - 1, 1))
    return np.repeat((amp * env * np.sin(2 * np.pi * freq * t))[:, None], ch, 1)


def concat(paths, rate=None, channels=None, gap_ms=0, slate_ms=0, peak_db=-1.0):
    loaded = [(p, *audio_tidy.read_wav(p)) for p in paths]
    sr = rate or loaded[0][2]; ch = channels or min(2, max(x.shape[1] for _, x, _ in loaded))
    gap = np.zeros((int(round(sr * gap_ms / 1000)), ch)) if gap_ms else None
    parts, cues, t = [], [], 0.0
    for i, (p, x, r) in enumerate(loaded):
        x = to_ch(audio_tidy.resample(x, r, sr).astype(np.float64), ch)
        if slate_ms:
            sl = np.zeros((int(round(sr * slate_ms / 1000)), ch)); parts.append(np.concatenate([sl, beep(sr, ch)], 0) if len(sl) else beep(sr, ch))
            t += (len(sl) + int(round(sr * 0.04))) / sr
        if i and gap is not None: parts.append(gap); t += len(gap) / sr
        start = t; parts.append(x); t += len(x) / sr
        cues.append({"file": p, "rel": os.path.basename(p), "start_s": round(start, 4), "end_s": round(t, 4), "duration_s": round(len(x) / sr, 4)})
    out = np.concatenate(parts, 0) if parts else np.zeros((0, ch))
    peak = float(np.abs(out).max()) if out.size else 0; target = 10 ** (peak_db / 20); scale = (target / peak) if peak > target and peak > 0 else 1.0
    return out * scale, sr, cues, {"scale_db": round(20 * np.log10(scale), 2) if scale != 1 else 0.0, "duration_s": round(len(out) / sr, 3) if sr else 0, "channels": ch, "rate": sr}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Concatenate WAV files into one reel with a cue list.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--rate", type=int); ap.add_argument("--channels", type=int, choices=[1, 2])
    ap.add_argument("--gap-ms", type=float, default=0); ap.add_argument("--slate-ms", type=float, default=0)
    ap.add_argument("--peak-db", type=float, default=-1.0); ap.add_argument("--bits", type=int, choices=[16, 24, 32], default=16)
    ap.add_argument("--cues"); ap.add_argument("--cues-json")
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

    y, sr, cues, info = concat(collect(a.inputs), a.rate, a.channels, a.gap_ms, a.slate_ms, a.peak_db)
    audio_tidy.write_wav(a.out, y, sr, a.bits)
    dest = a.cues or os.path.splitext(a.out)[0] + ".cues.csv"
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["rel", "start_s", "end_s", "duration_s", "file"]); w.writeheader(); w.writerows(cues)
    if a.cues_json: json.dump(cues, open(a.cues_json, "w"), indent=1)
    print(f"{len(cues)} file(s), {info['duration_s']} s, {info['channels']} ch @ {info['rate']} Hz, scale {info['scale_db']:+.2f} dB -> {a.out}")
    print(f"cues -> {dest}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
