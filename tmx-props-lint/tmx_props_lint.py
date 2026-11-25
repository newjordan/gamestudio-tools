#!/usr/bin/env python3
"""tmx-props-lint: check that Tiled objects (and optionally layers) carry required custom properties of the expected
types. The schema is a JSON file keyed by object type (`*` is a default). Exit 1 when anything is missing or mistyped,
for CI. Encoded maps are decoded. Reports text, JSON or Markdown.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

TYPE_OK = {
    "string": lambda v: isinstance(v, str),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool) or v in (0, 1, "true", "false", "True", "False"),
    "color": lambda v: isinstance(v, str) and (v.startswith("#") and len(v) in (7, 9)),
    "file": lambda v: isinstance(v, str),
    "object": lambda v: isinstance(v, int) and not isinstance(v, bool),
}


def props_of(obj):
    out = {}
    for p in obj.get("properties") or []:
        if isinstance(p, dict) and "name" in p:
            out[p["name"]] = (p.get("type") or "string", p.get("value"))
    # Tiled JSON sometimes uses a dict (older / some exporters)
    if isinstance(obj.get("properties"), dict):
        for k, v in obj["properties"].items():
            out[k] = ("string", v)
    return out


def schema_for(schema, typ):
    objects = schema.get("objects") or schema
    if typ in objects: return objects[typ]
    if "*" in objects: return objects["*"]
    return None


def check_object(o, layer, schema, path):
    typ = o.get("type") or o.get("class") or ""
    rule = schema_for(schema, typ)
    if rule is None: return []
    required = list(rule.get("required") or [])
    types = dict(rule.get("types") or {})
    have = props_of(o)
    issues = []
    ident = o.get("name") or o.get("id") or "?"
    builtins = {"name", "id", "x", "y", "width", "height", "gid", "type", "class"}
    for key in required:
        if key in have:
            continue
        if key in builtins and key in o:
            val = o.get(key)
            if key == "name" and not str(val or "").strip():
                issues.append({"kind": "missing", "layer": layer, "object": ident, "type": typ, "property": key, "path": path})
            continue
        issues.append({"kind": "missing", "layer": layer, "object": ident, "type": typ, "property": key, "path": path})
    for key, expect in types.items():
        if key not in have: continue
        ptype, value = have[key]
        fn = TYPE_OK.get(expect)
        if fn is None:
            issues.append({"kind": "unknown_type", "layer": layer, "object": ident, "type": typ, "property": key,
                           "expected": expect, "path": path})
        elif not fn(value):
            issues.append({"kind": "type", "layer": layer, "object": ident, "type": typ, "property": key,
                           "expected": expect, "got": type(value).__name__, "value": value, "path": path})
    return issues


def lint(m, schema, path=""):
    issues = []
    def walk(layers, prefix=""):
        for l in layers or []:
            name = prefix + l.get("name", "")
            if l.get("type") == "group":
                walk(l.get("layers") or [], name + "/")
            elif l.get("type") == "objectgroup":
                for o in l.get("objects") or []:
                    issues.extend(check_object(o, name, schema, path))
    walk(m.get("layers") or [])
    return issues


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint required Tiled object properties against a JSON schema.")
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--schema", required=True)
    ap.add_argument("--json")
    ap.add_argument("--md")
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
    _src_keys = ('maps', 'schema')
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

    schema = json.load(open(a.schema, encoding="utf-8"))
    all_issues = []
    for path in a.maps:
        m = map_diff.decode_map(json.load(open(path, encoding="utf-8")))
        iss = lint(m, schema, path)
        all_issues.extend(iss)
        if not iss:
            print(f"ok {path}")
        else:
            print(f"{path}: {len(iss)} issue(s)")
            for i in iss:
                extra = f" (expected {i['expected']}, got {i.get('got')})" if i["kind"] == "type" else ""
                print(f"  {i['kind']} {i['layer']}/{i['object']} type={i['type']!r} prop={i['property']}{extra}")
    rec = {"issues": all_issues, "count": len(all_issues)}
    if a.json: json.dump(rec, open(a.json, "w"), indent=1)
    if a.md:
        lines = [f"# tmx-props-lint ({len(all_issues)} issue(s))", ""]
        for i in all_issues:
            lines.append(f"- `{i['path']}` {i['kind']} `{i['layer']}/{i['object']}` type `{i['type']}` prop `{i['property']}`")
        open(a.md, "w").write("\n".join(lines) + "\n")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
