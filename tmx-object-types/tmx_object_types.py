#!/usr/bin/env python3
"""tmx-object-types: lint a Tiled JSON map's objects against a Tiled `objecttypes.xml`
(or a JSON type schema), or apply the schema by filling in missing default properties.
Existing property values are left alone unless `--overwrite-props` is passed with apply.
Types that are not in the schema are skipped. Encoded tile data is left untouched (objects
do not need it). Apply writes a new map; the input is never overwritten unless `--in-place`.
Lint is report-only (optional `-o` / `--json` / `--md`).
"""
import argparse, os, json, sys, xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tmx-props-lint"))
import safe_out, tmx_props_lint  # noqa: E402

TYPE_COERCE = {
    "string": lambda v: str(v) if v is not None else "",
    "int": lambda v: int(float(v)) if v not in ("", None) else 0,
    "float": lambda v: float(v) if v not in ("", None) else 0.0,
    "bool": lambda v: v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes"),
    "color": lambda v: str(v) if v else "#00000000",
    "file": lambda v: str(v) if v is not None else "",
    "object": lambda v: int(v) if v not in ("", None) else 0,
}


def walk_objects(layers, prefix=""):
    for l in layers or []:
        path = f"{prefix}/{l.get('name') or ''}".strip("/") if prefix else (l.get("name") or "")
        if l.get("type") == "group":
            yield from walk_objects(l.get("layers") or [], path)
        elif l.get("type") in ("objectgroup", None) and "objects" in l:
            for obj in l.get("objects") or []:
                yield path, l, obj


def load_types(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in (".json", ".js"):
        raw = json.load(open(path, encoding="utf-8"))
        return normalize_json(raw)
    tree = ET.parse(path)
    root = tree.getroot()
    types = {}
    for ot in root.iter("objecttype"):
        name = ot.attrib.get("name") or ""
        if not name:
            continue
        props = {}
        for p in list(ot):
            if p.tag != "property":
                continue
            pname = p.attrib.get("name")
            if not pname:
                continue
            ptype = (p.attrib.get("type") or "string").lower()
            default = p.attrib.get("default", "")
            props[pname] = {"type": ptype, "default": default}
        types[name] = {"color": ot.attrib.get("color"), "properties": props}
    return types


def normalize_json(raw):
    # Accept { "NPC": { "color", "properties": { "speed": {"type","default"} } } }
    # or { "objecttypes": [ { "name", "color", "properties": [ {"name","type","default"} ] } ] }
    # or a list of those objects.
    if isinstance(raw, dict) and "objecttypes" in raw:
        raw = raw["objecttypes"]
    types = {}
    if isinstance(raw, list):
        for item in raw:
            name = item.get("name") or ""
            if not name:
                continue
            types[name] = _props_from(item)
    elif isinstance(raw, dict):
        for name, item in raw.items():
            if not isinstance(item, dict):
                continue
            types[name] = _props_from(item, default_name=name)
    return types


def _props_from(item, default_name=None):
    props = {}
    raw_props = item.get("properties") or {}
    if isinstance(raw_props, list):
        for p in raw_props:
            if isinstance(p, dict) and p.get("name"):
                props[p["name"]] = {"type": (p.get("type") or "string").lower(),
                                    "default": p.get("default", p.get("value", ""))}
    elif isinstance(raw_props, dict):
        for pname, p in raw_props.items():
            if isinstance(p, dict):
                props[pname] = {"type": (p.get("type") or "string").lower(),
                                "default": p.get("default", p.get("value", ""))}
            else:
                props[pname] = {"type": "string", "default": p}
    return {"color": item.get("color"), "properties": props}


def coerce(ptype, value):
    fn = TYPE_COERCE.get(ptype or "string")
    if fn is None:
        return value if value is not None else ""
    try:
        return fn(value)
    except (TypeError, ValueError):
        return value


def lint_map(m, types):
    issues = []
    for path, layer, obj in walk_objects(m.get("layers") or []):
        typ = obj.get("type") or obj.get("class") or ""
        if typ not in types:
            continue
        have = tmx_props_lint.props_of(obj)
        schema = {"objects": {typ: {n: info["type"] for n, info in types[typ]["properties"].items()}}}
        # reuse type checks via a tiny required-schema: every property is required
        required = {n: info["type"] for n, info in types[typ]["properties"].items()}
        for name, ptype in required.items():
            if name not in have:
                issues.append({"layer": path, "id": obj.get("id"), "name": obj.get("name"),
                               "type": typ, "issue": "missing", "property": name, "expected": ptype})
                continue
            got_type, got_val = have[name]
            checker = tmx_props_lint.TYPE_OK.get(ptype)
            if checker and not checker(got_val):
                issues.append({"layer": path, "id": obj.get("id"), "name": obj.get("name"),
                               "type": typ, "issue": "type", "property": name, "expected": ptype,
                               "got": got_type})
    return issues


def apply_map(m, types, overwrite=False):
    m = json.loads(json.dumps(m))
    filled = 0
    overwritten = 0
    for _path, _layer, obj in walk_objects(m.get("layers") or []):
        typ = obj.get("type") or obj.get("class") or ""
        if typ not in types:
            continue
        have = tmx_props_lint.props_of(obj)
        # normalise to a property array
        props = obj.get("properties")
        if isinstance(props, dict):
            arr = [{"name": k, "type": "string", "value": v} for k, v in props.items()]
        else:
            arr = list(props or [])
        by_name = {p.get("name"): i for i, p in enumerate(arr) if isinstance(p, dict) and p.get("name")}
        for pname, info in types[typ]["properties"].items():
            ptype = info.get("type") or "string"
            default = coerce(ptype, info.get("default"))
            if pname in by_name:
                if overwrite:
                    i = by_name[pname]
                    arr[i] = {"name": pname, "type": ptype, "value": default}
                    overwritten += 1
                continue
            arr.append({"name": pname, "type": ptype, "value": default})
            by_name[pname] = len(arr) - 1
            filled += 1
        obj["properties"] = arr
        if types[typ].get("color") and "color" not in obj:
            # Tiled stores type colour in the schema, not necessarily on the object.
            pass
    return m, filled, overwritten


def format_text(issues):
    if not issues:
        return "no issues\n"
    lines = []
    for it in issues:
        loc = f"{it.get('layer') or '?'} id={it.get('id')} type={it.get('type')}"
        lines.append(f"{loc}: {it['issue']} {it['property']}" + (f" (expected {it.get('expected')})" if it.get("expected") else ""))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint or apply a Tiled objecttypes schema onto a map's objects.")
    ap.add_argument("command", choices=("lint", "apply"))
    ap.add_argument("map")
    ap.add_argument("--types", required=True, help="objecttypes.xml or a JSON schema")
    ap.add_argument("-o", "--out", help="written map (required for apply) or lint report")
    ap.add_argument("--overwrite-props", action="store_true", help="apply: replace existing values with schema defaults")
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--no-fail", action="store_true", help="lint: exit 0 even when issues are found")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    dests = [p for p in (a.out, a.json, a.md) if p]
    for d in dests:
        safe_out.check(a.map, d, a.in_place)
    if a.command == "apply" and not a.out:
        sys.exit("apply requires -o/--out")
    types = load_types(a.types)
    m = json.load(open(a.map, encoding="utf-8"))
    if a.command == "lint":
        issues = lint_map(m, types)
        rec = {"issues": issues, "count": len(issues)}
        text = format_text(issues)
        if a.out:
            os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
            if os.path.splitext(a.out)[1].lower() == ".json":
                json.dump(rec, open(a.out, "w"), indent=1)
            else:
                open(a.out, "w").write(text)
        if a.json:
            os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
            json.dump(rec, open(a.json, "w"), indent=1)
        if a.md:
            os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
            open(a.md, "w").write("# object types\n\n" + (text if issues else "No issues.\n"))
        sys.stdout.write(text)
        return 0 if (a.no_fail or not issues) else 1
    m2, filled, overwritten = apply_map(m, types, overwrite=a.overwrite_props)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m2, open(a.out, "w"), indent=2)
    rec = {"filled": filled, "overwritten": overwritten, "types": len(types), "out": a.out}
    print(f"filled {filled} propert(y/ies), overwrote {overwritten} -> {a.out}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
