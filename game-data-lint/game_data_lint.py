#!/usr/bin/env python3
"""game-data-lint: validate data tables (items, enemies, quests...) in CSV or JSON against a small schema,
including cross-table references. Catches the bugs that otherwise show up in playtests: a drop table that
points at an item that does not exist, a negative price, a typo in an enum, duplicate ids.

schema.json:
{"tables": {
  "items":   {"file": "items.csv", "key": "id", "fields": {
      "id": {"type": "str", "pattern": "^[a-z_]+$", "unique": true},
      "price": {"type": "int", "min": 0},
      "rarity": {"type": "enum", "values": ["common", "rare", "epic"]},
      "icon": {"type": "str", "required": false}}},
  "enemies": {"file": "enemies.json", "fields": {"drop": {"type": "ref", "table": "items", "list": ","}}}}}
Types: str, int, float, bool, enum, ref (value or list of values must be a key in the other table). Fields
not in the schema are reported as warnings (typos). CSV values are parsed from text; JSON must be a list of objects.
"""
import argparse, os, csv, json, re, sys


def load(path):
    if path.endswith(".json"):
        d = json.load(open(path, encoding="utf-8"))
        if not isinstance(d, list): raise SystemExit(f"{path}: expected a JSON list of objects")
        return d
    with open(path, newline="", encoding="utf-8") as f: return list(csv.DictReader(f))


def parse(v, typ):
    if typ in ("str", "enum", "ref"): return str(v)
    if isinstance(v, str): v = v.strip()
    if typ == "int":
        if isinstance(v, bool): raise ValueError
        if isinstance(v, float) and v != int(v): raise ValueError
        return int(v)
    if typ == "float": return float(v)
    if typ == "bool":
        if isinstance(v, bool): return v
        if str(v).lower() in ("true", "1", "yes"): return True
        if str(v).lower() in ("false", "0", "no"): return False
        raise ValueError
    raise SystemExit(f"unknown type {typ}")


def lint(schema, root="."):
    data = {n: load(os.path.join(root, t["file"])) for n, t in schema["tables"].items()}
    keys = {}
    for n, t in schema["tables"].items():
        k = t.get("key")
        if k: keys[n] = {str(r.get(k)) for r in data[n]}
    out = []
    add = lambda lvl, tab, row, field, msg: out.append({"level": lvl, "table": tab, "row": row, "field": field, "msg": msg})
    for n, t in schema["tables"].items():
        fields = t["fields"]; seen = {f: {} for f, s in fields.items() if s.get("unique")}
        for i, r in enumerate(data[n], 1):
            for extra in set(r) - set(fields): add("warn", n, i, extra, "field not in schema (typo?)")
            for f, s in fields.items():
                raw = r.get(f)
                if raw is None or (isinstance(raw, str) and raw.strip() == ""):
                    if s.get("required", True): add("error", n, i, f, "missing required value")
                    continue
                typ = s["type"]
                vals = [x.strip() for x in str(raw).split(s["list"])] if s.get("list") else [raw]
                for v in vals:
                    try: pv = parse(v, typ)
                    except (ValueError, TypeError): add("error", n, i, f, f"{v!r} is not a valid {typ}"); continue
                    if typ in ("int", "float"):
                        if "min" in s and pv < s["min"]: add("error", n, i, f, f"{pv} < min {s['min']}")
                        if "max" in s and pv > s["max"]: add("error", n, i, f, f"{pv} > max {s['max']}")
                    if typ == "enum" and pv not in s["values"]: add("error", n, i, f, f"{pv!r} not in {s['values']}")
                    if typ == "str" and s.get("pattern") and not re.search(s["pattern"], pv): add("error", n, i, f, f"{pv!r} does not match {s['pattern']}")
                    if typ == "ref":
                        tgt = s["table"]
                        if tgt not in keys: add("error", n, i, f, f"referenced table {tgt!r} has no key"); continue
                        if pv not in keys[tgt]: add("error", n, i, f, f"{pv!r} not found in {tgt}")
                    if s.get("unique"):
                        if str(pv) in seen[f]: add("error", n, i, f, f"duplicate {pv!r} (first at row {seen[f][str(pv)]})")
                        else: seen[f][str(pv)] = i
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint game data tables against a schema.")
    ap.add_argument("schema"); ap.add_argument("--root", help="folder the table files are relative to (default: schema folder)")
    ap.add_argument("--strict", action="store_true"); ap.add_argument("--json")
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
    _src_keys = ('schema',)
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

    res = lint(json.load(open(a.schema)), a.root or os.path.dirname(os.path.abspath(a.schema)))
    for r in res: print(f"{r['level'].upper():5} {r['table']}[{r['row']}].{r['field']}: {r['msg']}")
    e = sum(r["level"] == "error" for r in res); w = len(res) - e
    print(f"{e} error(s), {w} warning(s)")
    if a.json: json.dump(res, open(a.json, "w"), indent=1)
    return 1 if e or (a.strict and w) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
