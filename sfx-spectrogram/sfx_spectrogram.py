#!/usr/bin/env python3
"""sfx-spectrogram: spectrogram PNG of a WAV for eyeballing clicks, clipping, noise floors and cut-off tails, with a
waveform strip underneath (clipped columns in red). Prints and optionally writes JSON with clipped ranges
(runs of >= 3 samples at or above 0.999 full scale) and silent ranges (below --silence dBFS for >= 0.1 s).
STFT: Hann window, n_fft 1024 by default, 0 dB = loudest bin, --range dB shown, --log for a log frequency axis. Mixes channels to mono. numpy only.
"""
import argparse, os, json, sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402

STOPS = [(0.0, (0, 0, 4)), (0.2, (50, 10, 90)), (0.4, (150, 30, 90)), (0.6, (230, 80, 40)), (0.8, (250, 190, 40)), (1.0, (252, 255, 210))]


def cmap(v):
    v = np.clip(v, 0, 1); xs = [s[0] for s in STOPS]
    return np.stack([np.interp(v, xs, [s[1][c] for s in STOPS]) for c in range(3)], -1).astype(np.uint8)


def stft_db(x, n_fft=1024, hop=None):
    hop = hop or n_fft // 4
    if len(x) < n_fft: x = np.pad(x, (0, n_fft - len(x)))
    win = np.hanning(n_fft); n = 1 + (len(x) - n_fft) // hop
    idx = np.arange(n_fft)[None, :] + hop * np.arange(n)[:, None]
    mag = np.abs(np.fft.rfft(x[idx] * win, axis=1)) / (n_fft / 4)
    return 20 * np.log10(np.maximum(mag, 1e-9)).T                       # (freq bins, frames)


def runs(mask, min_len):
    d = np.diff(np.concatenate([[0], mask.astype(np.int8), [0]])); s, e = np.where(d == 1)[0], np.where(d == -1)[0]
    return [(int(a), int(b)) for a, b in zip(s, e) if b - a >= min_len]


def analyse(x, sr, silence_db=-60.0):
    clip = [(round(a / sr, 4), round(b / sr, 4)) for a, b in runs(np.abs(x) >= 0.999, 3)]
    win = max(1, int(sr * 0.01)); n = len(x) // win
    rms = np.sqrt((x[:n * win].reshape(n, win) ** 2).mean(1)) if n else np.zeros(1)
    quiet = [(round(a * win / sr, 3), round(b * win / sr, 3)) for a, b in runs(20 * np.log10(np.maximum(rms, 1e-9)) < silence_db, 10)]
    return {"seconds": round(len(x) / sr, 3), "sample_rate": sr, "peak": round(float(np.abs(x).max()), 4), "clipped_ranges_s": clip, "silent_ranges_s": quiet}


def render(x, sr, width=800, height=256, n_fft=1024, db_range=90.0, max_freq=None, wave_h=64, log=False):
    S = stft_db(x, n_fft, max(1, (len(x) - n_fft) // max(width - 1, 1)) if len(x) > n_fft else None)
    if max_freq: S = S[: max(2, int(max_freq / (sr / 2) * S.shape[0]))]
    S = (np.clip(S - S.max(), -db_range, 0) + db_range) / db_range
    if log:                                                     # log frequency axis from ~40 Hz: music and speech fill the picture
        top = max_freq or sr / 2; nb = S.shape[0]; f = np.geomspace(40, top, height); pos = np.clip(f / top * (nb - 1), 0, nb - 1)
        S = np.stack([np.interp(pos, np.arange(nb), S[:, c]) for c in range(S.shape[1])], 1)
    spec = Image.fromarray(cmap(S[::-1]), "RGB").resize((width, height), Image.BILINEAR)
    wave = np.zeros((wave_h, width, 3), np.uint8); seg = np.array_split(np.arange(len(x)), width)
    for c, ix in enumerate(seg):
        if len(ix) == 0: continue
        lo, hi = x[ix].min(), x[ix].max(); y0, y1 = int((1 - (hi + 1) / 2) * (wave_h - 1)), int((1 - (lo + 1) / 2) * (wave_h - 1))
        wave[y0:y1 + 1, c] = (255, 40, 40) if np.abs(x[ix]).max() >= 0.999 else (120, 200, 255)
    out = Image.new("RGB", (width, height + wave_h)); out.paste(spec, (0, 0)); out.paste(Image.fromarray(wave, "RGB"), (0, height)); return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="WAV spectrogram PNG + clipping / silence report.")
    ap.add_argument("wav", nargs="+"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("--width", type=int, default=800); ap.add_argument("--height", type=int, default=256)
    ap.add_argument("--n-fft", type=int, default=1024); ap.add_argument("--range", type=float, default=90.0); ap.add_argument("--max-freq", type=float); ap.add_argument("--silence", type=float, default=-60.0)
    ap.add_argument("--log", action="store_true", help="log frequency axis"); ap.add_argument("--json"); ap.add_argument("--fail-on-clip", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); os.makedirs(a.outdir, exist_ok=True); rep = {}; rc = 0
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
    _src_keys = ('wav',)
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

    for f in a.wav:
        x, sr = audio_tidy.read_wav(f); x = x.mean(1)
        if len(x) == 0: print(f"{f}: empty"); continue
        r = analyse(x, sr, a.silence); rep[os.path.basename(f)] = r
        render(x, sr, a.width, a.height, a.n_fft, a.range, a.max_freq, log=a.log).save(os.path.join(a.outdir, os.path.splitext(os.path.basename(f))[0] + "_spec.png"))
        print(f"{f}: {r['seconds']}s peak {r['peak']}" + (f", CLIPPED at {r['clipped_ranges_s'][:3]}" if r["clipped_ranges_s"] else "") + (f", silent {r['silent_ranges_s'][:3]}" if r["silent_ranges_s"] else ""))
        if r["clipped_ranges_s"] and a.fail_on_clip: rc = 1
    if a.json: json.dump(rep, open(a.json, "w"), indent=1)
    return rc


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
