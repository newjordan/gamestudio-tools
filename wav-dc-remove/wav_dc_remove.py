#!/usr/bin/env python3
"""wav-dc-remove: strip DC offset from PCM WAVs by subtracting each channel's mean, writing new files and a
before/after report (DC, peak). Inputs may be files or folders. The input path is never overwritten (pass --outdir
or --suffix). PCM only, via audio-tidy; other RIFF chunks are dropped.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402


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


def dc_of(x):
    return [float(x[:, c].mean()) for c in range(x.shape[1])]


def peak(x):
    return float(np.max(np.abs(x))) if len(x) else 0.0


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
        x, sr = audio_tidy.read_wav(f)
        before = dc_of(x)
        y = x - np.array(before, dtype=x.dtype)
        rec = {"file": f, "out": dest, "rate": sr, "channels": x.shape[1],
               "dc_before": [round(v, 8) for v in before], "dc_after": [round(v, 8) for v in dc_of(y)],
               "peak_before": round(peak(x), 6), "peak_after": round(peak(y), 6)}
        if not a.dry_run:
            audio_tidy.write_wav(dest, y, sr, bits=a.bits)
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
