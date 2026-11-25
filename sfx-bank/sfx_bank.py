#!/usr/bin/env python3
"""sfx-bank: pack many short WAVs into one WAV "audio sprite" plus an index, and unpack them again. One file means one
request on the web and one decode on mobile. pack: clips are converted to a common sample rate (the highest, unless --rate)
and channel count (--mono forces mono), separated by --gap seconds of silence so encoders do not smear one clip into the next.
The index lists start/end in frames and seconds per clip, and --howler writes the Howler.js `sprite` map ({name: [offset_ms,
duration_ms]}; add loop flags by hand). unpack: cuts the clips back out by the index. Lossless 16-bit PCM; encode the bank with
audio-convert afterwards (keep the gap larger than the encoder delay, e.g. 0.05 s).
"""
import argparse, os, glob, json, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


def pack(paths, rate=None, mono=False, gap=0.05):
    clips = []
    for p in paths:
        x, sr = audio_tidy.read_wav(p); clips.append((os.path.splitext(os.path.basename(p))[0], x, sr))
    if not clips: raise SystemExit("no WAV files")
    names = [c[0] for c in clips]
    if len(set(names)) != len(names): raise SystemExit("duplicate clip names: " + ", ".join(sorted({n for n in names if names.count(n) > 1})))
    sr = rate or max(c[2] for c in clips); ch = 1 if mono else max(c[1].shape[1] for c in clips); parts, index, pos = [], {}, 0
    gap_n = int(round(gap * sr)); silence = np.zeros((gap_n, ch), np.float32)
    for name, x, s in clips:
        if mono and x.shape[1] > 1: x = x.mean(1, keepdims=True)
        elif x.shape[1] < ch: x = np.repeat(x, ch, axis=1)
        elif x.shape[1] > ch: x = x[:, :ch]
        if s != sr: x = audio_tidy.resample(x, s, sr)
        x = x.reshape(len(x), -1)
        index[name] = {"start": pos, "end": pos + len(x), "start_s": round(pos / sr, 6), "end_s": round((pos + len(x)) / sr, 6)}
        parts += [x, silence]; pos += len(x) + gap_n
    return np.concatenate(parts), sr, index


def howler(index):
    return {"sprite": {n: [int(round(v["start_s"] * 1000)), int(round((v["end_s"] - v["start_s"]) * 1000))] for n, v in index.items()}}


def unpack(wav, index, outdir):
    x, sr = audio_tidy.read_wav(wav); os.makedirs(outdir, exist_ok=True)
    for n, v in index.items():
        if v["end"] > len(x): raise SystemExit(f"{n}: index points past the end of the WAV")
        audio_tidy.write_wav(os.path.join(outdir, n + ".wav"), x[v["start"]:v["end"]], sr)
    return len(index)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Audio sprite bank.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pack"); p.add_argument("inputs", nargs="+"); p.add_argument("-o", "--out", required=True, help="basename: writes .wav and .json")
    p.add_argument("--rate", type=int); p.add_argument("--mono", action="store_true"); p.add_argument("--gap", type=float, default=0.05); p.add_argument("--howler", action="store_true")
    u = sub.add_parser("unpack"); u.add_argument("wav"); u.add_argument("index"); u.add_argument("-o", "--outdir", required=True)
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
    _src_keys = ('inputs', 'wav', 'index')
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

    if a.cmd == "pack":
        files = [f for pat in a.inputs for f in (sorted(glob.glob(os.path.join(pat, "*.wav"))) if os.path.isdir(pat) else (sorted(glob.glob(pat)) or [pat]))]
        x, sr, idx = pack(files, a.rate, a.mono, a.gap); audio_tidy.write_wav(a.out + ".wav", x, sr)
        json.dump({"sample_rate": sr, "channels": x.shape[1], "frames": len(x), "clips": idx}, open(a.out + ".json", "w"), indent=1)
        if a.howler: json.dump(howler(idx), open(a.out + ".howler.json", "w"), indent=1)
        print(f"{len(idx)} clip(s), {len(x) / sr:.2f}s, {sr} Hz, {x.shape[1]} ch -> {a.out}.wav/.json"); return 0
    meta = json.load(open(a.index)); print(f"{unpack(a.wav, meta['clips'], a.outdir)} clip(s) -> {a.outdir}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
