#!/usr/bin/env python3
"""prefab-index: walk a folder of Tiled JSON maps and write a CSV or JSON index of each file: name, size, tilesets,
layer names, object types and counts, and custom map properties. Useful as a catalogue of prefab rooms. Encoded tile
data is not required (only metadata is read).
"""
import argparse, os, csv, json, sys


def collect(root):
    out = []
    if os.path.isfile(root) and root.lower().endswith(".json"):
        return [root]
    for dirpath, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".json"):
                out.append(os.path.join(dirpath, f))
    return sorted(out)


def layer_names(layers, acc=None):
    acc = [] if acc is None else acc
    for l in layers or []:
        acc.append(l.get("name") or "")
        if l.get("type") == "group":
            layer_names(l.get("layers") or [], acc)
    return acc


def object_types(layers, counts=None):
    counts = {} if counts is None else counts
    for l in layers or []:
        if l.get("type") == "group":
            object_types(l.get("layers") or [], counts)
        elif l.get("type") == "objectgroup":
            for o in l.get("objects") or []:
                typ = o.get("type") or o.get("class") or ""
                counts[typ] = counts.get(typ, 0) + 1
    return counts


def index_one(path, root):
    m = json.load(open(path, encoding="utf-8"))
    if not isinstance(m, dict) or "layers" not in m:
        return None
    rel = os.path.relpath(path, root) if os.path.isdir(root) else os.path.basename(path)
    ts = [t.get("name") or t.get("source") or "" for t in m.get("tilesets") or []]
    types = object_types(m.get("layers") or [])
    props = m.get("properties") or []
    if isinstance(props, list):
        props = {p.get("name"): p.get("value") for p in props if isinstance(p, dict)}
    return {
        "file": rel.replace("\\", "/"),
        "name": m.get("name") or os.path.splitext(os.path.basename(path))[0],
        "width": m.get("width"),
        "height": m.get("height"),
        "tilewidth": m.get("tilewidth"),
        "tileheight": m.get("tileheight"),
        "tilesets": ts,
        "layers": layer_names(m.get("layers") or []),
        "object_types": types,
        "object_count": sum(types.values()),
        "properties": props,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Index a folder of Tiled JSON maps as CSV or JSON.")
    ap.add_argument("folder")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--json", action="store_true", help="write JSON (default: CSV)")
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
    _src_keys = ('folder',)
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

    files = collect(a.folder)
    if not files: sys.exit("no JSON maps found")
    rows = []
    skipped = 0
    for f in files:
        rec = index_one(f, a.folder)
        if rec is None:
            skipped += 1; continue
        rows.append(rec)
    if not rows: sys.exit("no Tiled JSON maps found (files lacked a layers key)")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    if a.json or a.out.lower().endswith(".json"):
        json.dump(rows, open(a.out, "w"), indent=1)
    else:
        flat = []
        for r in rows:
            flat.append({
                "file": r["file"], "name": r["name"],
                "width": r["width"], "height": r["height"],
                "tilewidth": r["tilewidth"], "tileheight": r["tileheight"],
                "tilesets": ",".join(r["tilesets"]),
                "layers": ",".join(r["layers"]),
                "object_types": ";".join(f"{k}:{v}" for k, v in sorted(r["object_types"].items(), key=lambda x: x[0])),
                "object_count": r["object_count"],
                "properties": json.dumps(r["properties"], separators=(",", ":")),
            })
        w = csv.DictWriter(open(a.out, "w", newline=""), fieldnames=list(flat[0]))
        w.writeheader(); w.writerows(flat)
    print(f"{len(rows)} map(s) indexed" + (f", {skipped} skipped" if skipped else "") + f" -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
