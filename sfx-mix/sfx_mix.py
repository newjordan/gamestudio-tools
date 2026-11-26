#!/usr/bin/env python3
"""sfx-mix: layer several WAV files into one sound effect from a JSON recipe (the way a sound designer stacks a click, a thump and a
sparkle). Recipe:
  {"sample_rate": 44100, "channels": 2, "tail_ms": 0, "master_gain_db": 0, "peak_db": -1, "normalize": false, "soft_clip": false,
   "layers": [{"file": "thump.wav", "offset_ms": 0, "gain_db": -3, "pitch_semitones": -5, "reverse": false, "trim_ms": 400,
               "fade_in_ms": 2, "fade_out_ms": 60, "lowpass_hz": 3000, "highpass_hz": 80, "pan": -0.3}, ...]}
File names are relative to the recipe. Pitch is a resample (speed and pitch move together, linear interpolation); filters are first-order
(6 dB/octave); pan (-1 left .. +1 right, constant power with the centre at unity gain) is for mono sources. Output channels default to the widest
layer (max 2), or stereo when any layer has a pan. Peak handling: the mix is scaled down to --peak_db when it is louder; "normalize": true scales it up to peak_db as well;
"soft_clip": true rounds the peaks with tanh before the final check. Prints a timeline; --dry-run writes nothing. PCM WAV in, 16/24/32-bit out.
"""
import argparse, os, json, math, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402

KNOWN = {"file", "offset_ms", "gain_db", "pitch_semitones", "reverse", "trim_ms", "fade_in_ms", "fade_out_ms", "lowpass_hz", "highpass_hz", "pan"}


def one_pole(x, sr, fc, high=False):
    """First-order low/high-pass via the frequency response on a zero-padded FFT (equals running the filter, no SciPy needed)."""
    n = len(x); m = 1 << int(math.ceil(math.log2(n + sr + 1))); f = np.fft.rfftfreq(m, 1 / sr); H = 1 / (1 + 1j * f / fc)
    if high: H = 1 - H
    return np.fft.irfft(np.fft.rfft(x, m, axis=0) * H[:, None], m, axis=0)[:n]


def prepare_layer(L, base, sr):
    x, rate = audio_tidy.read_wav(os.path.join(base, L["file"])); x = audio_tidy.resample(x, rate, sr).astype(np.float64)
    if L.get("reverse"): x = x[::-1]
    st = float(L.get("pitch_semitones", 0))
    if st:
        r = 2 ** (st / 12); n = max(1, int(round(len(x) / r))); t = np.arange(n) * r
        x = np.stack([np.interp(t, np.arange(len(x)), x[:, c]) for c in range(x.shape[1])], 1)
    if L.get("trim_ms") is not None: x = x[: int(round(sr * L["trim_ms"] / 1000))]
    if L.get("highpass_hz"): x = one_pole(x, sr, float(L["highpass_hz"]), high=True)
    if L.get("lowpass_hz"): x = one_pole(x, sr, float(L["lowpass_hz"]))
    n = len(x); fi = min(n, int(round(sr * L.get("fade_in_ms", 0) / 1000))); fo = min(n, int(round(sr * L.get("fade_out_ms", 0) / 1000)))
    if fi: x[:fi] *= np.linspace(0, 1, fi, endpoint=False)[:, None]
    if fo: x[n - fo:] *= np.linspace(1, 0, fo, endpoint=False)[:, None]
    x = x * 10 ** (float(L.get("gain_db", 0)) / 20)
    return x


def to_channels(x, ch, pan=None):
    if x.shape[1] == ch: return x
    if x.shape[1] == 1 and ch == 2:
        if pan is None: return np.repeat(x, 2, 1)
        p = (max(-1.0, min(1.0, float(pan))) + 1) * math.pi / 4; return np.concatenate([x * math.sqrt(2) * math.cos(p), x * math.sqrt(2) * math.sin(p)], 1)
    if ch == 1: return x.mean(1, keepdims=True)
    return x[:, :ch]


def mix(recipe, base="."):
    sr = int(recipe.get("sample_rate", 44100)); layers = recipe.get("layers") or []
    if not layers: raise SystemExit("recipe has no layers")
    prepared = []
    for i, L in enumerate(layers):
        bad = set(L) - KNOWN
        if bad: raise SystemExit(f"layer {i}: unknown key(s) {sorted(bad)} (known: {sorted(KNOWN)})")
        if "file" not in L: raise SystemExit(f"layer {i} has no 'file'")
        prepared.append(prepare_layer(L, base, sr))
    ch = int(recipe.get("channels") or (2 if any("pan" in L for L in layers) else min(2, max(p.shape[1] for p in prepared))))
    ends = [int(round(sr * L.get("offset_ms", 0) / 1000)) + len(p) for L, p in zip(layers, prepared)]
    total = max(ends) + int(round(sr * recipe.get("tail_ms", 0) / 1000)); out = np.zeros((total, ch)); timeline = []
    for L, p in zip(layers, prepared):
        o = int(round(sr * L.get("offset_ms", 0) / 1000)); out[o:o + len(p)] += to_channels(p, ch, L.get("pan") if "pan" in L else None)
        timeline.append({"file": L["file"], "start_ms": round(o / sr * 1000, 1), "end_ms": round((o + len(p)) / sr * 1000, 1), "peak_db": round(audio_tidy.db(float(np.abs(p).max())), 1)})
    out *= 10 ** (recipe.get("master_gain_db", 0) / 20)
    if recipe.get("soft_clip"): out = np.tanh(out)
    peak = float(np.abs(out).max()); target = 10 ** (recipe.get("peak_db", -1.0) / 20); scale = 1.0
    if peak > 0 and (peak > target or recipe.get("normalize")): scale = target / peak; out *= scale
    return out, sr, {"timeline": timeline, "duration_s": round(total / sr, 3), "channels": ch, "scale_db": round(20 * math.log10(scale), 2), "peak_db": round(audio_tidy.db(float(np.abs(out).max())), 2)}


_HELP = """\
Recipe keys (JSON object):
  sample_rate   output rate (default 44100)
  channels      1 or 2 (default: widest layer, or 2 if any layer sets pan)
  tail_ms       silence appended after the last layer (default 0)
  master_gain_db  gain applied to the sum before the peak stage (default 0)
  peak_db       peak ceiling in dBFS (default -1). The mix is scaled down when
                it is louder than this and left alone when it is quieter.
  normalize     false (default) or true. true also scales a quieter mix up so
                the peak lands on peak_db. Omit it and peak_db is only a ceiling.
  soft_clip     false (default) or true. true applies tanh before the peak stage.
  layers        list of layer objects. Each layer:
                  file (required, path relative to the recipe),
                  offset_ms, gain_db, pitch_semitones, reverse,
                  trim_ms, fade_in_ms, fade_out_ms, lowpass_hz, highpass_hz, pan
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Mix WAV layers into one SFX from a JSON recipe.",
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=_HELP)
    ap.add_argument("recipe"); ap.add_argument("-o", "--out"); ap.add_argument("--bits", type=int, choices=[16, 24, 32], default=16); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.recipe) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    try: recipe = json.load(open(a.recipe))
    except (OSError, json.JSONDecodeError) as e: sys.exit(f"cannot read recipe {a.recipe}: {e}")
    out, sr, rep = mix(recipe, os.path.dirname(os.path.abspath(a.recipe)))
    for t in rep["timeline"]: print(f"  {t['start_ms']:8.1f} - {t['end_ms']:8.1f} ms  {t['file']}  (peak {t['peak_db']} dBFS)")
    print(f"{len(rep['timeline'])} layer(s), {rep['duration_s']} s, {rep['channels']} ch, mix scaled {rep['scale_db']:+.2f} dB, final peak {rep['peak_db']} dBFS")
    if a.dry_run: return 0
    if not a.out: sys.exit("give -o OUT.wav (or --dry-run)")
    audio_tidy.write_wav(a.out, out, sr, a.bits); print(f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
