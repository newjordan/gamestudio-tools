#!/usr/bin/env python3
"""sfx-reverse: reverse a PCM WAV in time (last sample becomes first). When the file has a
RIFF `smpl` loop, the markers are remapped so they still cover the same audio after the reverse
(`start' = (n-1)-end`, `end' = (n-1)-start`, inclusive smpl convention) unless `--no-remap-loops`
is passed (the chunk is then dropped). PCM is reversed as integers, so a file written back at
the same width (8/16/24/32-bit) is bit-exact; a wider or narrower `--bits` is a shift, not a
float round-trip. Writes a new WAV; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, wav_loop_meta, pcm_frames  # noqa: E402


def remap_loop(start, end, n):
    return (n - 1) - end, (n - 1) - start


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reverse a PCM WAV in time, optionally remapping smpl loop markers.")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--no-remap-loops", action="store_true",
                    help="drop any smpl loop chunk instead of remapping it")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32),
                    help="output bit depth (default: same as the input, 16 if the input is 8-bit)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    file_bytes = open(a.wav, "rb").read()
    loops = wav_loop_meta.read_loops(file_bytes)
    samples, sr, src_bits = pcm_frames.read_frames(str(a.wav))
    bits = a.bits or src_bits
    if bits not in (16, 24, 32):
        bits = 16
    y, bits = pcm_frames.to_bits(samples[::-1], src_bits, bits)
    n = int(y.shape[0])
    pcm_frames.write_frames(str(a.out), y, sr, bits)
    written_loops = []
    if loops and not a.no_remap_loops:
        lp = loops[0]
        ns, ne = remap_loop(int(lp["start"]), int(lp["end"]), n)
        if not (0 <= ns < ne < n):
            raise SystemExit(f"remapped loop {ns}..{ne} is outside 0..{n - 1}")
        patched = wav_loop_meta.set_loop(open(a.out, "rb").read(), ns, ne)
        open(a.out, "wb").write(patched)
        written_loops = [{"start": ns, "end": ne, "play_count": lp.get("play_count", 0)}]
        if len(loops) > 1:
            print(f"WARN {len(loops) - 1} extra smpl loop(s) not written (only the first is remapped)")
    rec = {"sr": sr, "frames": n, "bits": bits, "loops_in": loops, "loops_out": written_loops, "out": a.out}
    print(f"reversed {n} frames @ {sr} Hz" + (f", loop {written_loops[0]['start']}..{written_loops[0]['end']}" if written_loops else "") + f" -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
