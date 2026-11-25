#!/usr/bin/env python3
"""tmx-layer-opacity: set or report opacity and visibility on named Tiled layers (tile,
object, image, group). `--set name=0.5,other=1` and `--visible name=0,other=1` write a new
map. `--list` prints the current values (and is the default when no set/visible flags are
given). Group members are matched by layer name; duplicate names all receive the same
assignment. The input is never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def walk(layers, prefix=""):
    for i, l in enumerate(layers or []):
        path = f"{prefix}/{l.get('name') or ''}".strip("/") if prefix else (l.get("name") or "")
        yield path, l
        if l.get("type") == "group":
            yield from walk(l.get("layers") or [], path)


def parse_assignments(s, typ, flag):
    out = {}
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"{flag} expects name=value entries")
        name, val = part.split("=", 1)
        name, val = name.strip(), val.strip()
        if typ is float:
            try:
                v = float(val)
            except ValueError:
                raise SystemExit(f"{flag}: {val!r} is not a number")
            if v < 0 or v > 1:
                raise SystemExit(f"{flag}: opacity {v} is outside 0..1")
            out[name] = v
        else:
            out[name] = val.lower() not in ("0", "false", "no", "off")
    return out


def apply(layers, opacities, visibles):
    changed = 0
    seen = set()
    for path, l in walk(layers):
        name = l.get("name") or ""
        if name in opacities:
            l["opacity"] = opacities[name]
            changed += 1
            seen.add(name)
        if name in visibles:
            l["visible"] = bool(visibles[name])
            changed += 1
            seen.add(name)
    missing = [n for n in list(opacities) + [k for k in visibles if k not in opacities] if n not in seen]
    return changed, missing


def listing(layers):
    rows = []
    for path, l in walk(layers):
        rows.append({
            "name": l.get("name") or "",
            "path": path,
            "type": l.get("type") or "",
            "opacity": l.get("opacity", 1),
            "visible": l.get("visible", True),
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Set or report opacity and visibility on Tiled layers.")
    ap.add_argument("map")
    ap.add_argument("-o", "--out", help="written map (required when setting values)")
    ap.add_argument("--set", dest="opacities", help="comma list of name=opacity (0..1)")
    ap.add_argument("--visible", dest="visibles", help="comma list of name=0/1 (or true/false)")
    ap.add_argument("--list", action="store_true", help="print current opacity/visibility")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.out:
        safe_out.check(a.map, a.out, a.in_place)
    if a.json:
        safe_out.check(a.map, a.json, a.in_place)
    opacities = parse_assignments(a.opacities, float, "--set")
    visibles = parse_assignments(a.visibles, bool, "--visible")
    setting = bool(opacities or visibles)
    if setting and not a.out:
        sys.exit("setting opacity/visibility requires -o/--out")
    m = json.load(open(a.map, encoding="utf-8"))
    rec = {"layers": listing(m.get("layers") or [])}
    if setting:
        changed, missing = apply(m.get("layers") or [], opacities, visibles)
        if missing:
            sys.exit("layer(s) not found: " + ", ".join(missing))
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        json.dump(m, open(a.out, "w"), indent=2)
        rec = {"changed": changed, "layers": listing(m.get("layers") or []), "out": a.out}
        print(f"{changed} assignment(s) -> {a.out}")
    if a.list or not setting:
        for row in rec["layers"]:
            vis = "visible" if row["visible"] else "hidden"
            print(f"{row['path'] or row['name']}: opacity={row['opacity']} {vis}")
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
