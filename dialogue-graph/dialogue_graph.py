#!/usr/bin/env python3
"""dialogue-graph: map the structure of Yarn Spinner (.yarn) and ink (.ink) scripts and find broken flow.

Builds a node graph (Yarn: `title:` nodes + <<jump X>> / <<detour X>>; ink: knots/stitches + `-> target`
diverts and `-> END/DONE`), then reports: jumps to missing nodes (error), nodes unreachable from the start
(warning), and dead ends (a node with no outgoing edge: normal in Yarn, but in ink only a knot without
`-> END/DONE` or a divert is flagged). Exports Graphviz DOT and Mermaid for docs/wikis.
Syntax per the public Yarn Spinner and ink docs; no code from either project.
"""
import os
import argparse, glob, json, re, sys

JUMP = re.compile(r"<<\s*(?:jump|detour)\s+([A-Za-z0-9_.]+)\s*>>")
DIVERT = re.compile(r"->\s*([A-Za-z_][A-Za-z0-9_.]*)")
INK_END = {"END", "DONE"}


def parse_yarn(text):
    nodes, cur, body = {}, None, False
    for line in text.splitlines():
        s = line.strip()
        if not body and s.startswith("title:"):
            cur = s.split(":", 1)[1].strip(); nodes[cur] = {"edges": [], "lines": 0, "ends": False}; continue
        if s == "---": body = True; continue
        if s == "===": body = False; cur = None; continue
        if body and cur:
            for m in JUMP.finditer(s): nodes[cur]["edges"].append(m.group(1))
            if s and not s.startswith(("//", "<<", "->")): nodes[cur]["lines"] += 1
            if re.match(r"<<\s*stop\s*>>", s): nodes[cur]["ends"] = True
    return nodes


def parse_ink(text):
    nodes, cur, root = {}, None, "(start)"
    nodes[root] = {"edges": [], "lines": 0, "ends": False}; cur = root; knot = None
    for line in text.splitlines():
        s = line.split("//")[0].strip()
        if not s: continue
        m = re.match(r"^={2,}\s*(?:function\s+)?(\w+)", s)
        if m:
            knot = m.group(1); cur = knot; nodes[cur] = {"edges": [], "lines": 0, "ends": False}; continue
        m = re.match(r"^=\s*(\w+)", s)
        if m and knot:
            cur = f"{knot}.{m.group(1)}"; nodes[cur] = {"edges": [], "lines": 0, "ends": False}
            nodes[knot]["edges"].append(cur); continue          # falling into a stitch is an implicit edge from the knot header
        if s.startswith(("VAR ", "CONST ", "INCLUDE ", "EXTERNAL ", "~", "TODO")): continue
        for m in DIVERT.finditer(s):
            t = m.group(1)
            if t in INK_END: nodes[cur]["ends"] = True
            else: nodes[cur]["edges"].append(t if t in nodes or "." in t else (f"{knot}.{t}" if knot and f"{knot}.{t}" in nodes else t))
        if not s.startswith("->"): nodes[cur]["lines"] += 1
    if nodes[root]["lines"] == 0 and not nodes[root]["edges"] and not nodes[root]["ends"] and len(nodes) > 1:
        del nodes[root]
    return nodes


def resolve(nodes):
    """fix ink stitch references to knot.stitch after parsing."""
    for n, d in nodes.items():
        out = []
        for e in d["edges"]:
            if e in nodes: out.append(e)
            elif f"{n.split('.')[0]}.{e}" in nodes: out.append(f"{n.split('.')[0]}.{e}")
            else: out.append(e)
        d["edges"] = out
    return nodes


def analyse(nodes, start=None, kind="yarn"):
    nodes = resolve(nodes)
    start = start or next(iter(nodes))
    seen, st = set(), [start]
    while st:
        n = st.pop()
        if n in seen or n not in nodes: continue
        seen.add(n); st += nodes[n]["edges"]
    missing = sorted({(n, e) for n, d in nodes.items() for e in d["edges"] if e not in nodes})
    dead = [n for n, d in nodes.items() if not d["edges"] and (kind == "ink" and not d["ends"])]
    ends = [n for n, d in nodes.items() if not d["edges"]]
    return {"start": start, "nodes": len(nodes), "edges": sum(len(d["edges"]) for d in nodes.values()), "unreachable": sorted(set(nodes) - seen),
            "missing_targets": [{"from": a, "to": b} for a, b in missing], "dead_ends": sorted(dead), "terminal_nodes": sorted(ends)}


def to_dot(nodes, rep):
    L = ["digraph dialogue {", "  rankdir=LR; node [shape=box, style=rounded];"]
    for n, d in nodes.items():
        col = "lightcoral" if n in rep["unreachable"] else ("palegreen" if n == rep["start"] else "white")
        L.append(f'  "{n}" [label="{n}\\n{d["lines"]} lines", style="rounded,filled", fillcolor={col}];')
    for n, d in nodes.items():
        for e in sorted(set(d["edges"])):
            L.append(f'  "{n}" -> "{e}"' + (' [color=red, style=dashed]' if e not in nodes else "") + ";")
    return "\n".join(L + ["}"]) + "\n"


def to_mermaid(nodes, rep):
    ident = lambda s: re.sub(r"\W", "_", s)
    L = ["flowchart LR"]
    for n, d in nodes.items(): L.append(f'  {ident(n)}["{n} ({d["lines"]})"]')
    for n, d in nodes.items():
        for e in sorted(set(d["edges"])):
            L.append(f"  {ident(n)} --> {ident(e)}" + ("" if e in nodes else f'["{e} (MISSING)"]'))
    L += [f"  style {ident(n)} fill:#f8b4b4" for n in rep["unreachable"]]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Dialogue flow graph + checks for Yarn/ink.")
    ap.add_argument("inputs", nargs="+"); ap.add_argument("--start"); ap.add_argument("--dot"); ap.add_argument("--mermaid"); ap.add_argument("--json")
    ap.add_argument("--strict", action="store_true", help="unreachable nodes fail too")
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

    files = [f for p in a.inputs for f in (sorted(glob.glob(p)) or [p])]
    nodes, kind = {}, "yarn"
    for f in files:
        t = open(f, encoding="utf-8").read()
        if f.endswith(".ink"): nodes.update(parse_ink(t)); kind = "ink"
        else: nodes.update(parse_yarn(t))
    if not nodes: sys.exit("no nodes found")
    rep = analyse(nodes, a.start, kind)
    print(f"{rep['nodes']} node(s), {rep['edges']} edge(s), start {rep['start']!r}")
    for m in rep["missing_targets"]: print(f"ERROR  {m['from']} -> {m['to']}: target does not exist")
    for n in rep["unreachable"]: print(f"WARN   {n}: unreachable from {rep['start']!r}")
    for n in rep["dead_ends"]: print(f"WARN   {n}: ink knot has no divert or -> END/DONE")
    if a.dot: open(a.dot, "w").write(to_dot(nodes, rep))
    if a.mermaid: open(a.mermaid, "w").write(to_mermaid(nodes, rep))
    if a.json: json.dump({**rep, "graph": {n: d["edges"] for n, d in nodes.items()}}, open(a.json, "w"), indent=1)
    return 1 if rep["missing_targets"] or (a.strict and (rep["unreachable"] or rep["dead_ends"])) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
