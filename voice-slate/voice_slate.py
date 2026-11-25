#!/usr/bin/env python3
"""voice-slate: build recording-session sheets per speaker from Yarn / ink scripts (or a dialogue-extract CSV).
For each speaker: lines in script order grouped by node, a stable take id and target file name per line, direction notes
(tags), estimated read time, and a session budget: read time x takes plus per-line overhead, split into sessions of at most
--session-min minutes (splits prefer node boundaries). Writes <outdir>/<speaker>.csv (blank take/notes columns for the
studio), slate.md (printable, per speaker and session) and summary.json. Lines without a speaker are skipped unless
--narrator NAME is given. Read-time estimates are the same words-per-second guess as dialogue-extract; real actors vary.
"""
import argparse, os, csv, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dialogue-extract"))
import dialogue_extract  # noqa: E402


def load_rows(paths):
    rows = []
    for p in paths:
        if p.endswith(".yarn"): rows += dialogue_extract.parse_yarn(p)
        elif p.endswith(".ink"): rows += dialogue_extract.parse_ink(p)
        elif p.endswith(".csv"):
            for i, r in enumerate(csv.DictReader(open(p, newline="", encoding="utf-8"))):
                r = dict(r); r["line"] = int(r.get("line") or i + 1); r["est_seconds"] = float(r.get("est_seconds") or 0) or max(0.8, len(r.get("text", "").split()) / 2.5)
                r.setdefault("node", ""); r.setdefault("tags", ""); rows.append(r)
        else: raise SystemExit(f"unsupported input {p} (use .yarn, .ink or dialogue-extract .csv)")
    return rows


def slug(s): return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").lower() or "unknown"


def plan(rows, takes=3.0, overhead=6.0, session_min=120.0, narrator=None, pattern="{speaker}_{id}.wav"):
    by = {}
    for r in rows:
        sp = (r.get("speaker") or "").strip() or (narrator or "")
        if not sp: continue
        by.setdefault(sp, []).append(r)
    out = {}
    for sp, rs in sorted(by.items()):
        items = []
        for n, r in enumerate(rs, 1):
            secs = float(r["est_seconds"]); cost = secs * takes + overhead
            items.append({"take_id": f"{slug(sp)}-{n:03d}", "line_id": r["id"], "file": r.get("file", ""), "node": r.get("node", ""), "text": r["text"], "direction": r.get("tags", ""),
                          "est_seconds": round(secs, 1), "budget_seconds": round(cost, 1), "target": pattern.format(speaker=slug(sp), id=r["id"], n=n)})
        # sessions: fill up to session_min, preferring to split where the node changes
        cap = session_min * 60; sessions, cur, t = [], [], 0.0
        for i, it in enumerate(items):
            if cur and t + it["budget_seconds"] > cap:
                # back up to the last node boundary if it does not leave the session nearly empty
                j = max((k for k in range(len(cur) - 1, 0, -1) if cur[k]["node"] != cur[k - 1]["node"]), default=None)
                if j is not None and sum(x["budget_seconds"] for x in cur[:j]) >= cap * 0.5:
                    sessions.append(cur[:j]); cur = cur[j:]
                else: sessions.append(cur); cur = []
                t = sum(x["budget_seconds"] for x in cur)
            cur.append(it); t += it["budget_seconds"]
        if cur: sessions.append(cur)
        for k, s in enumerate(sessions, 1):
            for it in s: it["session"] = k
        out[sp] = {"items": items, "sessions": sessions, "lines": len(items), "words": sum(len(i["text"].split()) for i in items),
                   "read_min": round(sum(i["est_seconds"] for i in items) / 60, 1), "budget_min": round(sum(i["budget_seconds"] for i in items) / 60, 1)}
    return out


def markdown(p, takes, overhead):
    L = ["# Voice recording slate", "", f"Budget assumes {takes:g} takes per line and {overhead:g} s overhead per line. Read times are estimates.", "", "| Speaker | Lines | Words | Read (min) | Budget (min) | Sessions |", "|---|---|---|---|---|---|"]
    for sp, d in p.items(): L.append(f"| {sp} | {d['lines']} | {d['words']} | {d['read_min']} | {d['budget_min']} | {len(d['sessions'])} |")
    for sp, d in p.items():
        for k, s in enumerate(d["sessions"], 1):
            L += ["", f"## {sp}, session {k} of {len(d['sessions'])} ({round(sum(i['budget_seconds'] for i in s) / 60, 1)} min budget)", "", "| Take | Node | Line | Direction | Text | File |", "|---|---|---|---|---|---|"]
            for it in s: L.append(f"| {it['take_id']} | {it['node']} | {it['line_id']} | {it['direction']} | {it['text'].replace('|', '/')} | {it['target']} |")
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recording session sheets per speaker.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("-o", "--outdir", default="slate")
    ap.add_argument("--takes", type=float, default=3.0); ap.add_argument("--overhead", type=float, default=6.0, help="seconds per line (slate, direction, playback)")
    ap.add_argument("--session-min", type=float, default=120.0); ap.add_argument("--narrator", help="speaker name for lines without one"); ap.add_argument("--speaker", action="append", help="only these speakers")
    ap.add_argument("--skip-choices", action="store_true", help="leave out player choice lines (->)")
    ap.add_argument("--pattern", default="{speaker}_{id}.wav", help="target file name: {speaker} {id} {n}")
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

    rows = [r for r in load_rows(a.inputs) if not (a.skip_choices and r.get("kind") == "choice")]
    p = plan(rows, a.takes, a.overhead, a.session_min, a.narrator, a.pattern)
    if a.speaker: p = {k: v for k, v in p.items() if k.lower() in {s.lower() for s in a.speaker}}
    if not p: sys.exit("no speakers found")
    os.makedirs(a.outdir, exist_ok=True)
    cols = ["session", "take_id", "line_id", "file", "node", "direction", "text", "est_seconds", "budget_seconds", "target", "take_no", "notes"]
    for sp, d in p.items():
        with open(os.path.join(a.outdir, slug(sp) + ".csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore"); w.writeheader(); w.writerows(d["items"])
    open(os.path.join(a.outdir, "slate.md"), "w", encoding="utf-8").write(markdown(p, a.takes, a.overhead))
    json.dump({sp: {k: v for k, v in d.items() if k not in ("items", "sessions")} | {"sessions": len(d["sessions"])} for sp, d in p.items()}, open(os.path.join(a.outdir, "summary.json"), "w"), indent=1)
    for sp, d in p.items(): print(f"{sp}: {d['lines']} lines, ~{d['read_min']} min read, ~{d['budget_min']} min budget, {len(d['sessions'])} session(s)")
    print(f"-> {a.outdir}/slate.md")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
