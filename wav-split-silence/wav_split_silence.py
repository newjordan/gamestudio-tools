#!/usr/bin/env python3
"""wav-split-silence: split a long recording (a VO take, a field recording, a music impro) into separate WAV files at
silences. A run of samples whose peak stays under --thresh-db for at least --min-silence-ms is a cut point. Each kept
region is padded by --pad-ms of the original audio (or silence if the file ends) and dropped if it is shorter than
--min-keep-ms. Writes numbered files (<out>/<prefix>_0001.wav) plus a cue CSV/JSON (index, start_s, end_s, file).
PCM WAV; output bit depth matches the input (16/24/32). This is an editor's first pass, not a sentence segmenter:
breaths and short pauses shorter than --min-silence-ms stay inside a region.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


def regions(x, sr, thresh_db=-40, min_silence_ms=300, min_keep_ms=80, pad_ms=50):
    th = 10 ** (thresh_db / 20); loud = np.abs(x).max(axis=1) > th
    # runs of loud / silent
    min_sil = int(round(sr * min_silence_ms / 1000)); min_keep = int(round(sr * min_keep_ms / 1000)); pad = int(round(sr * pad_ms / 1000))
    n = len(x); cuts = []
    i = 0
    while i < n:
        if not loud[i]:
            i += 1; continue
        j = i
        while j < n and loud[j]: j += 1
        # extend over short silences (shorter than min_sil) so they don't split
        while True:
            k = j
            while k < n and not loud[k]: k += 1
            if k < n and (k - j) < min_sil:
                j = k
                while j < n and loud[j]: j += 1
                continue
            break
        if (j - i) >= min_keep: cuts.append((max(0, i - pad), min(n, j + pad)))
        i = j
    return cuts


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a WAV into regions separated by silence.")
    ap.add_argument("wav"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("--prefix", default="take")
    ap.add_argument("--thresh-db", type=float, default=-40); ap.add_argument("--min-silence-ms", type=float, default=300)
    ap.add_argument("--min-keep-ms", type=float, default=80); ap.add_argument("--pad-ms", type=float, default=50)
    ap.add_argument("--bits", type=int, choices=[16, 24, 32]); ap.add_argument("--cues"); ap.add_argument("--json")
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

    x, sr = audio_tidy.read_wav(a.wav)
    bits = a.bits or (wave_bits(a.wav))
    cuts = regions(x, sr, a.thresh_db, a.min_silence_ms, a.min_keep_ms, a.pad_ms)
    if not cuts: sys.exit("no audible regions found (try a higher --thresh-db or a shorter --min-keep-ms)")
    os.makedirs(a.outdir, exist_ok=True); cues = []
    for i, (s, e) in enumerate(cuts, 1):
        name = f"{a.prefix}_{i:04d}.wav"; audio_tidy.write_wav(os.path.join(a.outdir, name), x[s:e], sr, bits)
        cues.append({"index": i, "file": name, "start_s": round(s / sr, 4), "end_s": round(e / sr, 4), "duration_s": round((e - s) / sr, 4)})
        print(f"{name}: {cues[-1]['start_s']:.2f}-{cues[-1]['end_s']:.2f}s ({cues[-1]['duration_s']:.2f}s)")
    dest = a.cues or os.path.join(a.outdir, "cues.csv")
    with open(dest, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["index", "file", "start_s", "end_s", "duration_s"]); w.writeheader(); w.writerows(cues)
    if a.json: json.dump(cues, open(a.json, "w"), indent=1)
    print(f"{len(cues)} region(s) from {a.wav} -> {a.outdir}")
    return 0


def wave_bits(path):
    import wave
    with wave.open(path, "rb") as w: return w.getsampwidth() * 8


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
