#!/usr/bin/env python3
"""wav-gain: apply a fixed dB gain to a WAV (or a folder of WAVs). Optional
`--max-true-peak` caps the gain so the 4x-oversampled true peak stays under a
ceiling (the same uncertified meter as wav-batch-meta). `smpl` loop markers are
preserved. Writes next to the source with `--suffix` or under `--outdir`. The
input is never overwritten unless `--in-place`. PCM only, via audio-tidy.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx-normalize"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-batch-meta"))
import safe_out, audio_tidy, wav_loop_meta, sfx_normalize, wav_batch_meta  # noqa: E402


def process(path, dest, gain_db, max_tp, bits):
    x, sr = audio_tidy.read_wav(path)
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    gain = float(gain_db)
    status = "ok"
    tp_in = None
    if max_tp is not None:
        meas = wav_batch_meta.measure(path)
        tp_in = meas["true_peak_db"]
        headroom = max_tp - meas["true_peak_db"]
        if gain > headroom + 1e-9:
            gain = headroom
            status = "peak-capped"
    y = np.clip(x * (10.0 ** (gain / 20.0)), -1.0, 1.0)
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    audio_tidy.write_wav(dest, y, sr, bits=bits)
    if loops:
        lp = loops[0]
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), lp["start"], lp["end"])
        open(dest, "wb").write(patched)
    rec = {"file": path, "out": dest, "gain_db": round(gain, 4), "requested_db": gain_db,
           "status": status, "true_peak_in_db": tp_in,
           "loop": ({"start": loops[0]["start"], "end": loops[0]["end"]} if loops else None)}
    if max_tp is not None:
        after = wav_batch_meta.measure(dest)
        rec["true_peak_out_db"] = after["true_peak_db"]
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply a fixed dB gain to PCM WAV files, with an optional true-peak cap.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--gain", type=float, required=True, help="gain in dB (negative to attenuate)")
    ap.add_argument("-o", "--out", help="output WAV (single file) or directory")
    ap.add_argument("--outdir")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--max-true-peak", type=float, default=None,
                    help="optional true-peak ceiling in dBTP (uncertified 4x-oversampled meter)")
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    paths = sfx_normalize.collect(a.inputs)
    if len(paths) > 1 and a.out and a.out.lower().endswith(".wav"):
        sys.exit("-o as a WAV path is only valid for a single input; use --outdir")
    if not a.outdir and a.suffix == "" and not a.out and not a.in_place:
        sys.exit("pass --outdir, --suffix, -o, or --in-place so inputs are not overwritten")
    out_file = a.out if (a.out and len(paths) == 1 and a.out.lower().endswith(".wav")) else None
    if a.out and not out_file and not a.outdir:
        a.outdir = a.out
    recs = []
    for p in paths:
        dest = sfx_normalize.dest_of(p, a.outdir, a.suffix, out_file)
        safe_out.check(p, dest, a.in_place)
        if a.json:
            safe_out.check(p, a.json, a.in_place)
        recs.append(process(p, dest, a.gain, a.max_true_peak, a.bits))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs, "gain_db": a.gain, "max_true_peak": a.max_true_peak}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} file(s) gained {a.gain:g} dB")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
