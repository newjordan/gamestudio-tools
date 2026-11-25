#!/usr/bin/env python3
"""vo-diff: compare two dialogue-extract CSVs (or any CSV with id,text[,speaker]) and tell the VO/loc team
exactly what changed between script versions: added, removed, text-changed, speaker-changed lines,
with estimated re-record minutes per speaker. Optionally check a recordings folder for lines that have
no audio yet (files named <id>.wav/.ogg/.mp3/.flac).
"""
import argparse, csv, difflib, json, os, re
from collections import defaultdict
import os, sys

AUDIO = (".wav", ".ogg", ".mp3", ".flac", ".opus")


def load(path):
    rows = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            rows[r["id"]] = r
    return rows


def norm(t):
    return re.sub(r"\s+", " ", t).strip()


def est(r):
    try:
        return float(r.get("est_seconds") or 0) or max(0.8, len(norm(r.get("text", "")).split()) / 2.5)
    except ValueError:
        return 1.0


def diff(old, new, ratio_minor=0.92):
    out = {"added": [], "removed": [], "changed": [], "minor": [], "speaker_changed": [], "unchanged": 0}
    for i, r in new.items():
        if i not in old:
            out["added"].append(r)
            continue
        o = old[i]
        if o.get("speaker", "") != r.get("speaker", ""):
            out["speaker_changed"].append({**r, "old_speaker": o.get("speaker", "")})
        if norm(o["text"]) != norm(r["text"]):
            sim = difflib.SequenceMatcher(None, norm(o["text"]), norm(r["text"])).ratio()
            (out["minor"] if sim >= ratio_minor else out["changed"]).append({**r, "old_text": o["text"], "similarity": round(sim, 3)})
        elif o.get("speaker", "") == r.get("speaker", ""):
            out["unchanged"] += 1
    out["removed"] = [r for i, r in old.items() if i not in new]
    return out


def rerecord_minutes(d):
    per = defaultdict(float)
    for key in ("added", "changed", "minor", "speaker_changed"):
        for r in d[key]:
            per[r.get("speaker") or "(none)"] += est(r)
    return {k: round(v / 60, 2) for k, v in sorted(per.items())}


def missing_audio(rows, folder):
    have = {os.path.splitext(f)[0] for f in os.listdir(folder) if f.lower().endswith(AUDIO)}
    return [r for i, r in rows.items() if i not in have]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff two dialogue CSVs for VO/localisation.")
    ap.add_argument("old"); ap.add_argument("new")
    ap.add_argument("-o", "--out", help="CSV of lines needing (re)recording")
    ap.add_argument("--json", help="full diff JSON")
    ap.add_argument("--audio-dir", help="folder of recordings named <id>.<ext>; report lines with no audio")
    ap.add_argument("--minor-ratio", type=float, default=0.92, help="similarity above which an edit is 'minor' (typo-level)")
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
    _src_keys = ('old', 'new')
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

    old, new = load(a.old), load(a.new)
    d = diff(old, new, a.minor_ratio)
    mins = rerecord_minutes(d)
    print(f"added {len(d['added'])}, removed {len(d['removed'])}, changed {len(d['changed'])}, minor {len(d['minor'])}, "
          f"speaker-changed {len(d['speaker_changed'])}, unchanged {d['unchanged']}")
    print("re-record estimate (min): " + (", ".join(f"{k} {v}" for k, v in mins.items()) or "none"))
    if a.audio_dir:
        miss = missing_audio(new, a.audio_dir)
        d["no_audio"] = miss
        print(f"{len(miss)} of {len(new)} line(s) have no recording in {a.audio_dir}")
    if a.out:
        cols = ["id", "speaker", "text", "reason"]
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
            seen = set()
            for key, reason in (("added", "new"), ("changed", "text changed"), ("minor", "minor edit, check wording"), ("speaker_changed", "speaker changed"), ("no_audio", "no recording")):
                for r in d.get(key, []):
                    if r["id"] not in seen:
                        seen.add(r["id"]); w.writerow({"id": r["id"], "speaker": r.get("speaker", ""), "text": r["text"], "reason": reason})
        print(f"wrote {a.out}")
    if a.json:
        json.dump({**d, "rerecord_minutes": mins}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
