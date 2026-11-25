#!/usr/bin/env python3
"""map-layer-rename: regex-rename Tiled JSON layer names, and optionally object names, by --pattern / --repl.
`--targets layers,objects` picks what is rewritten. `--dry-run` prints the planned changes and writes nothing.
Writes a new map; the input is never overwritten.
"""
import argparse, os, json, re, sys


def walk_layers(layers, fn):
    for l in layers or []:
        yield from fn(l) or ()
        if l.get("type") == "group":
            yield from walk_layers(l.get("layers") or [], fn)


def apply(m, pattern, repl, targets, dry=False):
    cre = re.compile(pattern)
    recs = []

    def rename(kind, item):
        old = item.get("name") or ""
        new = cre.sub(repl, old)
        rec = {"kind": kind, "old": old, "new": new, "changed": new != old}
        if rec["changed"] and not dry:
            item["name"] = new
        recs.append(rec)

    if "layers" in targets:
        def fn(l):
            rename("layer", l)
            return ()
        list(walk_layers(m.get("layers") or [], fn))
    if "objects" in targets:
        def fn(l):
            if l.get("type") == "objectgroup":
                for o in l.get("objects") or []:
                    rename("object", o)
            return ()
        list(walk_layers(m.get("layers") or [], fn))
    return recs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Regex-rename Tiled JSON layer (and optionally object) names.")
    ap.add_argument("map")
    ap.add_argument("--pattern", required=True, help="Python regex matched against each name")
    ap.add_argument("--repl", required=True, help="replacement (may use group backrefs)")
    ap.add_argument("--targets", default="layers", help="comma list: layers, objects (default: layers)")
    ap.add_argument("-o", "--out", help="output map (required unless --dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    targets = [t.strip() for t in a.targets.split(",") if t.strip()]
    bad = [t for t in targets if t not in ("layers", "objects")]
    if bad: sys.exit("unknown --targets: " + ", ".join(bad))
    if not a.dry_run and not a.out: sys.exit("--out is required unless --dry-run")
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.map):
        sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    m = json.load(open(a.map, encoding="utf-8"))
    recs = apply(m, a.pattern, a.repl, targets, dry=a.dry_run)
    changed = [r for r in recs if r["changed"]]
    for r in changed:
        print(f"{r['kind']}: {r['old']!r} -> {r['new']!r}")
    print(f"{len(changed)}/{len(recs)} name(s) changed")
    if not a.dry_run:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(m, open(a.out, "w"), indent=(2 if a.pretty else None),
                  separators=(None if a.pretty else (",", ":")))
        print("->", a.out)
    if a.json: json.dump({"changed": len(changed), "total": len(recs), "renames": recs}, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
