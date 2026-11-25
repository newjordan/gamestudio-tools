#!/usr/bin/env python3
"""cue-sheet: build an audio cue list from a folder of WAV files, for FMOD / Wwise import reviews and voice-over tracking.
Per file: duration, sample rate, channels, bit depth, peak, RMS, integrated LUFS (when the file is long enough for
wav-batch-meta), loop points from the smpl chunk, a loudness class (silent / oneshot / sfx / voice / music) and a suggested
bus. Buses come first from --rule "music/*=music" patterns (matched on the path relative to the input folder); otherwise
from the class. Class heuristics: silent if the peak is under --silent-db; music if the file loops and is longer than
--music-s (or lives in a folder named music); voice if it is longer than --voice-s and not looping; oneshot if shorter than
--oneshot-s; otherwise sfx. Writes CSV and JSON. PCM WAV only. Loudness figures come from wav-batch-meta and are not a
certified meter.
"""
import argparse, os, csv, fnmatch, glob, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-batch-meta"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "wav-loop-meta"))
import wav_batch_meta, wav_loop_meta  # noqa: E402


def collect(paths):
    out = []
    for p in paths:
        if os.path.isdir(p): out += sorted(glob.glob(os.path.join(p, "**", "*.wav"), recursive=True) + glob.glob(os.path.join(p, "**", "*.WAV"), recursive=True))
        else: out += sorted(glob.glob(p)) or [p]
    return list(dict.fromkeys(out))


def rel_to(path, roots):
    for r in roots:
        if os.path.commonpath([os.path.abspath(path), os.path.abspath(r)]) == os.path.abspath(r):
            return os.path.relpath(path, r).replace(os.sep, "/")
    return os.path.basename(path)


def classify(m, loops, rel, music_s=8.0, voice_s=1.5, oneshot_s=0.5, silent_db=-60.0):
    if m["silent"] or m["peak_db"] <= silent_db: return "silent"
    parts = rel.lower().replace("\\", "/").split("/")
    if "music" in parts or "bgm" in parts or "ost" in parts: return "music"
    if "vo" in parts or "voice" in parts or "dialogue" in parts or "speech" in parts: return "voice"
    if "sfx" in parts or "fx" in parts: 
        return "oneshot" if m["duration_s"] < oneshot_s else "sfx"
    if loops or m["duration_s"] >= music_s: return "music"
    if m["duration_s"] < oneshot_s: return "oneshot"
    if m["duration_s"] >= voice_s and m["channels"] == 1: return "voice"
    return "sfx"


def cue(path, rel, rules, **cls):
    m = wav_batch_meta.measure(path)
    try: loops = wav_loop_meta.read_loops(open(path, "rb").read())
    except (Exception, SystemExit): loops = []
    klass = classify(m, bool(loops), rel, **cls)
    bus = next((v for pat, v in rules if fnmatch.fnmatch(rel, pat)), klass)
    return {"file": path, "rel": rel, "duration_s": m["duration_s"], "rate": m["rate"], "channels": m["channels"], "bits": m["bits"],
            "peak_db": m["peak_db"], "rms_db": m["rms_db"], "lufs": m["lufs"], "loop": bool(loops),
            "loop_start": loops[0]["start"] if loops else None, "loop_end": loops[0]["end"] if loops else None,
            "class": klass, "bus": bus, "short": m["short"], "clipped": m["clipped"] > 0}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build an audio cue list (CSV/JSON) from WAV files.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--csv", default="cues.csv"); ap.add_argument("--json")
    ap.add_argument("--rule", action="append", default=[], help='path pattern=bus, e.g. "vo/*=dialogue"')
    ap.add_argument("--music-s", type=float, default=8.0); ap.add_argument("--voice-s", type=float, default=1.5)
    ap.add_argument("--oneshot-s", type=float, default=0.5); ap.add_argument("--silent-db", type=float, default=-60.0)
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('inputs',)
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    rules = []
    for r in a.rule:
        if "=" not in r: sys.exit(f"bad --rule {r!r} (want pattern=bus)")
        pat, val = r.rsplit("=", 1); rules.append((pat.replace(os.sep, "/"), val))
    roots = [p for p in a.inputs if os.path.isdir(p)]; files = collect(a.inputs)
    if not files: sys.exit("no WAV files found")
    rows, err = [], 0
    for f in files:
        try: rows.append(cue(f, rel_to(f, roots or [os.path.dirname(f) or "."]), rules, music_s=a.music_s, voice_s=a.voice_s, oneshot_s=a.oneshot_s, silent_db=a.silent_db))
        except Exception as e:
            print(f"ERR  {f}: {e}"); err += 1
    counts = {}
    for r in rows: counts[r["class"]] = counts.get(r["class"], 0) + 1
    for r in rows:
        loop = f"  loop {r['loop_start']}..{r['loop_end']}" if r["loop"] else ""
        print(f"{r['class']:<8} {r['bus']:<10} {r['duration_s']:7.2f}s  {r['rel']}{loop}")
    print(f"{len(rows)} cue(s): " + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())))
    cols = ["rel", "class", "bus", "duration_s", "rate", "channels", "bits", "peak_db", "rms_db", "lufs", "loop", "loop_start", "loop_end", "file"]
    with open(a.csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(rows)
    if a.json: json.dump(rows, open(a.json, "w"), indent=1)
    print(f"-> {a.csv}")
    return 1 if err else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
