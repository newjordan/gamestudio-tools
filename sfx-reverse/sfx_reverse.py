#!/usr/bin/env python3
"""sfx-reverse: reverse a PCM WAV in time (last sample becomes first). When the file has a
RIFF `smpl` loop, the markers are remapped so they still cover the same audio after the reverse
(`start' = (n-1)-end`, `end' = (n-1)-start`, inclusive smpl convention) unless `--no-remap-loops`
is passed (the chunk is then dropped). Uses the shared audio-tidy PCM reader (paths must be
str()). Writes a new WAV; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys, wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "audio-tidy"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import safe_out, audio_tidy, wav_loop_meta  # noqa: E402


def wav_bits(path):
    with wave.open(path, "rb") as wf:
        return wf.getsampwidth() * 8


def remap_loop(start, end, n):
    return (n - 1) - end, (n - 1) - start


def reverse_pcm(x):
    if x.ndim == 1:
        x = x[:, None]
    return x[::-1].copy()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reverse a PCM WAV in time, optionally remapping smpl loop markers.")
    ap.add_argument("wav")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--no-remap-loops", action="store_true",
                    help="drop any smpl loop chunk instead of remapping it")
    ap.add_argument("--bits", type=int, choices=(16, 24, 32),
                    help="output bit depth (default: same as the input, 16 if unknown)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.wav, a.out, a.in_place)
    if a.json:
        safe_out.check(a.wav, a.json, a.in_place)
    raw = open(a.wav, "rb").read()
    loops = wav_loop_meta.read_loops(raw)
    x, sr = audio_tidy.read_wav(str(a.wav))
    y = reverse_pcm(x)
    n = int(y.shape[0])
    bits = a.bits or wav_bits(str(a.wav))
    if bits not in (16, 24, 32):
        bits = 16
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    audio_tidy.write_wav(str(a.out), y, sr, bits=bits)
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
