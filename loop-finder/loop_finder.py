#!/usr/bin/env python3
"""loop-finder: find a seamless loop region in music/ambience WAVs, then optionally render a crossfaded
loop or print engine loop points (samples and seconds; Godot loop_begin/loop_end).

Method: the audio *after* the loop end should continue like the audio *after* the loop start. For several
candidate end points near the tail, normalised cross-correlation (FFT) against the head finds the best
matching start; both are snapped to the nearest rising zero crossing. Score 0..1 (1 = identical continuation).
Scores are quantized to 4 decimal places before ranking, so FFT rounding cannot change the winner.
Tied scores take the earliest start, then the shortest loop. CPU only; no models.
Typical use: MiniMax Music exports that start with an intro and fade at the end.
"""
import argparse, json, os, wave
import numpy as np
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def read_wav(path):
    raw, ch, sw, sr, n = gst_read.read_wav_frames(path)
    if sw == 2:
        x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    elif sw == 4:
        x = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648
    elif sw == 1:
        x = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128
    else:
        raise GstInputError("WAV unsupported sample width %s" % sw)
    if ch < 1 or x.size % ch != 0:
        raise GstInputError("WAV data length is not a multiple of sample width")
    return x.reshape(-1, ch), sr


def write_wav(path, x, sr):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(x.shape[1]); wf.setsampwidth(2); wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


# Ranking ignores anything past 4 decimal places, which is also how the score is printed.
SCORE_DECIMALS = 4
_SCORE_SCALE = 10 ** SCORE_DECIMALS


def quantize_score(score):
    """Integer rank key. Values that print as the same 4-decimal score compare equal."""
    return int(np.round(float(score) * _SCORE_SCALE))


def pick_candidate(cands):
    """Choose (score, start, length). Highest quantized score, then earliest start, then shortest length.

    `cands` is an iterable of (score, start, length). Returns (quantized, start, length, score)
    or None when there is nothing to rank.
    """
    best = None
    for score, start, length in cands:
        q = quantize_score(score)
        if best is None or q > best[0] or (q == best[0] and (start < best[1] or (start == best[1] and length < best[2]))):
            best = (q, int(start), int(length), float(score))
    return best


def zero_cross(m, i, radius):
    lo, hi = max(1, i - radius), min(len(m) - 1, i + radius)
    cand = np.where((m[lo - 1:hi - 1] <= 0) & (m[lo:hi] > 0))[0]
    if cand.size == 0:
        return i
    return int(lo + cand[np.argmin(np.abs(cand + lo - i))])


def find_loop(x, sr, window_s=0.5, min_len_s=2.0, tail_s=None, head_frac=0.5, candidates=24):
    m = x.mean(axis=1).astype(np.float64)
    n = len(m)
    W = int(window_s * sr)
    if n < W * 4:
        raise SystemExit("clip too short for loop search")
    tail = int((tail_s if tail_s else n / sr * 0.25) * sr)
    head = m[: int(n * head_frac)]
    ends = np.linspace(n - W - tail, n - W, candidates).astype(int)
    csum = np.concatenate([[0], np.cumsum(head ** 2)])
    energy = csum[W:] - csum[:-W]                      # sliding energy of head windows
    L = len(head) - W + 1
    rad = int(0.01 * sr)
    ranked = []
    for e in ends:
        e = int(e)
        ref = m[e:e + W]
        re = float(np.sum(ref ** 2))
        if re < 1e-9:
            continue
        size = 1 << int(np.ceil(np.log2(len(head) + W)))
        cc = np.fft.irfft(np.fft.rfft(head, size) * np.conj(np.fft.rfft(ref, size)), size)[:L]
        score = cc / np.sqrt(np.maximum(energy[:L], 1e-12) * re)
        lim = np.arange(L) <= e - int(min_len_s * sr)
        score = np.where(lim, score, -2.0)
        # Quantize first so a 1-ulp FFT difference cannot move the peak, then take the earliest start.
        qscore = np.round(score * _SCORE_SCALE)
        s = int(np.argmax(qscore))
        if float(score[s]) <= -2.0:
            continue
        s2, e2 = zero_cross(m, s, rad), zero_cross(m, e, rad)
        ranked.append((float(score[s]), s2, e2 - s2))
    chosen = pick_candidate(ranked)
    if chosen is None:
        score, s2, e2 = -2.0, zero_cross(m, 0, rad), zero_cross(m, 0, rad)
    else:
        score, s2, e2 = chosen[3], chosen[1], chosen[1] + chosen[2]
    return {"start": s2, "end": e2, "score": round(score, 4), "sr": sr,
            "start_s": round(s2 / sr, 4), "end_s": round(e2 / sr, 4), "length_s": round((e2 - s2) / sr, 4)}


def render_loop(x, loop, fade_ms=40):
    s, e, sr = loop["start"], loop["end"], loop["sr"]
    seg = x[s:e].copy()
    nf = min(int(sr * fade_ms / 1000), len(seg) // 4, len(x) - e)
    if nf > 0:
        ramp = np.linspace(0, 1, nf)[:, None]
        seg[-nf:] = seg[-nf:] * (1 - ramp) + x[e:e + nf] * ramp   # tail blends into the audio that follows the end
    return seg


def main(argv=None):
    ap = argparse.ArgumentParser(description="Find seamless loop points in WAV music.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", help="write crossfaded loop WAVs here")
    ap.add_argument("--json", help="write loop points JSON")
    ap.add_argument("--window", type=float, default=0.5, help="match window seconds")
    ap.add_argument("--min-length", type=float, default=2.0)
    ap.add_argument("--fade-ms", type=float, default=40)
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

    res = {}
    for f in a.inputs:
        x, sr = read_wav(f)
        lp = find_loop(x, sr, a.window, a.min_length)
        res[os.path.basename(f)] = lp
        print(f"{f}: loop {lp['start_s']}s -> {lp['end_s']}s ({lp['length_s']}s) score {lp['score']}  "
              f"[godot loop_begin={lp['start']} loop_end={lp['end']}]")
        if a.outdir:
            os.makedirs(a.outdir, exist_ok=True)
            write_wav(os.path.join(a.outdir, os.path.splitext(os.path.basename(f))[0] + "_loop.wav"), render_loop(x, lp, a.fade_ms), sr)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
