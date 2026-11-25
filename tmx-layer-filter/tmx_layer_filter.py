#!/usr/bin/env python3
"""tmx-layer-filter: keep or drop Tiled JSON layers by name glob (`--keep` or
`--drop`, comma-separated, fnmatch). Group layers are walked: a group is kept
if it matches or if any child is kept. The input is never overwritten unless
`--in-place`.
"""
import argparse, os, copy, fnmatch, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def parse_globs(s):
    return [p.strip() for p in s.split(",") if p.strip()]


def matches(name, globs):
    name = name or ""
    return any(fnmatch.fnmatchcase(name, g) or fnmatch.fnmatch(name, g) for g in globs)


def filter_layers(layers, keep, drop):
    out, kept, dropped = [], 0, 0
    for l in layers or []:
        typ = l.get("type")
        name = l.get("name") or ""
        if typ == "group":
            children, k, d = filter_layers(l.get("layers") or [], keep, drop)
            hit = (matches(name, keep) if keep else not matches(name, drop))
            if hit or children:
                g = copy.deepcopy(l)
                g["layers"] = children
                out.append(g)
                kept += k + (1 if hit or children else 0)
                dropped += d
            else:
                dropped += d + 1
            continue
        if keep:
            ok = matches(name, keep)
        else:
            ok = not matches(name, drop)
        if ok:
            out.append(copy.deepcopy(l))
            kept += 1
        else:
            dropped += 1
    return out, kept, dropped


def main(argv=None):
    ap = argparse.ArgumentParser(description="Keep or drop Tiled layers by name glob.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--keep", help="comma-separated fnmatch globs of layers to keep")
    g.add_argument("--drop", help="comma-separated fnmatch globs of layers to drop")
    ap.add_argument("--allow-empty", action="store_true", help="allow a map with no remaining layers")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    globs = parse_globs(a.keep or a.drop)
    if not globs:
        sys.exit("no globs given")
    raw = json.load(open(a.map, encoding="utf-8"))
    m = copy.deepcopy(raw)
    layers, kept, dropped = filter_layers(m.get("layers") or [],
                                          parse_globs(a.keep) if a.keep else None,
                                          parse_globs(a.drop) if a.drop else None)
    if not layers and not a.allow_empty:
        sys.exit("no layers left; pass --allow-empty to write anyway")
    m["layers"] = layers
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(m, open(a.out, "w"), indent=2)
    rec = {"out": a.out, "kept": kept, "dropped": dropped, "mode": "keep" if a.keep else "drop"}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{kept} layer(s) kept, {dropped} dropped -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
