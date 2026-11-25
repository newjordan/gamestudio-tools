#!/usr/bin/env python3
"""dialogue-stats: numbers for a Yarn / ink script set: lines, words, estimated VO minutes, lines per speaker (with share),
longest lines, narration (no speaker) share, lines without #line: ids, and graph shape: nodes, choices per node
(out-degree), most-branching nodes, terminal nodes. Built on this kit's dialogue-extract and dialogue-graph parsers, so the
same syntax limits apply. --max-words flags over-long lines (UI box overflow, VO takes); --fail-long exits 1 when any exist.
Output: text, optional Markdown and JSON.
"""
import argparse, os, collections, glob, json, sys

HERE = os.path.dirname(os.path.abspath(__file__))
for d in ("dialogue-extract", "dialogue-graph"): sys.path.insert(0, os.path.join(HERE, "..", d))
import dialogue_extract, dialogue_graph  # noqa: E402


def collect(files):
    rows, nodes = [], {}
    for f in files:
        if f.endswith(".yarn"): rows += dialogue_extract.parse_yarn(f); nodes.update(dialogue_graph.parse_yarn(open(f, encoding="utf-8").read()))
        elif f.endswith(".ink"): rows += dialogue_extract.parse_ink(f); nodes.update(dialogue_graph.parse_ink(open(f, encoding="utf-8").read()))
    return rows, dialogue_graph.resolve(nodes)


def stats(rows, nodes, top=5, max_words=None):
    words = sum(r["words"] for r in rows); n = len(rows)
    spk = collections.OrderedDict()
    for r in rows:
        s = spk.setdefault(r["speaker"] or "(narration)", {"lines": 0, "words": 0}); s["lines"] += 1; s["words"] += r["words"]
    speakers = [{"speaker": k, "lines": v["lines"], "words": v["words"], "share_pct": round(100 * v["lines"] / n, 1) if n else 0} for k, v in sorted(spk.items(), key=lambda kv: -kv[1]["lines"])]
    longest = [{"id": r["id"], "speaker": r["speaker"], "node": r["node"], "words": r["words"], "text": r["text"][:80]} for r in sorted(rows, key=lambda r: -r["words"])[:top]]
    deg = {k: len(set(d["edges"])) for k, d in nodes.items()}
    branching = [{"node": k, "choices": v} for k, v in sorted(deg.items(), key=lambda kv: -kv[1])[:top] if v > 1]
    with_edges = [v for v in deg.values() if v]
    out = {"lines": n, "words": words, "avg_words_per_line": round(words / n, 2) if n else 0, "vo_minutes": round(sum(r["est_seconds"] for r in rows) / 60, 1),
           "speakers": speakers, "narration_pct": round(100 * sum(1 for r in rows if not r["speaker"]) / n, 1) if n else 0, "lines_without_id": sum(1 for r in rows if not r["has_id"]),
           "nodes": len(nodes), "avg_branching": round(sum(with_edges) / len(with_edges), 2) if with_edges else 0, "most_branching": branching, "terminal_nodes": sorted(k for k, v in deg.items() if v == 0),
           "longest_lines": longest}
    if max_words is not None: out["over_max_words"] = [{"id": r["id"], "node": r["node"], "words": r["words"]} for r in rows if r["words"] > max_words]
    return out


def markdown(s):
    L = ["# Dialogue stats", "", f"- {s['lines']} lines, {s['words']} words ({s['avg_words_per_line']} per line), about {s['vo_minutes']} min of VO", f"- {s['nodes']} nodes, average {s['avg_branching']} outgoing links per node that has any; {len(s['terminal_nodes'])} terminal",
         f"- narration (no speaker): {s['narration_pct']}% of lines; {s['lines_without_id']} lines have no `#line:` id", "", "| Speaker | Lines | Words | Share |", "|---|---|---|---|"]
    L += [f"| {x['speaker']} | {x['lines']} | {x['words']} | {x['share_pct']}% |" for x in s["speakers"]]
    L += ["", "## Longest lines", ""] + [f"- {x['words']} words, {x['speaker'] or 'narration'} in {x['node']}: {x['text']}" for x in s["longest_lines"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Statistics for Yarn/ink dialogue.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--top", type=int, default=5); ap.add_argument("--max-words", type=int); ap.add_argument("--fail-long", action="store_true")
    ap.add_argument("--md"); ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); files = [f for p in a.inputs for f in (sorted(glob.glob(p)) or [p])]
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

    rows, nodes = collect(files)
    if not rows: sys.exit("no dialogue lines found")
    s = stats(rows, nodes, a.top, a.max_words)
    print(f"{s['lines']} lines, {s['words']} words, ~{s['vo_minutes']} min VO, {s['nodes']} nodes, branching {s['avg_branching']}")
    for x in s["speakers"]: print(f"  {x['speaker']:<16} {x['lines']:>4} lines {x['share_pct']:>5}%")
    for x in s.get("over_max_words", []): print(f"WARN  {x['node']} {x['id']}: {x['words']} words (> {a.max_words})")
    if a.md: open(a.md, "w").write(markdown(s))
    if a.json: json.dump(s, open(a.json, "w"), indent=1)
    return 1 if a.fail_long and s.get("over_max_words") else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
