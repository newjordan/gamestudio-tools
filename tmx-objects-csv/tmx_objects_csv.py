#!/usr/bin/env python3
"""tmx-objects-csv: export Tiled object layers to a CSV, and optionally apply a CSV back onto a map.
Export columns: map, layer, id, name, type, x, y, width, height, rotation, gid, visible, plus one column per
custom property name (union across all objects). --import reads a CSV and writes a new map: rows whose id already
exists on the named layer are updated; new ids (or a blank id) are appended. Refuses to overwrite the map on import.
Group-layer paths use a slash, as in map-diff.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

BASE = ["map", "layer", "id", "name", "type", "x", "y", "width", "height", "rotation", "gid", "visible"]


def export_rows(paths):
    rows, props = [], set()
    for p in paths:
        m = map_diff.decode_map(json.load(open(p)))
        stem = os.path.basename(p)
        for layer, l in map_diff.flat_layers(m.get("layers") or []):
            if l.get("type") != "objectgroup": continue
            for o in l.get("objects") or []:
                pr = map_diff.props(o)
                props.update(pr)
                rows.append({
                    "map": stem, "layer": layer, "id": o.get("id", ""), "name": o.get("name", ""),
                    "type": o.get("type") or o.get("class") or "", "x": o.get("x", 0), "y": o.get("y", 0),
                    "width": o.get("width", 0), "height": o.get("height", 0), "rotation": o.get("rotation", 0),
                    "gid": o.get("gid", ""), "visible": o.get("visible", True), **{k: pr[k] for k in pr},
                })
    return rows, sorted(props)


def write_csv(path, rows, prop_names):
    cols = BASE + [k for k in prop_names if k not in BASE]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore"); w.writeheader()
        for r in rows:
            out = dict(r)
            if isinstance(out.get("visible"), bool): out["visible"] = "true" if out["visible"] else "false"
            w.writerow(out)


def coerce(v):
    if v is None or v == "": return v
    if isinstance(v, (int, float, bool)): return v
    s = str(v).strip()
    if s.lower() in ("true", "false"): return s.lower() == "true"
    try:
        return int(s) if s.isdigit() or (s.startswith("-") and s[1:].isdigit()) else float(s) if s.replace(".", "", 1).replace("-", "", 1).isdigit() else v
    except ValueError:
        return v


def apply_csv(map_path, csv_path):
    m = map_diff.decode_map(json.load(open(map_path)))
    # index layer path -> layer dict
    layers = {name: l for name, l in map_diff.flat_layers(m.get("layers") or []) if l.get("type") == "objectgroup"}
    # max ids
    max_id = 0
    for l in layers.values():
        for o in l.get("objects") or []: max_id = max(max_id, o.get("id") or 0)
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    updated, added = 0, 0
    for r in rows:
        layer_name = r.get("layer") or ""
        if layer_name not in layers:
            raise SystemExit(f"object layer {layer_name!r} not in the map")
        l = layers[layer_name]
        l.setdefault("objects", [])
        oid = r.get("id")
        oid = int(oid) if str(oid).strip().isdigit() else None
        target = None
        if oid is not None:
            for o in l["objects"]:
                if o.get("id") == oid: target = o; break
        if target is None:
            oid = oid if oid is not None else (max_id := max_id + 1)
            target = {"id": oid}; l["objects"].append(target); added += 1
        else:
            updated += 1
        target["name"] = r.get("name", target.get("name", ""))
        target["type"] = r.get("type", target.get("type", ""))
        for k in ("x", "y", "width", "height", "rotation"):
            if r.get(k) not in (None, ""): target[k] = coerce(r[k])
        if r.get("gid") not in (None, ""): target["gid"] = int(float(r["gid"]))
        if r.get("visible") not in (None, ""): target["visible"] = coerce(r["visible"])
        extra = {k: coerce(v) for k, v in r.items() if k not in BASE and v not in (None, "")}
        if extra:
            # merge into properties list
            cur = map_diff.props(target); cur.update(extra)
            target["properties"] = [{"name": k, "value": v} for k, v in cur.items()]
    return m, updated, added


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export or import Tiled object layers as CSV.")
    ap.add_argument("maps", nargs="+")
    ap.add_argument("-o", "--out", help="CSV (export) or map JSON (import)")
    ap.add_argument("--import-csv", dest="import_csv", help="CSV to apply onto the (single) map; write the result to --out")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if a.import_csv:
        if len(a.maps) != 1: sys.exit("import expects exactly one map")
        if not a.out: sys.exit("import requires -o for the written map")
        if os.path.abspath(a.out) == os.path.abspath(a.maps[0]) and not a.in_place:
            sys.exit("refusing to overwrite the input map; pick a different -o or pass --in-place")
        m, updated, added = apply_csv(a.maps[0], a.import_csv)
        json.dump(m, open(a.out, "w"), indent=2 if a.pretty else None, separators=None if a.pretty else (",", ":"))
        print(f"updated {updated}, added {added} -> {a.out}")
        return 0
    if not a.out: sys.exit("export requires -o for the CSV")
    rows, props = export_rows(a.maps)
    write_csv(a.out, rows, props)
    print(f"{len(rows)} object(s), {len(props)} property column(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
