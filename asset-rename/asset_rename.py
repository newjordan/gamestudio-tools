#!/usr/bin/env python3
"""asset-rename: bring asset file names in line with a convention, safely. Rules (combine): --case snake|kebab|lower|keep,
--replace OLD=NEW (plain text, repeatable), --regex PATTERN=REPLACEMENT (repeatable), --prefix, --suffix (before the extension),
--strip-spaces, --ext-lower. The default is a DRY RUN that prints the plan; --apply performs it. Safety: nothing is overwritten
(a target that exists, or two files mapping to one name, aborts the whole run before any file is touched), a
`rename_undo.json` log is written next to the root, and `undo` reverses a run. --fix-refs DIR rewrites exact old file names
(with extension) to the new ones inside text files (.json .tscn .tres .yarn .ink .csv .md .txt .cfg .gd .cs) under DIR so references keep working.
Only file names change; folders are left alone. Case-only renames work on case-insensitive disks via a temporary name.
"""
import argparse, os, json, re, sys, uuid

TEXT = (".json", ".tscn", ".tres", ".yarn", ".ink", ".csv", ".md", ".txt", ".cfg", ".gd", ".cs", ".import")


def convert(stem, case):
    if case == "keep": return stem
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", stem)                     # camelCase -> camel_Case
    s = re.sub(r"[\s\-]+", "_" if case == "snake" else "-", s) if case in ("snake", "kebab") else s
    if case == "kebab": s = s.replace("_", "-")
    s = re.sub(r"[^\w\-]+", "", s) if case in ("snake", "kebab") else s
    s = re.sub(r"([_\-])\1+", r"\1", s).strip("_-")
    return s.lower()


def plan(root, case="keep", replace=(), regex=(), prefix="", suffix="", strip_spaces=False, ext_lower=False, include=None):
    out = []
    for dp, dn, fn in os.walk(root):
        dn.sort()
        for f in sorted(fn):
            if f in ("rename_undo.json",): continue
            rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/")
            if include and not any(rel.endswith(e) for e in include): continue
            stem, ext = os.path.splitext(f); n = stem
            for o, nw in replace: n = n.replace(o, nw)
            for pat, rep in regex: n = re.sub(pat, rep, n)
            if strip_spaces: n = n.replace(" ", "")
            n = convert(n, case); n = prefix + n + suffix
            if ext_lower: ext = ext.lower()
            nf = n + ext
            if not n: raise SystemExit(f"{rel}: the rules would leave an empty name")
            if nf != f: out.append((rel, (os.path.dirname(rel) + "/" if os.path.dirname(rel) else "") + nf))
    return out


def check(root, moves):
    errs = []; targets = {}
    for a, b in moves: targets.setdefault(b, []).append(a)
    for b, srcs in targets.items():
        if len(srcs) > 1: errs.append(f"{', '.join(srcs)} would all become {b}")
    srcset = {a for a, _ in moves}
    for a, b in moves:
        if os.path.exists(os.path.join(root, b)) and b not in srcset and not (a.lower() == b.lower() and a in srcset): errs.append(f"{a} -> {b}: target already exists")
    return errs


def apply(root, moves, log_path=None):
    tmp = []
    for a, b in moves:                                                     # two phases so swaps and case-only renames cannot clash
        t = f"{a}.{uuid.uuid4().hex[:8]}.gstmp"; os.rename(os.path.join(root, a), os.path.join(root, t)); tmp.append((t, b))
    for t, b in tmp: os.rename(os.path.join(root, t), os.path.join(root, b))
    if log_path: json.dump({"root": os.path.abspath(root), "moves": moves}, open(log_path, "w"), indent=1)


def fix_refs(ref_dir, moves):
    by_name = {}
    for a, b in moves: by_name.setdefault(os.path.basename(a), set()).add(os.path.basename(b))
    changed = 0
    for dp, dn, fn in os.walk(ref_dir):
        for f in fn:
            if not f.endswith(TEXT): continue
            p = os.path.join(dp, f)
            try: t = open(p, encoding="utf-8").read()
            except (UnicodeDecodeError, OSError): continue
            new = t
            for old, news in by_name.items():
                if len(news) == 1: new = re.sub(r"(?<![\w.\-])" + re.escape(old) + r"(?![\w\-]|\.\w)", next(iter(news)), new)
            if new != t: open(p, "w", encoding="utf-8").write(new); changed += 1
    return changed


def undo(log_path):
    d = json.load(open(log_path)); root = d["root"]; moves = [(b, a) for a, b in d["moves"]]
    errs = [f"{a} is missing" for a, _ in moves if not os.path.exists(os.path.join(root, a))]
    if errs: raise SystemExit("cannot undo: " + "; ".join(errs))
    apply(root, moves); return len(moves)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Safe asset renamer.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("root"); r.add_argument("--case", choices=["snake", "kebab", "lower", "keep"], default="keep")
    r.add_argument("--replace", action="append", default=[]); r.add_argument("--regex", action="append", default=[]); r.add_argument("--prefix", default=""); r.add_argument("--suffix", default="")
    r.add_argument("--strip-spaces", action="store_true"); r.add_argument("--ext-lower", action="store_true"); r.add_argument("--only-ext", help="comma list, e.g. .png,.wav")
    r.add_argument("--apply", action="store_true"); r.add_argument("--fix-refs"); r.add_argument("--log")
    u = sub.add_parser("undo"); u.add_argument("log")
    a = ap.parse_args(argv)
    if a.cmd == "undo": print(f"restored {undo(a.log)} file(s)"); return 0
    moves = plan(a.root, a.case, [tuple(x.split("=", 1)) for x in a.replace], [tuple(x.split("=", 1)) for x in a.regex], a.prefix, a.suffix, a.strip_spaces, a.ext_lower, tuple(a.only_ext.split(",")) if a.only_ext else None)
    for x, y in moves: print(f"{x} -> {y}")
    errs = check(a.root, moves)
    for e in errs: print("ERROR", e)
    if errs: return 1
    print(f"{len(moves)} rename(s)" + ("" if a.apply else " (dry run; add --apply)"))
    if not a.apply or not moves: return 0
    log = a.log or os.path.join(os.path.dirname(os.path.abspath(a.root)), "rename_undo.json"); apply(a.root, moves, log); print(f"applied; undo log: {log}")
    if a.fix_refs: print(f"{fix_refs(a.fix_refs, moves)} file(s) had references updated")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
