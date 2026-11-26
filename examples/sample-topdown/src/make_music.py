#!/usr/bin/env python3
"""Write the sfx-mix recipe for Ember Crypt's music loop.

The score is data: an 8-bar A-minor riff at 120 bpm (16 s), three voices built
from sfx-gen one-shots that build.sh renders first (blip for the lead and bass,
a trimmed, pitched-down explosion for the kick, a high-passed hit for the hat).
sfx-mix does the mixing; wav-loop-snap cuts the result to exactly 16 s and
writes the smpl loop that Godot imports.
"""
import argparse, json

BPM = 120
STEP_MS = 60000 / BPM / 4          # sixteenth note
BAR = 16
# lead: (step, semitones relative to the blip's own pitch); A minor pentatonic-ish
LEAD = [0, None, 3, None, 7, None, 3, 5, 7, None, 10, None, 7, 5, 3, None]
LEAD_B = [0, None, 3, None, 7, 8, 7, 5, 3, None, 0, None, -2, None, 0, None]
BASS_ROOTS = [-24, -24, -19, -21, -24, -24, -17, -19]  # one root per bar


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--blip", default="blip.wav")
    ap.add_argument("--kick", default="kick.wav")
    ap.add_argument("--hat", default="hat.wav")
    a = ap.parse_args()
    layers = []
    for bar in range(8):
        base = bar * BAR
        riff = LEAD if bar % 2 == 0 else LEAD_B
        lift = 2 if bar in (4, 5) else 0
        for i, semi in enumerate(riff):
            if semi is None:
                continue
            layers.append({"file": a.blip, "offset_ms": round((base + i) * STEP_MS, 2),
                           "pitch_semitones": semi + lift, "gain_db": -9, "fade_out_ms": 20, "pan": -0.15})
        root = BASS_ROOTS[bar]
        for i in (0, 3, 6, 8, 11, 14):
            layers.append({"file": a.blip, "offset_ms": round((base + i) * STEP_MS, 2),
                           "pitch_semitones": root + (12 if i in (6, 14) else 0), "gain_db": -6,
                           "lowpass_hz": 900, "fade_out_ms": 30, "pan": 0.1})
        for i in (0, 8):
            layers.append({"file": a.kick, "offset_ms": round((base + i) * STEP_MS, 2), "gain_db": -3})
        for i in range(2, 16, 4):
            layers.append({"file": a.hat, "offset_ms": round((base + i) * STEP_MS, 2), "gain_db": -16,
                           "highpass_hz": 4000, "pan": 0.3})
    recipe = {"sample_rate": 44100, "channels": 2, "peak_db": -1.0, "tail_ms": 400, "layers": layers}
    json.dump(recipe, open(a.out, "w"), indent=1)
    print(f"{len(layers)} layers, {8 * BAR * STEP_MS / 1000:.1f} s -> {a.out}")


if __name__ == "__main__":
    main()
