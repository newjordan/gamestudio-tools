#!/usr/bin/env python3
"""data-diff: balance-review diff of two game data tables (CSV or JSON list of objects) matched by a key column:
rows added, removed and changed, per-field old -> new, and for numbers the percent change. Filters: --only / --ignore
columns, --min-pct to hide small numeric changes. Output: text, Markdown (--md) or JSON (--json).
--fail-on-removed and --fail-on-diff give CI exit codes. Duplicate keys are reported, and the last row wins.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "game-data-lint"))
import game_data_lint  # noqa: E402


def num(v):
    if isinstance(v, bool): return None
    try: return float(v)
    except (TypeError, ValueError): return None


def index(rows, key):
    d, dup = {}, []
    for r in rows:
        k = str(r.get(key))
        if k in d: dup.append(k)
        d[k] = r
    return d, dup


def diff(old, new, key, only=None, ignore=(), min_pct=0.0):
    o, od = index(old, key); n, nd = index(new, key); changed = {}
    for k in o.keys() & n.keys():
        cols = [c for c in dict.fromkeys(list(o[k]) + list(n[k])) if c != key and c not in ignore and (not only or c in only)]
        ch = {}
        for c in cols:
            a, b = o[k].get(c), n[k].get(c)
            if str(a if a is not None else "") == str(b if b is not None else ""): continue
            fa, fb = num(a), num(b)
            if fa is not None and fb is not None:
                if fa == fb: continue
                pct = (fb - fa) / abs(fa) * 100 if fa else float("inf")
                if abs(pct) < min_pct: continue
                ch[c] = {"old": a, "new": b, "pct": None if pct == float("inf") else round(pct, 2)}
            else: ch[c] = {"old": a, "new": b, "pct": None}
        if ch: changed[k] = ch
    fields = {}
    for ch in changed.values():
        for c in ch: fields[c] = fields.get(c, 0) + 1
    return {"added": sorted(n.keys() - o.keys()), "removed": sorted(o.keys() - n.keys()), "changed": dict(sorted(changed.items())), "fields_changed": dict(sorted(fields.items(), key=lambda kv: -kv[1])),
            "duplicate_keys": {"old": sorted(set(od)), "new": sorted(set(nd))}}


def fmt_change(c, d): return f"{c}: {d['old']} -> {d['new']}" + (f" ({d['pct']:+.1f}%)" if d["pct"] is not None else "")


def markdown(d, key):
    L = ["# Data diff", "", f"- added {len(d['added'])}, removed {len(d['removed'])}, changed {len(d['changed'])}", ""]
    if d["added"]: L += ["## Added", ""] + [f"- {k}" for k in d["added"]] + [""]
    if d["removed"]: L += ["## Removed", ""] + [f"- {k}" for k in d["removed"]] + [""]
    if d["changed"]:
        L += ["## Changed", "", f"| {key} | Change |", "|---|---|"] + [f"| {k} | " + "; ".join(fmt_change(c, x) for c, x in ch.items()) + " |" for k, ch in d["changed"].items()]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diff two game data tables by key.")
    ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("--key", required=True); ap.add_argument("--only", default=""); ap.add_argument("--ignore", default="")
    ap.add_argument("--min-pct", type=float, default=0.0); ap.add_argument("--md"); ap.add_argument("--json"); ap.add_argument("--fail-on-removed", action="store_true"); ap.add_argument("--fail-on-diff", action="store_true")
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

    d = diff(game_data_lint.load(a.old), game_data_lint.load(a.new), a.key, set(filter(None, a.only.split(","))), set(filter(None, a.ignore.split(","))), a.min_pct)
    print(f"added {len(d['added'])}, removed {len(d['removed'])}, changed {len(d['changed'])}")
    for k in d["added"]: print(f"+ {k}")
    for k in d["removed"]: print(f"- {k}")
    for k, ch in d["changed"].items(): print(f"~ {k}: " + "; ".join(fmt_change(c, x) for c, x in ch.items()))
    for side, ks in d["duplicate_keys"].items():
        if ks: print(f"WARN duplicate keys in {side}: {ks}")
    if a.md: open(a.md, "w").write(markdown(d, a.key))
    if a.json: json.dump(d, open(a.json, "w"), indent=1)
    return 1 if (a.fail_on_removed and d["removed"]) or (a.fail_on_diff and (d["added"] or d["removed"] or d["changed"])) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
