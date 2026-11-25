#!/usr/bin/env python3
"""subtitle-timing: build SRT / WebVTT / engine JSON subtitles from a dialogue CSV and the recorded audio.

CSV needs id,text (speaker optional, from dialogue-extract). Durations come from <id>.wav in --audio-dir
(falls back to est_seconds / a words-per-second estimate). Lines are placed back-to-back with --gap.
Wraps to max 2 lines of --max-chars, enforces a minimum on-screen time, and warns when the reading speed
exceeds --max-cps (characters per second).
"""
import argparse, csv, json, os, textwrap, wave
import os, sys


def wav_seconds(path):
    try:
        with wave.open(path) as wf:
            return wf.getnframes() / wf.getframerate()
    except Exception:
        return None


def ts(t, comma=True):
    ms = int(round(t * 1000)); h, ms = divmod(ms, 3600000); m, ms = divmod(ms, 60000); s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}{',' if comma else '.'}{ms:03d}"


def wrap(text, width):
    lines = textwrap.wrap(text, width) or [""]
    if len(lines) > 2:   # rebalance into two lines at the middle space; flag if still too long
        mid = textwrap.wrap(text, max(width, -(-len(text) // 2) + 6))
        lines = mid
    return lines


def build(rows, audio_dir=None, gap=0.3, min_dur=1.0, max_chars=42, max_cps=17.0, start=0.0, pad=0.15):
    t, cues, warnings = start, [], []
    for r in rows:
        dur = wav_seconds(os.path.join(audio_dir, r["id"] + ".wav")) if audio_dir else None
        src = "audio"
        if dur is None:
            try:
                dur = float(r.get("est_seconds") or 0) or None
            except ValueError:
                dur = None
            src = "estimate"
        if dur is None:
            dur, src = max(0.8, len(r["text"].split()) / 2.5), "estimate"
        shown = max(dur + pad, min_dur)
        lines = wrap(r["text"], max_chars)
        cps = len(r["text"]) / shown
        if cps > max_cps: warnings.append(f"{r['id']}: {cps:.1f} chars/s exceeds {max_cps}")
        if len(lines) > 2 or any(len(l) > max_chars + 6 for l in lines): warnings.append(f"{r['id']}: text too long for 2 lines of {max_chars}")
        cues.append({"id": r["id"], "speaker": r.get("speaker", ""), "start": round(t, 3), "end": round(t + shown, 3), "lines": lines, "duration_source": src})
        t += shown + gap
    return cues, warnings


def to_srt(cues):
    return "\n".join(f"{i}\n{ts(c['start'])} --> {ts(c['end'])}\n" + "\n".join(([f"{c['speaker']}: " + c['lines'][0]] + c['lines'][1:]) if c["speaker"] else c["lines"]) + "\n" for i, c in enumerate(cues, 1))


def to_vtt(cues):
    return "WEBVTT\n\n" + "\n".join(f"{c['id']}\n{ts(c['start'], False)} --> {ts(c['end'], False)}\n" + "\n".join(([f'<v {c["speaker"]}>' + c['lines'][0]] + c['lines'][1:]) if c["speaker"] else c["lines"]) + "\n" for c in cues)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dialogue CSV + audio -> SRT/VTT/JSON subtitles.")
    ap.add_argument("csv"); ap.add_argument("-o", "--out", required=True, help="basename (.srt .vtt .json)")
    ap.add_argument("--audio-dir"); ap.add_argument("--gap", type=float, default=0.3); ap.add_argument("--min-dur", type=float, default=1.0)
    ap.add_argument("--max-chars", type=int, default=42); ap.add_argument("--max-cps", type=float, default=17.0)
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
    _src_keys = ('csv',)
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

    rows = list(csv.DictReader(open(a.csv, newline="", encoding="utf-8")))
    cues, warns = build(rows, a.audio_dir, a.gap, a.min_dur, a.max_chars, a.max_cps)
    open(a.out + ".srt", "w", encoding="utf-8").write(to_srt(cues))
    open(a.out + ".vtt", "w", encoding="utf-8").write(to_vtt(cues))
    json.dump({"cues": cues, "warnings": warns}, open(a.out + ".json", "w"), indent=1, ensure_ascii=False)
    for w in warns: print("WARN", w)
    print(f"{len(cues)} cue(s), {cues[-1]['end'] if cues else 0}s total -> {a.out}.srt/.vtt/.json")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
