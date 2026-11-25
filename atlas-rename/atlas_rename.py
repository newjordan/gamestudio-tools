#!/usr/bin/env python3
"""atlas-rename: rename frames in an atlas-pack / TexturePacker JSON with a
regex (`--pattern` / `--replace`, backrefs allowed) or an explicit
`old=new,old=new` map (or a JSON object). Colliding destination names are
refused. The image is not rewritten. The input is never overwritten unless
`--in-place`.
"""
import argparse, os, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out, atlas_json  # noqa: E402


def load_map(spec):
    if os.path.isfile(spec) and spec.lower().endswith((".json", ".csv")):
        if spec.lower().endswith(".json"):
            data = json.load(open(spec, encoding="utf-8"))
            if isinstance(data, dict) and "map" in data and isinstance(data["map"], dict):
                data = data["map"]
            if not isinstance(data, dict):
                raise SystemExit("--map JSON must be an object")
            return {str(k): str(v) for k, v in data.items()}
        rows = {}
        for line in open(spec, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "," in line:
                a, b = line.split(",", 1)
                rows[a.strip()] = b.strip()
        return rows
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"--map item {part!r} is not old=new")
        a, b = part.split("=", 1)
        out[a.strip()] = b.strip()
    return out


def frame_name(kind, name, rec):
    if kind == "array":
        return rec.get("filename") or rec.get("name") or rec.get("id") or name
    return name


def set_frame_name(kind, rec, new):
    out = json.loads(json.dumps(rec))
    if kind == "array":
        if "filename" in out or "name" not in out:
            out["filename"] = new
        elif "name" in out:
            out["name"] = new
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rename frames in an atlas JSON.")
    ap.add_argument("atlas")
    ap.add_argument("-o", "--out", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--map", help="old=new,old=new list, or a JSON object / CSV")
    g.add_argument("--pattern", help="regex matched against frame names")
    ap.add_argument("--replace", default="", help="replacement for --pattern (backrefs allowed)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.pattern is not None and a.replace == "" and not a.map:
        # empty replace is allowed (strip a prefix)
        pass
    safe_out.check(a.atlas, a.out, a.in_place)
    if a.json:
        safe_out.check(a.atlas, a.json, a.in_place)
    data, items, kind = atlas_json.load(a.atlas)
    mapping = load_map(a.map) if a.map else None
    rx = re.compile(a.pattern) if a.pattern is not None else None
    new_items = []
    seen = {}
    renamed = 0
    collisions = []
    for name, rec in items:
        src = frame_name(kind, name, rec)
        if mapping is not None:
            dest = mapping.get(src, src)
        else:
            dest = rx.sub(a.replace, src)
        if dest != src:
            renamed += 1
        rec2 = set_frame_name(kind, rec, dest)
        if dest in seen:
            collisions.append({"from": src, "to": dest, "also": seen[dest]})
        else:
            seen[dest] = src
        new_items.append((dest, rec2))
    if collisions:
        names = ", ".join(c["to"] for c in collisions[:8])
        raise SystemExit(f"colliding destination frame names: {names}")
    data2, _items, _w, _h = atlas_json._store(data, new_items,
                                              (data.get("meta") or {}).get("size", {}).get("w") or 1,
                                              (data.get("meta") or {}).get("size", {}).get("h") or 1)
    atlas_json.save(a.out, data2)
    rec = {"out": a.out, "renamed": renamed, "frames": len(new_items), "collisions": collisions}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{renamed} of {len(new_items)} frame(s) renamed -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
