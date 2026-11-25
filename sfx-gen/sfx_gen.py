#!/usr/bin/env python3
"""sfx-gen: sfxr-style retro sound-effect generator (coin, jump, laser, explosion, hit, powerup, blip).

Clean-room re-implementation of the sfxr parameter model (DrPetter's sfxr, MIT-licensed) in numpy.
Seeded, so a seed + preset is a reproducible sound; batch mode writes variations for A/B picks.
"""
import argparse, json, os, wave
import numpy as np
import os, sys

SR = 44100


def preset(kind, rng):
    r = rng.uniform
    p = dict(wave="square", freq=440.0, slide=0.0, attack=0.0, sustain=0.1, decay=0.2,
             duty=0.5, vib_depth=0.0, vib_speed=0.0, arp_mult=1.0, arp_time=0.0, lpf=1.0, volume=0.5)
    if kind == "coin":
        p.update(freq=r(700, 1200), sustain=r(0.02, 0.08), decay=r(0.15, 0.3), arp_mult=r(1.3, 1.6), arp_time=r(0.04, 0.09))
    elif kind == "jump":
        p.update(freq=r(250, 500), slide=r(0.5, 1.5), sustain=r(0.05, 0.12), decay=r(0.1, 0.25), duty=r(0.2, 0.5))
    elif kind == "laser":
        p.update(wave=rng.choice(["square", "saw", "sine"]), freq=r(800, 2000), slide=r(-3.0, -1.2), sustain=r(0.05, 0.15), decay=r(0.05, 0.2))
    elif kind == "explosion":
        p.update(wave="noise", freq=r(60, 200), slide=r(-0.6, 0.0), sustain=r(0.1, 0.3), decay=r(0.3, 0.7), lpf=r(0.2, 0.6))
    elif kind == "hit":
        p.update(wave=rng.choice(["noise", "saw", "square"]), freq=r(150, 500), slide=r(-2.0, -0.5), sustain=r(0.0, 0.05), decay=r(0.05, 0.15))
    elif kind == "powerup":
        p.update(freq=r(300, 600), slide=r(0.6, 1.4), sustain=r(0.1, 0.3), decay=r(0.2, 0.4), vib_depth=r(0.0, 0.15), vib_speed=r(8, 20))
    elif kind == "blip":
        p.update(wave=rng.choice(["square", "sine"]), freq=r(600, 1200), sustain=r(0.02, 0.06), decay=r(0.03, 0.08))
    else:
        raise SystemExit(f"unknown preset {kind}")
    return p


def synth(p, seed=0):
    rng = np.random.default_rng(seed)
    n = int((p["attack"] + p["sustain"] + p["decay"]) * SR) + 1
    t = np.arange(n) / SR
    # frequency curve: exponential slide (octaves per second) + vibrato + arpeggio jump
    f = p["freq"] * 2.0 ** (p["slide"] * t)
    if p["vib_depth"]:
        f *= 1 + p["vib_depth"] * np.sin(2 * np.pi * p["vib_speed"] * t)
    if p["arp_time"]:
        f = np.where(t >= p["arp_time"], f * p["arp_mult"], f)
    f = np.clip(f, 20, SR / 2 - 1)
    phase = np.cumsum(f / SR) % 1.0
    w = p["wave"]
    if w == "square":
        s = np.where(phase < p["duty"], 1.0, -1.0)
    elif w == "saw":
        s = 2 * phase - 1
    elif w == "sine":
        s = np.sin(2 * np.pi * phase)
    elif w == "noise":
        # sample-and-hold noise, re-rolled each wave cycle (like sfxr)
        cyc = np.floor(np.cumsum(f / SR) * 2).astype(int)
        vals = rng.uniform(-1, 1, cyc.max() + 2)
        s = vals[cyc]
    else:
        raise ValueError(w)
    if p["lpf"] < 1.0:
        a = p["lpf"]
        out = np.empty_like(s)
        acc = 0.0
        for i, v in enumerate(s):
            acc += a * (v - acc)
            out[i] = acc
        s = out
    env = np.ones(n)
    na, ns = int(p["attack"] * SR), int(p["sustain"] * SR)
    if na:
        env[:na] = np.linspace(0, 1, na)
    env[na + ns:] = np.linspace(1, 0, n - na - ns) ** 2
    return (s * env * p["volume"]).astype(np.float32)


def write_wav(path, x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate retro SFX WAVs.")
    ap.add_argument("preset", choices=["coin", "jump", "laser", "explosion", "hit", "powerup", "blip"])
    ap.add_argument("-o", "--outdir", default="sfx")
    ap.add_argument("-n", "--count", type=int, default=1, help="number of variations")
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    os.makedirs(a.outdir, exist_ok=True)
    meta = []
    for i in range(a.count):
        s = a.seed + i
        p = preset(a.preset, np.random.default_rng(s))
        x = synth(p, s)
        name = f"{a.preset}_{s:04d}.wav"
        write_wav(os.path.join(a.outdir, name), x)
        meta.append({"file": name, "seed": s, "params": p})
    json.dump(meta, open(os.path.join(a.outdir, f"{a.preset}_params.json"), "w"), indent=1)
    print(f"wrote {a.count} {a.preset} sfx to {a.outdir}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
