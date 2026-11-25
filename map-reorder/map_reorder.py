#!/usr/bin/env python3
"""map-reorder: reorder Tiled JSON layers (and optionally objects inside a named layer) from a name list or a
one-name-per-line file, writing a new map. Unlisted sibling layers keep their relative order at the end. Group
children can be targeted with a `group/child` path, or with --inside GROUP. --tiles-first / --objects-last are
convenience shuffles of top-level layers by type. Encoded tile data is decoded. The input is never overwritten.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402


def load_order(arg, path):
    names = []
    if path:
        for line in open(path, encoding="utf-8"):
            s = line.strip()
            if s and not s.startswith("#"): names.append(s)
    if arg:
        names.extend(n for n in arg.split(",") if n.strip())
    return names


def reorder(items, names, keyfn, unused="end"):
    """Return a new list. names that are missing are reported. unlisted items keep order at the end (or start)."""
    by = {}
    for it in items:
        k = keyfn(it)
        by.setdefault(k, []).append(it)
    seen, missing, out = set(), [], []
    for n in names:
        if n in by:
            out.extend(by[n]); seen.add(n)
        else:
            missing.append(n)
    rest = [it for it in items if keyfn(it) not in seen]
    return (rest + out) if unused == "start" else (out + rest), missing


def find_group(layers, path):
    """Walk a `a/b` path of group names; empty path means the root list (returned as a synthetic holder)."""
    if not path: return layers, None
    parts = [p for p in path.split("/") if p]
    cur, parent = layers, None
    for p in parts:
        match = next((l for l in cur if l.get("name") == p), None)
        if match is None: sys.exit(f"no layer named {p!r} in path {path}")
        if match.get("type") != "group": sys.exit(f"{p!r} is not a group layer")
        parent, cur = match, match.setdefault("layers", [])
    return cur, parent


def type_rank(l, tiles_first, objects_last):
    typ = l.get("type")
    if tiles_first and typ == "tilelayer": return 0
    if objects_last and typ == "objectgroup": return 2
    return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="Reorder Tiled JSON layers or objects from a name list.")
    ap.add_argument("map"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--order", help="comma-separated layer names (top-level, or paths with --inside)")
    ap.add_argument("--order-file", help="one layer name per line")
    ap.add_argument("--inside", default="", help="group path whose children are reordered")
    ap.add_argument("--tiles-first", action="store_true")
    ap.add_argument("--objects-last", action="store_true")
    ap.add_argument("--objects", help="reorder objects in this layer: LAYER:name1,name2 or LAYER (keep existing, sort listed first)")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.map) and not a.in_place:
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    m = map_diff.decode_map(json.load(open(a.map, encoding="utf-8")))
    names = load_order(a.order, a.order_file)
    missing = []
    if names or a.tiles_first or a.objects_last:
        target, _ = find_group(m.get("layers") or [], a.inside)
        if a.tiles_first or a.objects_last:
            target[:] = sorted(target, key=lambda l: (type_rank(l, a.tiles_first, a.objects_last), target.index(l)))
        if names:
            # if names look like paths and --inside is empty, apply to top-level by the last component? Use basename only if no slash.
            keyfn = lambda l: l.get("name", "")
            # allow group/child when inside is empty: if any name has a slash, peel those into groups
            simple = [n for n in names if "/" not in n]
            paths = [n for n in names if "/" in n]
            if simple:
                new, miss = reorder(target, simple, keyfn)
                target[:] = new; missing.extend(miss)
            for p in paths:
                parent_path, _, child = p.rpartition("/")
                grp, _ = find_group(m.get("layers") or [], parent_path)
                new, miss = reorder(grp, [child], lambda l: l.get("name", ""))
                # applying one name at a time would scramble; collect by parent
                missing.extend(miss)
            # redo path names grouped by parent
            if paths:
                from collections import OrderedDict
                buckets = OrderedDict()
                for p in paths:
                    parent_path, _, child = p.rpartition("/")
                    buckets.setdefault(parent_path, []).append(child)
                for parent_path, children in buckets.items():
                    grp, _ = find_group(m.get("layers") or [], parent_path)
                    new, miss = reorder(grp, children, lambda l: l.get("name", ""))
                    grp[:] = new; missing.extend(miss)
    if a.objects:
        layer_name, _, obj_names = a.objects.partition(":")
        # find the layer (top-level or path)
        if "/" in layer_name:
            parent_path, _, leaf = layer_name.rpartition("/")
            grp, _ = find_group(m.get("layers") or [], parent_path)
            layer = next((l for l in grp if l.get("name") == leaf), None)
        else:
            layer = next((l for _, l in map_diff.flat_layers(m.get("layers") or []) if l.get("name") == layer_name), None)
        if layer is None or layer.get("type") != "objectgroup":
            sys.exit(f"no object layer named {layer_name!r}")
        if obj_names:
            new, miss = reorder(layer.get("objects") or [], [n for n in obj_names.split(",") if n], lambda o: o.get("name", ""))
            layer["objects"] = new; missing.extend(miss)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None), separators=(None if a.pretty else (",", ":")))
    print(f"layers {[l.get('name') for l in m.get('layers') or []]} -> {a.out}")
    if missing: print("missing names: " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
