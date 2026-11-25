#!/usr/bin/env python3
"""wav-chan-split: split a multi-channel WAV into mono stems (default names L/R, or 5.1 / 7.1, or --names) plus a
cue/index JSON or CSV, and optionally interleave mono stems back into one multi-channel WAV (--join). Inputs may be
files or folders. Stems are written under --outdir (or next to the source with --suffix). The input path is never
overwritten. PCM only, via audio-tidy.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402

DEFAULT = {1: ["M"], 2: ["L", "R"], 3: ["L", "R", "C"], 4: ["L", "R", "Ls", "Rs"],
           5: ["L", "R", "C", "Ls", "Rs"], 6: ["L", "R", "C", "LFE", "Ls", "Rs"],
           8: ["L", "R", "C", "LFE", "Ls", "Rs", "Lb", "Rb"]}


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


def names_for(n, custom):
    if custom:
        names = [s.strip() for s in custom.split(",") if s.strip()]
        if len(names) != n:
            raise SystemExit(f"--names has {len(names)} label(s) but the file has {n} channel(s)")
        return names
    if n in DEFAULT: return list(DEFAULT[n])
    return [f"ch{i:02d}" for i in range(n)]


def stem_path(src, outdir, suffix, label):
    stem, ext = os.path.splitext(os.path.basename(src))
    name = f"{stem}{suffix}_{label}{ext}"
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def split_one(path, outdir, suffix, custom, bits, dry):
    x, sr = audio_tidy.read_wav(path)
    labels = names_for(x.shape[1], custom)
    rec = {"file": path, "rate": sr, "channels": x.shape[1], "frames": len(x),
           "duration_s": round(len(x) / sr, 3), "stems": []}
    if outdir and not dry: os.makedirs(outdir, exist_ok=True)
    for i, lab in enumerate(labels):
        dest = stem_path(path, outdir, suffix, lab)
        if os.path.abspath(dest) == os.path.abspath(path) and not a.in_place:
            raise SystemExit(f"refusing to overwrite the input: {dest}")
        if not dry:
            audio_tidy.write_wav(dest, x[:, i:i + 1], sr, bits=bits)
        rec["stems"].append({"channel": i, "name": lab, "out": dest})
    return rec


def join_files(paths, out, names, bits):
    if os.path.abspath(out) in {os.path.abspath(p) for p in paths}:
        sys.exit("refusing to overwrite an input; pick a different -o or pass --in-place")
    loaded = [audio_tidy.read_wav(p) for p in paths]
    srs = {sr for _, sr in loaded}
    if len(srs) != 1: sys.exit("join: all stems must share the same sample rate")
    sr = loaded[0][1]
    lens = {len(x) for x, _ in loaded}
    if len(lens) != 1: sys.exit("join: all stems must have the same length")
    cols = []
    for x, _ in loaded:
        if x.ndim == 1: x = x[:, None]
        if x.shape[1] != 1:
            sys.exit("join: each input must be mono (a multi-channel file would be ambiguous)")
        cols.append(x[:, 0])
    y = np.stack(cols, axis=1)
    os.makedirs(os.path.dirname(os.path.abspath(out)) or ".", exist_ok=True)
    audio_tidy.write_wav(out, y, sr, bits=bits)
    labels = names_for(y.shape[1], names)
    rec = {"out": out, "rate": sr, "channels": y.shape[1], "frames": len(y),
           "duration_s": round(len(y) / sr, 3), "names": labels,
           "sources": list(paths)}
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Split a multi-channel WAV into mono stems, or interleave stems back.")
    ap.add_argument("inputs", nargs="*")
    ap.add_argument("-o", "--outdir", help="directory for stems (split) or unused with --join")
    ap.add_argument("--join", metavar="OUT", help="interleave the input mono WAVs into this multi-channel WAV")
    ap.add_argument("--suffix", default="", help="inserted before _L.wav etc.")
    ap.add_argument("--names", help="comma-separated channel labels (must match channel count)")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32), default=16)
    ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.join:
        files = collect(a.inputs)
        if len(files) < 2: sys.exit("join needs at least two mono WAVs")
        rec = join_files(files, a.join, a.names, a.bits)
        print(f"joined {rec['channels']} channel(s), {rec['duration_s']}s -> {a.join}")
        rows = [rec]
    else:
        files = collect(a.inputs)
        if not files: sys.exit("no WAV files found")
        if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
            sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
        rows = []
        for f in files:
            rec = split_one(f, a.outdir, a.suffix, a.names, a.bits, a.dry_run)
            rows.append(rec)
            print(f"{os.path.basename(f)}: {rec['channels']} ch -> " + ", ".join(s["name"] for s in rec["stems"]))
    if a.json: json.dump(rows if a.join is None else rows, open(a.json, "w"), indent=1)
    if a.csv:
        flat = []
        for r in rows:
            if "stems" in r:
                for s in r["stems"]:
                    flat.append({"file": r["file"], "rate": r["rate"], "channel": s["channel"], "name": s["name"], "out": s["out"]})
            else:
                flat.append({"file": ",".join(r["sources"]), "rate": r["rate"], "channel": r["channels"], "name": ",".join(r["names"]), "out": r["out"]})
        if flat:
            w = csv.DictWriter(open(a.csv, "w", newline=""), fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
