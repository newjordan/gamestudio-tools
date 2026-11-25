#!/usr/bin/env python3
"""loc-key-lint: check loc-key naming conventions in a strings CSV (key column default `id`).
Flags empty or whitespace keys, characters outside a charset, a missing prefix, leading/trailing
or doubled separators, and mixed separators when a primary separator is set. Exit 1 on findings
unless `--no-fail`. Writes an optional JSON report; the CSV is never modified. The report path
is refused when it would overwrite the input unless `--in-place`.
"""
import argparse, os, csv, json, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import safe_out  # noqa: E402


def lint_key(key, charset, prefix, separator):
    issues = []
    if key is None or str(key).strip() == "":
        issues.append("blank key")
        return issues
    k = str(key)
    if k != k.strip():
        issues.append("leading or trailing whitespace")
    body = "[" + charset + "]"
    try:
        rx = re.compile("^" + body + "+$")
    except re.error as e:
        raise SystemExit(f"invalid --charset: {e}") from e
    bad = sorted({ch for ch in k if not re.match(body + r"\Z", ch)})
    if not rx.match(k):
        issues.append("characters outside charset" + (f" {bad!r}" if bad else ""))
    if prefix and not k.startswith(prefix):
        issues.append(f"missing prefix {prefix!r}")
    if separator:
        if k.startswith(separator) or k.endswith(separator):
            issues.append(f"leading or trailing separator {separator!r}")
        if separator * 2 in k:
            issues.append(f"doubled separator {separator!r}")
        others = {"_", ".", "-", "/"} - {separator}
        used = [c for c in others if c in k]
        if used:
            issues.append(f"mixed separators {used} (expected {separator!r})")
    return issues


def lint_rows(rows, key_col, charset, prefix, separator):
    out = []
    seen = {}
    for i, r in enumerate(rows, start=2):
        k = r.get(key_col, "")
        issues = lint_key(k, charset, prefix, separator)
        if k in seen and k not in (None, ""):
            issues.append(f"duplicate key (first at row {seen[k]})")
        elif k not in (None, ""):
            seen[k] = i
        for msg in issues:
            out.append({"row": i, "key": k, "msg": msg})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint loc-key naming conventions in a strings CSV.")
    ap.add_argument("csv")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--charset", default=r"A-Za-z0-9._-",
                    help="character class body allowed in keys (default: A-Za-z0-9._-)")
    ap.add_argument("--prefix", default="", help="required key prefix (e.g. ui.)")
    ap.add_argument("--separator", default=".",
                    help="hierarchical separator to check (default: .; pass empty to disable)")
    ap.add_argument("--no-fail", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    with open(a.csv, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    if not fields:
        sys.exit("CSV has no header")
    if a.key not in fields:
        sys.exit(f"key column {a.key!r} not in CSV")
    issues = lint_rows(rows, a.key, a.charset, a.prefix, a.separator)
    for it in issues:
        print(f"ERROR row {it['row']} {it['key']!r}: {it['msg']}")
    print(f"{len(rows)} key(s), {len(issues)} issue(s)")
    if a.json:
        rec = {"rows": len(rows), "issues": issues}
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0 if (a.no_fail or not issues) else 1


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
