#!/usr/bin/env python3
"""Reed Causeway music: a 4-bar reed motif at 120 bpm, or the loop span of a mix.

The score is an sfx-mix recipe (mono, 22050 Hz, 1.6 s of tail past the notes).
`--span FILE` prints the inclusive smpl loop `start end` used by loop-xfade and
wav-loop-snap: half a second of pre-roll, then exactly 8 seconds.
"""
import argparse, json, wave

BPM = 120
STEP_MS = 60000 / BPM / 4
BAR = 16
LEAD = [0, None, 3, None, 7, None, 5, 3, 7, None, 10, None, 7, 5, 3, None]
BASS = [-24, -19, -21, -17]


def recipe(blip, kick, hat):
    layers = []
    for bar in range(4):
        base = bar * BAR
        for i, semi in enumerate(LEAD):
            if semi is None:
                continue
            layers.append({"file": blip, "offset_ms": round((base + i) * STEP_MS, 2),
                           "pitch_semitones": semi + (2 if bar >= 2 else 0), "gain_db": -10,
                           "fade_out_ms": 30})
        root = BASS[bar]
        for i in (0, 6, 8, 14):
            layers.append({"file": blip, "offset_ms": round((base + i) * STEP_MS, 2),
                           "pitch_semitones": root, "gain_db": -6, "lowpass_hz": 800, "fade_out_ms": 40})
        for i in (0, 8):
            layers.append({"file": kick, "offset_ms": round((base + i) * STEP_MS, 2), "gain_db": -4})
        for i in range(2, 16, 4):
            layers.append({"file": hat, "offset_ms": round((base + i) * STEP_MS, 2),
                           "gain_db": -16, "highpass_hz": 3500})
    return {"sample_rate": 22050, "channels": 1, "peak_db": -1.0, "tail_ms": 1600, "layers": layers}


def span(path):
    with wave.open(path, "rb") as wf:
        sr = wf.getframerate()
        n = wf.getnframes()
    start = sr // 2
    end = start + 8 * sr - 1
    if end >= n:
        raise SystemExit("music is %d frames at %d Hz; the 8 s loop needs an end of %d" % (n, sr, end))
    print("%d %d" % (start, end))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", help="recipe JSON")
    ap.add_argument("--blip", default="blip.wav")
    ap.add_argument("--kick", default="kick.wav")
    ap.add_argument("--hat", default="hat.wav")
    ap.add_argument("--span", help="print start end for this WAV")
    a = ap.parse_args()
    if a.span:
        span(a.span)
        return
    if not a.out:
        raise SystemExit("pass -o or --span")
    doc = recipe(a.blip, a.kick, a.hat)
    json.dump(doc, open(a.out, "w"), indent=1)
    print("%d layers, 8.0 s of notes -> %s" % (len(doc["layers"]), a.out))


if __name__ == "__main__":
    main()
