#!/usr/bin/env python3
"""wav-gap-squeeze: shrink interior silences longer than --min-ms down to --cap-ms (dialogue cleanup). Leading and
trailing silence is left alone (use wav-trim for those). A fully silent file is refused unless --keep-silent. Inputs
may be files or folders. The input path is never overwritten. PCM only, via audio-tidy; other RIFF chunks are dropped.
"""
import argparse, os, csv, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
import audio_tidy  # noqa: E402

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
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def silence_runs(loud, n):
    """Return inclusive (start, end) index spans of interior silence (not leading/trailing)."""
    if n == 0: return []
    silent = np.ones(n, bool)
    silent[loud] = False
    # leading
    lead = 0
    while lead < n and silent[lead]: lead += 1
    trail = n
    while trail > lead and silent[trail - 1]: trail -= 1
    runs = []
    i = lead
    while i < trail:
        if not silent[i]:
            i += 1; continue
        j = i
        while j < trail and silent[j]: j += 1
        runs.append((i, j))  # [i, j)
        i = j
    return runs


def squeeze(x, sr, thresh_db, min_ms, cap_ms):
    n, ch = len(x), x.shape[1]
    th = 10 ** (thresh_db / 20)
    loud = np.where(np.max(np.abs(x), axis=1) > th)[0]
    if loud.size == 0:
        return None, {"status": "silent", "before_s": round(n / sr, 3), "after_s": None, "squeezed_ms": 0, "gaps": 0}
    min_n = max(1, int(round(sr * min_ms / 1000)))
    cap_n = max(0, int(round(sr * cap_ms / 1000)))
    runs = [(a, b) for a, b in silence_runs(loud, n) if (b - a) >= min_n]
    if not runs:
        return x.copy(), {"status": "unchanged", "before_s": round(n / sr, 3), "after_s": round(n / sr, 3),
                          "squeezed_ms": 0, "gaps": 0}
    parts = []
    cursor = 0
    removed = 0
    for a, b in runs:
        parts.append(x[cursor:a])
        keep = cap_n
        mid = a + (b - a) // 2
        # keep a slice centred in the gap, length cap_n
        if keep == 0:
            removed += (b - a)
        else:
            start = max(a, mid - keep // 2)
            end = min(b, start + keep)
            start = max(a, end - keep)
            parts.append(x[start:end])
            removed += (b - a) - (end - start)
        cursor = b
    parts.append(x[cursor:])
    y = np.concatenate(parts, axis=0) if parts else x[:0]
    return y, {"status": "squeezed", "before_s": round(n / sr, 3), "after_s": round(len(y) / sr, 3),
               "squeezed_ms": round(removed / sr * 1000), "gaps": len(runs)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Shrink long interior silences in WAV files down to a cap.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir"); ap.add_argument("--suffix", default="")
    ap.add_argument("--thresh-db", type=float, default=DEFAULT_THRESH)
    ap.add_argument("--min-ms", type=float, default=400, help="only squeeze gaps at least this long")
    ap.add_argument("--cap-ms", type=float, default=150, help="keep this much of each squeezed gap")
    ap.add_argument("--keep-silent", action="store_true")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32), default=16)
    ap.add_argument("--json"); ap.add_argument("--csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.cap_ms < 0 or a.min_ms < 0: sys.exit("--min-ms and --cap-ms must be >= 0")
    files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    if not a.outdir and not a.suffix and not a.dry_run and not a.in_place:
        sys.exit("refusing to overwrite inputs; pass --outdir or --suffix (or --dry-run)")
    if a.outdir and not a.dry_run: os.makedirs(a.outdir, exist_ok=True)
    rows = []
    for f in files:
        dest = dest_for(f, a.outdir, a.suffix)
        if os.path.abspath(dest) == os.path.abspath(f) and not a.in_place:
            sys.exit(f"refusing to overwrite the input: {dest} or pass --in-place")
        x, sr = audio_tidy.read_wav(f)
        y, rec = squeeze(x, sr, a.thresh_db, a.min_ms, a.cap_ms)
        rec.update({"file": f, "out": dest, "rate": sr, "channels": x.shape[1]})
        if rec["status"] == "silent" and not a.keep_silent:
            rec["out"] = None
            rows.append(rec)
            print(f"{os.path.basename(f)}: silent (skipped)")
            continue
        if rec["status"] == "silent" and a.keep_silent:
            pad = max(1, int(sr * a.cap_ms / 1000)); y = np.zeros((pad, x.shape[1]), dtype=x.dtype)
            rec["after_s"] = round(len(y) / sr, 3)
        if not a.dry_run and y is not None:
            audio_tidy.write_wav(dest, y, sr, bits=a.bits)
        rows.append(rec)
        print(f"{os.path.basename(f)}: {rec['status']} {rec['before_s']}s -> {rec['after_s']}s ({rec['squeezed_ms']} ms, {rec['gaps']} gap(s))")
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv and rows:
        w = csv.DictWriter(open(a.csv, "w", newline=""), fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
