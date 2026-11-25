#!/usr/bin/env python3
"""wav-chan-swap: swap or reorder channels in a multi-channel WAV. `--swap` flips the
first two channels (typical stereo L/R). `--order` is a comma list of 0-based indices
or of labels L,R,C,LFE,Ls,Rs,Lb,Rb (same names as wav-chan-split). `smpl` loop markers
are preserved. Writes `-o` or `--suffix` / `--outdir`. The input is never overwritten
unless `--in-place`. PCM only, via audio-tidy.
"""
import argparse, os, json, sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-chan-split"))
import safe_out, audio_tidy, wav_loop_meta, wav_chan_split  # noqa: E402


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


def parse_order(spec, nchans):
    labels = wav_chan_split.names_for(nchans, None)
    parts = [s.strip() for s in spec.split(",") if s.strip()]
    if len(parts) != nchans:
        raise SystemExit(f"--order has {len(parts)} entry(ies) but the file has {nchans} channel(s)")
    idx = []
    for p in parts:
        if p.isdigit() or (p.startswith("-") and p[1:].isdigit()):
            i = int(p)
        else:
            up = p if p in labels else p.upper()
            # names_for uses L/R/C/... ; also accept lowercase
            cmap = {lab.upper(): i for i, lab in enumerate(labels)}
            cmap.update({lab: i for i, lab in enumerate(labels)})
            if up not in cmap and p not in cmap:
                raise SystemExit(f"unknown channel {p!r} (want indices or {','.join(labels)})")
            i = cmap.get(up, cmap.get(p))
        if i < 0 or i >= nchans:
            raise SystemExit(f"channel index {i} out of range 0..{nchans - 1}")
        idx.append(i)
    if sorted(idx) != list(range(nchans)):
        raise SystemExit(f"--order must be a permutation of 0..{nchans - 1} (got {idx})")
    return idx


def dest_of(src, outdir, suffix, out_file):
    if out_file:
        return out_file
    stem, ext = os.path.splitext(os.path.basename(src))
    name = f"{stem}{suffix}{ext}"
    return os.path.join(outdir or os.path.dirname(os.path.abspath(src)), name)


def process(path, dest, order_spec, do_swap, bits):
    x, sr = audio_tidy.read_wav(path)
    if x.ndim == 1:
        x = x[:, None]
    n = x.shape[1]
    if do_swap:
        if n < 2:
            raise SystemExit(f"{path}: --swap needs at least 2 channels")
        order = [1, 0] + list(range(2, n))
    else:
        order = parse_order(order_spec, n)
    y = x[:, order]
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    os.makedirs(os.path.dirname(os.path.abspath(dest)) or ".", exist_ok=True)
    audio_tidy.write_wav(dest, y, sr, bits=bits)
    if loops:
        lp = loops[0]
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), lp["start"], lp["end"])
        open(dest, "wb").write(patched)
    return {"file": path, "out": dest, "rate": sr, "channels": n, "order": order}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Swap or reorder channels in a multi-channel WAV.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", help="output WAV (single file) or an outdir")
    ap.add_argument("--outdir")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--swap", action="store_true", help="swap the first two channels (stereo L/R)")
    ap.add_argument("--order", help="comma list of indices or labels (L,R,C,...)")
    ap.add_argument("--bits", type=int, default=16)
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if bool(a.swap) == bool(a.order):
        sys.exit("pass exactly one of --swap or --order")
    paths = collect(a.inputs)
    if len(paths) > 1 and a.out and a.out.lower().endswith(".wav"):
        sys.exit("-o as a WAV path is only valid for a single input; use --outdir")
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
        recs.append(process(p, dest, a.order, a.swap, a.bits))
    if a.json:
        json.dump({"files": recs}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} file(s) reordered")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
