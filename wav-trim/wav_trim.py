#!/usr/bin/env python3
"""wav-trim: trim leading and trailing silence from WAV files, write trimmed copies plus a before/after report.
Uses the same peak-threshold rule as wav-batch-meta (default --thresh-db -60) and an optional pad of kept silence
(--pad-ms, default 10). Mid-file silences are left alone. A fully silent file is not written (status silent) unless
--keep-silent (writes a pad-length of silence). Inputs may be files or folders. The input path is never overwritten
(write to --outdir, or to a sibling with --suffix). PCM only, via audio-tidy (16/24/32-bit out).
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402

# wav-batch-meta uses 10 ** (-60/20) to flag "loud" samples when measuring lead/trail silence.
DEFAULT_THRESH = -60.0


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p):
            out.extend(sorted(os.path.join(p, f) for f in os.listdir(p) if f.lower().endswith(".wav")))
        elif p.lower().endswith(".wav"):
            out.append(p)
        else:
            raise SystemExit(f"not a WAV or folder: {p}")
    return out


def dest_for(src, outdir, suffix):
    name = os.path.basename(src)
    if suffix:
        stem, ext = os.path.splitext(name); name = stem + suffix + ext
    if outdir: return os.path.join(outdir, name)
    return os.path.join(os.path.dirname(os.path.abspath(src)), name)


def trim_one(path, thresh_db, pad_ms, keep_silent, bits):
    x, sr = audio_tidy.read_wav(path)
    n = len(x)
    y = audio_tidy.trim_silence(x, sr, thresh_db=thresh_db, pad_ms=pad_ms)
    if len(y) == 0:
        status = "silent"
        if keep_silent:
            pad = max(1, int(sr * pad_ms / 1000)); y = np.zeros((pad, x.shape[1]), dtype=x.dtype)
        else:
            y = None
    else:
        status = "trimmed" if len(y) < n else "unchanged"
    lead = trail = n / sr * 1000
    th = 10 ** (thresh_db / 20)
    loud = np.where(np.abs(x).max(axis=1) > th)[0]
    if loud.size:
        lead = loud[0] / sr * 1000; trail = (n - 1 - loud[-1]) / sr * 1000
    rec = {"file": path, "status": status, "rate": sr, "channels": x.shape[1],
           "before_s": round(n / sr, 3), "after_s": None if y is None else round(len(y) / sr, 3),
           "lead_silence_ms": round(float(lead)), "trail_silence_ms": round(float(trail)),
           "trimmed_ms": None if y is None else round((n - len(y)) / sr * 1000), "out": None}
    return rec, y, sr, bits or None


def main(argv=None):
    ap = argparse.ArgumentParser(description="Trim leading and trailing silence from WAV files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir"); ap.add_argument("--suffix", default="", help="filename suffix when --outdir is omitted (e.g. _trim)")
    ap.add_argument("--thresh-db", type=float, default=DEFAULT_THRESH, help="peak threshold in dBFS (default -60, same as wav-batch-meta)")
    ap.add_argument("--pad-ms", type=float, default=10); ap.add_argument("--keep-silent", action="store_true")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32)); ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--fail-on-silent", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
        sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
    if a.outdir and not a.dry_run: os.makedirs(a.outdir, exist_ok=True)
    rows = []
    for f in files:
        # keep source bit depth if --bits omitted
        import wave
        with wave.open(f, "rb") as wf: src_bits = wf.getsampwidth() * 8
        rec, y, sr, _ = trim_one(f, a.thresh_db, a.pad_ms, a.keep_silent, a.bits)
        dest = dest_for(f, a.outdir, a.suffix)
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place and not a.dry_run:
            sys.exit(f"refusing to overwrite input {f}; pass --outdir or --suffix or pass --in-place")
        if y is not None and not a.dry_run:
            audio_tidy.write_wav(dest, y, sr, bits=a.bits or (src_bits if src_bits in (16, 24, 32) else 16))
            rec["out"] = dest
        elif y is not None:
            rec["out"] = dest
        rows.append(rec)
        print(f"{os.path.basename(f)}: {rec['status']} {rec['before_s']}s -> {rec['after_s'] if rec['after_s'] is not None else '-'}s "
              f"(lead {rec['lead_silence_ms']} ms, trail {rec['trail_silence_ms']} ms)" + (f" -> {rec['out']}" if rec.get("out") else ""))
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv:
        cols = ["file", "status", "before_s", "after_s", "lead_silence_ms", "trail_silence_ms", "trimmed_ms", "out"]
        with open(a.csv, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    silent = sum(r["status"] == "silent" for r in rows)
    print(f"{len(rows)} file(s), {silent} silent")
    return 1 if a.fail_on_silent and silent else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
