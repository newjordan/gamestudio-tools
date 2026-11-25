#!/usr/bin/env python3
"""wav-loop-meta: read, write and clear loop points stored inside a WAV (RIFF `smpl` chunk), the metadata
that samplers, FMOD/Wwise importers and many engines read. Other chunks and the audio data are kept byte for
byte. Pairs with loop-finder (`from-json` takes its output).
  show a.wav | set a.wav --start N --end N [-o out.wav] | clear a.wav [-o out.wav] | from-json loops.json --dir DIR
Sample positions are in frames; `end` is the last sample of the loop (smpl convention, inclusive).
"""
import argparse, os, json, struct, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402


def chunks(data):
    return gst_read.wav_chunks(data)


def build(chs):
    body = b"WAVE"
    for cid, payload in chs:
        body += cid + struct.pack("<I", len(payload)) + payload + (b"\0" if len(payload) & 1 else b"")
    return b"RIFF" + struct.pack("<I", len(body)) + body


def smpl_payload(sr, start, end, play_count=0):
    return struct.pack("<9I", 0, 0, int(1e9 / sr), 60, 0, 0, 0, 1, 0) + struct.pack("<6I", 0, 0, start, end, 0, play_count)


def read_loops(data):
    for cid, p in chunks(data):
        if cid == b"smpl":
            if len(p) < 36:
                raise GstInputError("WAV smpl chunk is truncated")
            n = struct.unpack_from("<I", p, 28)[0]
            out = []
            for i in range(n):
                off = 36 + 24 * i
                if off + 24 > len(p):
                    raise GstInputError("WAV smpl chunk is truncated")
                out.append({"start": struct.unpack_from("<I", p, off + 8)[0],
                            "end": struct.unpack_from("<I", p, off + 12)[0],
                            "play_count": struct.unpack_from("<I", p, off + 20)[0]})
            return out
    return []


def info(data):
    fmt, dat = gst_read.wav_fmt_and_data(data)
    ch, sr, _, _, bits = struct.unpack_from("<HIIHH", fmt, 2)
    if ch < 1 or bits < 8:
        raise GstInputError("WAV fmt chunk is truncated")
    width = ch * (bits // 8)
    if width < 1:
        raise GstInputError("WAV fmt chunk is truncated")
    return sr, len(dat) // width


def set_loop(data, start, end):
    sr, frames = info(data)
    if not (0 <= start < end < frames): raise SystemExit(f"loop {start}..{end} outside 0..{frames - 1}")
    chs = [(c, p) for c, p in chunks(data) if c != b"smpl"] + [(b"smpl", smpl_payload(sr, start, end))]
    return build(chs)


def clear(data):
    return build([(c, p) for c, p in chunks(data) if c != b"smpl"])


def main(argv=None):
    ap = argparse.ArgumentParser(description="WAV loop-point metadata.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show"); s.add_argument("wav")
    s = sub.add_parser("set"); s.add_argument("wav"); s.add_argument("--start", type=int, required=True); s.add_argument("--end", type=int, required=True); s.add_argument("-o", "--out")
    s.add_argument("--in-place", action="store_true", help="allow overwriting the input WAV")
    s = sub.add_parser("clear"); s.add_argument("wav"); s.add_argument("-o", "--out")
    s.add_argument("--in-place", action="store_true", help="allow overwriting the input WAV")
    s = sub.add_parser("from-json"); s.add_argument("json"); s.add_argument("--dir", required=True); s.add_argument("-o", "--outdir")
    s.add_argument("--in-place", action="store_true", help="allow overwriting WAVs in --dir when --outdir is omitted")
    a = ap.parse_args(argv)
    if a.cmd == "show":
        d = open(a.wav, "rb").read(); sr, fr = info(d); lp = read_loops(d)
        print(f"{a.wav}: {fr} frames @ {sr} Hz, loops: {lp or 'none'}")
    elif a.cmd == "set":
        if not a.out and not a.in_place:
            sys.exit("refusing to overwrite the input; pass -o or --in-place")
        out = a.out or a.wav
        safe_out.check(a.wav, out, a.in_place)
        data = open(a.wav, "rb").read()
        open(out, "wb").write(set_loop(data, a.start, a.end)); print(f"loop {a.start}..{a.end} -> {out}")
    elif a.cmd == "clear":
        if not a.out and not a.in_place:
            sys.exit("refusing to overwrite the input; pass -o or --in-place")
        out = a.out or a.wav
        safe_out.check(a.wav, out, a.in_place)
        data = open(a.wav, "rb").read()
        open(out, "wb").write(clear(data)); print(f"cleared -> {out}")
    else:
        if not a.outdir and not a.in_place:
            sys.exit("refusing to overwrite inputs in --dir; pass --outdir or --in-place")
        for name, lp in json.load(open(a.json)).items():
            srcp = os.path.join(a.dir, name); out = os.path.join(a.outdir or a.dir, name)
            safe_out.check(srcp, out, a.in_place)
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            data = open(srcp, "rb").read()
            open(out, "wb").write(set_loop(data, lp["start"], lp["end"] - 1)); print(f"{name}: loop {lp['start']}..{lp['end'] - 1}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
