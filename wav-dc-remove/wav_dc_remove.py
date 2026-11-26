#!/usr/bin/env python3
"""wav-dc-remove: strip DC offset from PCM WAVs by subtracting each channel's mean, writing new files and a
before/after report (DC, peak). Inputs may be files or folders. The input path is never overwritten (pass --outdir
or --suffix). The mean is subtracted in integer PCM, so a file whose mean
already rounds to 0 is copied bit-exact. Other RIFF chunks are dropped.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import pcm_frames  # noqa: E402


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
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Strip DC offset from PCM WAV files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir"); ap.add_argument("--suffix", default="")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32), default=16)
    ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
        sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
    if a.outdir and not a.dry_run: os.makedirs(a.outdir, exist_ok=True)
    rows = []
    for f in files:
        dest = dest_for(f, a.outdir, a.suffix)
        if not a.dry_run and os.path.abspath(dest) == os.path.abspath(f):
            sys.exit(f"refusing to overwrite the input: {dest} or pass --in-place")
        samples, sr, src_bits = pcm_frames.read_frames(f)
        full = float(1 << ((src_bits if src_bits in (8, 16, 24, 32) else 16) - 1))
        means = samples.astype(np.float64).mean(axis=0) if len(samples) else np.zeros(samples.shape[1])
        before = [float(m / full) for m in means]
        offsets = np.rint(means).astype(np.int64)
        y = samples - offsets
        after_means = y.astype(np.float64).mean(axis=0) if len(y) else means
        after = [float(m / full) for m in after_means]
        written, out_bits = pcm_frames.to_bits(y, src_bits, a.bits)
        rec = {"file": f, "out": dest, "rate": sr, "channels": int(samples.shape[1]),
               "dc_before": [round(v, 8) for v in before], "dc_after": [round(v, 8) for v in after],
               "peak_before": round(float(np.max(np.abs(samples)) / full) if len(samples) else 0.0, 6),
               "peak_after": round(float(np.max(np.abs(y)) / full) if len(y) else 0.0, 6)}
        if not a.dry_run:
            pcm_frames.write_frames(dest, written, sr, out_bits)
        rows.append(rec)
        print(f"{os.path.basename(f)}: DC {rec['dc_before']} -> {rec['dc_after']}")
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv and rows:
        # flatten dc lists
        flat = []
        for r in rows:
            f = dict(r)
            f["dc_before"] = ",".join(str(v) for v in r["dc_before"])
            f["dc_after"] = ",".join(str(v) for v in r["dc_after"])
            flat.append(f)
        w = csv.DictWriter(open(a.csv, "w", newline=""), fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
