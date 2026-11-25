#!/usr/bin/env python3
"""anim-rename: rename clips in an anim-meta JSON with a regex or an explicit old=new map.
`--pattern` / `--replace` use Python regex (backrefs allowed). `--map walk=run,idle=wait`
applies exact name replacements (and wins over the regex when both are given for the same
clip). Writes a new JSON; the input is never overwritten unless `--in-place`.
"""
import argparse, os, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "anim-splice"))
import safe_out, anim_splice  # noqa: E402


def parse_map(s):
    out = {}
    if not s:
        return out
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit(f"bad --map entry (expected old=new): {part}")
        old, new = part.split("=", 1)
        old, new = old.strip(), new.strip()
        if not old or not new:
            raise SystemExit(f"bad --map entry: {part}")
        out[old] = new
    return out


def rename_clips(clips, pattern, replace, mapping):
    rx = re.compile(pattern) if pattern is not None else None
    if rx is None and not mapping:
        raise SystemExit("pass --pattern/--replace and/or --map")
    new = {}
    rec = []
    collisions = []
    for name, clip in clips.items():
        dest = mapping.get(name)
        if dest is None and rx is not None:
            dest = rx.sub(replace if replace is not None else "", name)
        if dest is None:
            dest = name
        rec.append({"from": name, "to": dest, "changed": dest != name})
        if dest in new:
            collisions.append(dest)
        new[dest] = clip
    if collisions:
        raise SystemExit("rename would collide on: " + ", ".join(sorted(set(collisions))))
    return new, rec


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rename clips in an anim-meta JSON with a regex or an explicit map.")
    ap.add_argument("clips")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--pattern", help="regex matched against clip names")
    ap.add_argument("--replace", default=None, help="replacement (backrefs allowed); default empty if --pattern is set")
    ap.add_argument("--map", dest="mapping", help="comma list of old=new exact renames")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.clips, a.out, a.in_place)
    if a.json:
        safe_out.check(a.clips, a.json, a.in_place)
    data = anim_splice.load(a.clips)
    new, rec = rename_clips(data["clips"], a.pattern, a.replace, parse_map(a.mapping))
    out = dict(data)
    out["clips"] = new
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=(2 if a.pretty else None),
              separators=(None if a.pretty else (",", ":")))
    changed = sum(1 for r in rec if r["changed"])
    report = {"renamed": changed, "clips": rec, "out": a.out}
    print(f"{changed} clip(s) renamed -> {a.out}")
    if a.json:
        json.dump(report, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
