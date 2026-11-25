#!/usr/bin/env python3
"""sfx-normalize: peak-normalise a WAV (or a folder of WAVs) to a target peak dBFS
(default -1.0), or, with `--lufs`, to a target integrated LUFS capped so the true
peak stays under `--max-true-peak`. LUFS / true-peak use wav-batch-meta's meter
(ITU-R BS.1770-4, 4x-oversampled true peak, not certified). Silent files are left
unchanged and reported. `smpl` loop markers are preserved. Writes next to the source
with `--suffix` or under `--outdir`. The input is never overwritten unless
`--in-place`. PCM only, via audio-tidy.
"""
import argparse, os, json, math, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-batch-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loud-apply"))
import safe_out, audio_tidy, wav_loop_meta, wav_batch_meta, wav_loud_apply  # noqa: E402


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(".wav")))
        elif p.lower().endswith(".wav"):
            out.append(p)
        else:
            raise SystemExit(f"not a WAV or folder: {p}")
    if not out:
        raise SystemExit("no WAV files found")
    return out


def peak_dbfs(x):
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    if peak <= 0:
        return None, 0.0
    return 20.0 * math.log10(peak), peak


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    name = f"{stem}{suffix}{ext}"
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def _write(dest, y, sr, bits, loops):
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    audio_tidy.write_wav(dest, y, sr, bits=bits)
    if loops:
        lp = loops[0]
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), lp["start"], lp["end"])
        open(dest, "wb").write(patched)


def process(path, dest, target, bits):
    x, sr = audio_tidy.read_wav(path)
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    db, peak = peak_dbfs(x)
    rec = {"file": path, "out": dest, "rate": sr, "peak_in_dbfs": None if db is None else round(db, 4),
           "target_dbfs": target, "gain_db": 0.0, "status": "ok", "mode": "peak"}
    if db is None:
        rec["status"] = "silent"
        y = x
    else:
        gain_db = target - db
        rec["gain_db"] = round(gain_db, 4)
        y = x * (10.0 ** (gain_db / 20.0))
        # clip safety for a 0 dBFS target with rounding
        y = np.clip(y, -1.0, 1.0)
    _write(dest, y, sr, bits, loops)
    db2, _ = peak_dbfs(y)
    rec["peak_out_dbfs"] = None if db2 is None else round(db2, 4)
    return rec


def process_lufs(path, dest, target, max_true_peak, bits):
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    meas = wav_batch_meta.measure(path)
    rec = {"file": path, "out": dest, "rate": meas["rate"], "mode": "lufs",
           "lufs_in": meas["lufs"], "true_peak_in_db": meas["true_peak_db"],
           "target_lufs": target, "max_true_peak": max_true_peak,
           "short": meas["short"], "gain_db": 0.0, "status": "ok"}
    if meas.get("silent"):
        rec["status"] = "silent"
        x, sr = audio_tidy.read_wav(path)
        _write(dest, x, sr, bits, loops)
        rec["lufs_out"] = meas["lufs"]
        rec["true_peak_out_db"] = meas["true_peak_db"]
        return rec
    if meas["lufs"] is None:
        rec["status"] = "no-lufs"
        x, sr = audio_tidy.read_wav(path)
        _write(dest, x, sr, bits, loops)
        rec["lufs_out"] = None
        rec["true_peak_out_db"] = meas["true_peak_db"]
        return rec
    gain, status = wav_loud_apply.planned_gain(meas, target, max_true_peak)
    rec["gain_db"] = gain
    rec["status"] = status
    x, sr = audio_tidy.read_wav(path)
    y = np.clip(x * (10 ** (gain / 20)), -1, 1)
    _write(dest, y, sr, bits, loops)
    after = wav_batch_meta.measure(dest)
    rec["lufs_out"] = after["lufs"]
    rec["true_peak_out_db"] = after["true_peak_db"]
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Peak-normalise WAV files to a target peak dBFS, or to LUFS with a true-peak cap.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", help="output WAV (single file) or ignored when many inputs")
    ap.add_argument("--outdir", help="directory for outputs (default: next to each source, with --suffix)")
    ap.add_argument("--suffix", default="", help="filename suffix when writing next to the source")
    ap.add_argument("--peak", type=float, default=-1.0, help="target sample peak dBFS (default: -1.0; ignored when --lufs is set)")
    ap.add_argument("--lufs", type=float, default=None,
                    help="target integrated LUFS (uses the wav-batch-meta meter, capped by --max-true-peak)")
    ap.add_argument("--max-true-peak", type=float, default=-1.0,
                    help="true-peak ceiling in dBTP when --lufs is set (default: -1.0)")
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    paths = collect(a.inputs)
    if len(paths) > 1 and a.out and a.out.lower().endswith(".wav"):
        sys.exit(" -o as a WAV path is only valid for a single input; use --outdir")
    if not a.outdir and a.suffix == "" and not a.out and not a.in_place:
        sys.exit("pass --outdir, --suffix, -o, or --in-place so inputs are not overwritten")
    out_file = a.out if (a.out and len(paths) == 1 and a.out.lower().endswith(".wav")) else None
    if a.out and not out_file and not a.outdir:
        a.outdir = a.out
    recs = []
    for p in paths:
        dest = dest_of(p, a.outdir, a.suffix, out_file)
        safe_out.check(p, dest, a.in_place)
        if a.json:
            safe_out.check(p, a.json, a.in_place)
        if a.lufs is not None:
            recs.append(process_lufs(p, dest, a.lufs, a.max_true_peak, a.bits))
        else:
            recs.append(process(p, dest, a.peak, a.bits))
    report = {"files": recs, "mode": "lufs" if a.lufs is not None else "peak",
              "target_dbfs": None if a.lufs is not None else a.peak,
              "target_lufs": a.lufs, "max_true_peak": a.max_true_peak if a.lufs is not None else None}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(report, open(a.json, "w"), indent=2)
    if a.lufs is not None:
        print(f"{len(recs)} file(s) loudness-normalised to {a.lufs:g} LUFS (true-peak cap {a.max_true_peak:g} dBTP)")
    else:
        print(f"{len(recs)} file(s) peak-normalised to {a.peak:g} dBFS")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
