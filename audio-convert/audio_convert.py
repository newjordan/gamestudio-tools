#!/usr/bin/env python3
"""audio-convert: batch WAV -> OGG Vorbis / Opus / MP3 / FLAC with sensible game presets, via the local
`ffmpeg` binary (arguments are passed as a list, no shell). Optional EBU R128 loudness normalisation.
`-bitexact` and `-map_metadata -1` keep the encoded file free of the encoder version and the
wall-clock date, so the same WAV encodes to the same bytes.
Presets: music (vorbis q5), sfx (vorbis q4, mono), voice (opus 48k mono), mp3 (lame q2), flac.
Runs locally on whatever machine you run it on; it only reads your files and writes the outputs.
"""
import argparse, os, glob, shutil, subprocess, sys

PRESETS = {
    "music": (".ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
    "sfx": (".ogg", ["-c:a", "libvorbis", "-q:a", "4", "-ac", "1"]),
    "voice": (".opus", ["-c:a", "libopus", "-b:a", "48k", "-ac", "1", "-application", "voip"]),
    "mp3": (".mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
    "flac": (".flac", ["-c:a", "flac"]),
}


def command(src, dst, preset, loudnorm=None, rate=None, overwrite=True):
    ext, args = PRESETS[preset]
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y" if overwrite else "-n", "-i", src,
           "-vn", "-bitexact", "-map_metadata", "-1"]
    filters = []
    if loudnorm is not None:
        filters.append(f"loudnorm=I={loudnorm}:TP=-1.5:LRA=11")
    if filters:
        cmd += ["-af", ",".join(filters)]
    if rate:
        cmd += ["-ar", str(rate)]
    return cmd + args + [dst]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Batch convert WAVs for shipping.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--preset", choices=PRESETS, default="music")
    ap.add_argument("--loudnorm", type=float, metavar="LUFS", help="normalise integrated loudness, e.g. -16 (music) / -19 (voice)")
    ap.add_argument("--rate", type=int)
    ap.add_argument("--dry-run", action="store_true", help="print the ffmpeg commands only")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if not a.dry_run and not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not found on PATH")
    files = [f for p in a.inputs for f in (sorted(glob.glob(p)) or [p]) if f.lower().endswith((".wav", ".flac", ".ogg", ".mp3"))]
    os.makedirs(a.outdir, exist_ok=True)
    ok = 0
    for f in files:
        dst = os.path.join(a.outdir, os.path.splitext(os.path.basename(f))[0] + PRESETS[a.preset][0])
        if os.path.abspath(dst) == os.path.abspath(f) and not a.in_place:
            sys.exit("refusing to overwrite the input; pick a different --outdir or pass --in-place")
        cmd = command(f, dst, a.preset, a.loudnorm, a.rate)
        if a.dry_run:
            print(" ".join(cmd)); continue
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            print(f"FAIL {f}: {r.stderr.strip()[:200]}", file=sys.stderr)
        else:
            ok += 1; print(f"{f} -> {dst} ({os.path.getsize(f)} -> {os.path.getsize(dst)} B)")
    return 0 if ok == len(files) or a.dry_run else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
