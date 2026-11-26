#!/usr/bin/env python3
"""wav-invert: invert the polarity of a WAV (or a folder of WAVs) by multiplying
samples by -1. Samples are negated as integers, so a same-width file is bit-exact
except the most-negative code, which saturates (it has no positive twin). `smpl`
loop markers are preserved. Writes next to the source with `--suffix` or under
`--outdir`. The input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sfx-normalize"))
import safe_out, wav_loop_meta, sfx_normalize, pcm_frames  # noqa: E402


def process(path, dest, bits):
    samples, sr, src_bits = pcm_frames.read_frames(path)
    raw = open(path, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    y = pcm_frames.negate(samples, src_bits if src_bits in (8, 16, 24, 32) else 16)
    y, bits = pcm_frames.to_bits(y, src_bits, bits)
    pcm_frames.write_frames(dest, y, sr, bits)
    if loops:
        lp = loops[0]
        patched = wav_loop_meta.set_loop(open(dest, "rb").read(), lp["start"], lp["end"])
        open(dest, "wb").write(patched)
    return {"file": path, "out": dest, "rate": sr, "frames": int(len(y)),
            "loop": ({"start": loops[0]["start"], "end": loops[0]["end"]} if loops else None)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Invert polarity of PCM WAV files.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", help="output WAV (single file) or directory")
    ap.add_argument("--outdir")
    ap.add_argument("--suffix", default="")
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
        recs.append(process(p, dest, a.bits))
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump({"files": recs}, open(a.json, "w"), indent=2)
    print(f"{len(recs)} file(s) polarity-inverted")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
