#!/usr/bin/env python3
"""loc-rename: rename keys in a localisation CSV. `--map` takes a JSON/CSV table
or an inline `old=new,old=new` list; optional `--prefix` / `--suffix` are applied
after the map. Colliding destination keys are refused unless `--prefer first|last`.
Missing map keys are reported (and fail under `--strict`). The input is never
overwritten unless `--in-place`.
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-merge"))
import safe_out, loc_merge  # noqa: E402


def load_map(spec):
    if not spec:
        return {}
    if os.path.isfile(spec):
        low = spec.lower()
        if low.endswith(".csv"):
            rows = list(csv.DictReader(open(spec, newline="", encoding="utf-8-sig")))
            if not rows:
                raise SystemExit("rename CSV is empty")
            out = {}
            for r in rows:
                a = r.get("from") or r.get("old") or r.get("src") or r.get("key")
                b = r.get("to") or r.get("new") or r.get("dst") or r.get("rename")
                if a is None or b is None:
                    raise SystemExit("rename CSV needs from,to (or old,new) columns")
                out[str(a)] = str(b)
            return out
        data = json.load(open(spec, encoding="utf-8"))
        if isinstance(data, dict) and "rename" in data:
            data = data["rename"]
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        if isinstance(data, list):
            out = {}
            for item in data:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    out[str(item[0])] = str(item[1])
                else:
                    out[str(item.get("from", item.get("old")))] = str(item.get("to", item.get("new")))
            return out
        raise SystemExit("rename table must be a JSON object, a list of {from,to}, or a CSV")
    out = {}
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part and ":" not in part:
            raise SystemExit(f"bad rename token {part!r}; use old=new or a JSON/CSV file")
        a, b = part.replace(":", "=", 1).split("=", 1)
        out[a] = b
    if not out:
        raise SystemExit("rename map is empty")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rename keys in a localisation CSV.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--map", help="JSON/CSV table or inline old=new,old=new")
    ap.add_argument("--prefix", default="", help="prepended to each (already mapped) key")
    ap.add_argument("--suffix", default="", help="appended to each (already mapped) key")
    ap.add_argument("--prefer", choices=("fail", "first", "last"), default="fail",
                    help="when two keys land on the same name (default: fail)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if a --map key is missing from the CSV")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if not a.map and not a.prefix and not a.suffix:
        sys.exit("pass --map and/or --prefix / --suffix")
    safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    table = load_map(a.map)
    by, cols, dups = loc_merge.load_csv(a.csv, a.key)
    missing = [k for k in table if k not in by]
    renamed, collisions, order, seen = 0, [], [], {}
    rows = []
    for old in by:
        new = a.prefix + table.get(old, old) + a.suffix
        rec = dict(by[old])
        rec.pop("_row", None)
        rec[a.key] = new
        if new in seen:
            collisions.append({"from": [seen[new], old], "to": new})
            if a.prefer == "fail":
                continue
            if a.prefer == "last":
                # replace the earlier row
                idx = next(i for i, r in enumerate(rows) if r[a.key] == new)
                rows[idx] = rec
            # first: keep existing
        else:
            seen[new] = old
            rows.append(rec)
        if new != old:
            renamed += 1
        order.append({"from": old, "to": new})
    if collisions and a.prefer == "fail":
        sys.exit("destination key collision(s): " + ", ".join(c["to"] for c in collisions)
                 + " (pass --prefer first or --prefer last)")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    fields = [c for c in cols if c != "_row"]
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    rec = {"out": a.out, "renamed": renamed, "missing_map_keys": missing,
           "collisions": collisions, "duplicates_in": dups, "keys": order}
    if a.json:
        os.makedirs(os.path.dirname(os.path.abspath(a.json)) or ".", exist_ok=True)
        json.dump(rec, open(a.json, "w"), indent=2)
    print(f"{renamed} key(s) renamed, {len(missing)} missing map key(s) -> {a.out}")
    if a.strict and missing:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
