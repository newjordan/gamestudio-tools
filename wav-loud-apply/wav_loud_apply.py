#!/usr/bin/env python3
"""wav-loud-apply: apply a gain so a WAV hits a target integrated LUFS, capped so the true peak stays under a ceiling.
Uses wav-batch-meta's meter (ITU-R BS.1770-4, not certified) to measure, then a uniform gain. Files shorter than
400 ms use the same un-gated whole-file reading and are flagged short. Does not overwrite inputs (needs --outdir or
--suffix). --dry-run reports the planned gain only. PCM 16/24/32-bit out via audio-tidy.
"""
import argparse, os, csv, json, sys, wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-batch-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-trim"))
import audio_tidy, wav_batch_meta, wav_trim  # noqa: E402


def planned_gain(meas, target, max_true_peak):
    if meas["lufs"] is None: return 0.0, "no-lufs"
    need = target - meas["lufs"]
    # cap so true_peak + gain <= max_true_peak
    headroom = max_true_peak - meas["true_peak_db"]
    gain = min(need, headroom)
    status = "ok"
    if gain + 1e-6 < need: status = "peak-capped"
    return round(gain, 3), status


def main(argv=None):
    ap = argparse.ArgumentParser(description="Apply gain to hit a LUFS target, capped by true peak.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir"); ap.add_argument("--suffix", default="")
    ap.add_argument("--target", type=float, default=-16.0, help="target integrated LUFS (default -16)")
    ap.add_argument("--max-true-peak", type=float, default=-1.0)
    ap.add_argument("--bits", type=int, choices=(16, 24, 32))
    ap.add_argument("--json"); ap.add_argument("--csv"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = wav_trim.collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
        sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
    if a.outdir and not a.dry_run: os.makedirs(a.outdir, exist_ok=True)
    rows = []
    for f in files:
        meas = wav_batch_meta.measure(f)
        gain, status = planned_gain(meas, a.target, a.max_true_peak)
        dest = wav_trim.dest_for(f, a.outdir, a.suffix)
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place and not a.dry_run:
            sys.exit(f"refusing to overwrite input {f} or pass --in-place")
        rec = {"file": f, "lufs": meas["lufs"], "true_peak_db": meas["true_peak_db"], "short": meas["short"],
               "target": a.target, "gain_db": gain, "status": status, "out": None, "out_lufs": None}
        if not a.dry_run:
            x, sr = audio_tidy.read_wav(f)
            y = np.clip(x * (10 ** (gain / 20)), -1, 1)
            with wave.open(f, "rb") as wf: src_bits = wf.getsampwidth() * 8
            audio_tidy.write_wav(dest, y, sr, bits=a.bits or (src_bits if src_bits in (16, 24, 32) else 16))
            after = wav_batch_meta.measure(dest)
            rec["out"] = dest; rec["out_lufs"] = after["lufs"]; rec["out_true_peak_db"] = after["true_peak_db"]
        rows.append(rec)
        print(f"{os.path.basename(f)}: LUFS {meas['lufs']} peak {meas['true_peak_db']} dB, gain {gain:+.2f} dB ({status})"
              + (f" -> LUFS {rec['out_lufs']}" if rec.get("out_lufs") is not None else ""))
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv:
        cols = ["file", "lufs", "true_peak_db", "target", "gain_db", "status", "out_lufs", "out"]
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    print(f"{len(rows)} file(s)")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
