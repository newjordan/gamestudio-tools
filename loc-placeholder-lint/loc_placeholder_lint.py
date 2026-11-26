#!/usr/bin/env python3
"""loc-placeholder-lint: check that placeholder tokens stay consistent across languages in a loc CSV.
Tokens recognised: {name} and {name:fmt}, printf %s %d %i %f %x (and %% as an escape, not a token),
numbered printf %1$s, and $var$. ICU `{var, plural|select, ...}` counts as `{var}`; `{# words}`
inside a branch is translated text. Named placeholders are compared as a multiset (order does not matter);
unnumbered printf tokens are compared in order. Numbered printf tokens are compared by index and type.
JSON and text reports; exit 1 on any mismatch. Complements loc-check (which also looks at tags, escapes and length).
"""
import os
import argparse, csv, json, re, sys
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from icu_text import placeholder_view  # noqa: E402

# named {foo} or {foo:bar} — but not ${foo} ICU-ish starting with $ already handled separately
NAMED = re.compile(r"(?<!\$)\{([^{}]+)\}")
# numbered printf first, then unnumbered; %% is skipped by not matching a doubled %
NUMBERED = re.compile(r"%(\d+)\$([sdifxX])")
UNNUMBERED = re.compile(r"%([sdifxX])")
DOLLAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)\$")


def tokens(s):
    """Return a dict describing placeholders in s."""
    s = placeholder_view(s)
    named = NAMED.findall(s)
    numbered = NUMBERED.findall(s)
    # strip numbered and escaped %% before looking for unnumbered
    tmp = NUMBERED.sub("", s).replace("%%", "")
    unnumbered = UNNUMBERED.findall(tmp)
    dollar = DOLLAR.findall(s)
    return {
        "named": named,  # list of inner text (name or name:fmt)
        "named_set": Counter(n.split(":", 1)[0].strip() for n in named),
        "numbered": {int(i): typ for i, typ in numbered},
        "printf": unnumbered,  # ordered types
        "dollar": Counter(dollar),
    }


def compare(src, dst):
    a, b = tokens(src), tokens(dst)
    issues = []
    if a["named_set"] != b["named_set"]:
        miss = list((a["named_set"] - b["named_set"]).elements())
        extra = list((b["named_set"] - a["named_set"]).elements())
        issues.append("named mismatch" + (f", missing {miss}" if miss else "") + (f", unexpected {extra}" if extra else ""))
    if a["numbered"] != b["numbered"]:
        issues.append(f"numbered printf mismatch (source {a['numbered']}, got {b['numbered']})")
    if a["printf"] != b["printf"]:
        issues.append(f"printf order/types mismatch (source {a['printf']}, got {b['printf']})")
    if a["dollar"] != b["dollar"]:
        miss = list((a["dollar"] - b["dollar"]).elements())
        extra = list((b["dollar"] - a["dollar"]).elements())
        issues.append("dollar mismatch" + (f", missing {miss}" if miss else "") + (f", unexpected {extra}" if extra else ""))
    return issues


def lint(rows, src, langs):
    out = []
    for r in rows:
        s = r.get(src) or ""
        for lang in langs:
            t = r.get(lang)
            if t is None or not str(t).strip():
                continue  # missing translations are loc-check's job
            for msg in compare(s, t):
                out.append({"id": r.get("id", ""), "lang": lang, "msg": msg, "source": s, "text": t})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint loc-CSV placeholder consistency across languages.")
    ap.add_argument("csv"); ap.add_argument("--source", default="en")
    ap.add_argument("--langs", help="comma list (default: every column except id and --source)")
    ap.add_argument("--json")
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
    _src_keys = ('csv',)
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

    with open(a.csv, newline="", encoding="utf-8") as f:
        rd = csv.DictReader(f); rows = list(rd); cols = rd.fieldnames or []
    if a.source not in cols: sys.exit(f"source column {a.source!r} not in {cols}")
    langs = a.langs.split(",") if a.langs else [c for c in cols if c not in ("id", a.source)]
    issues = lint(rows, a.source, langs)
    for i in issues:
        print(f"ERROR {i['id']} [{i['lang']}]: {i['msg']}")
    print(f"{len(rows)} string(s), {len(langs)} language(s): {len(issues)} mismatch(es)")
    if a.json: json.dump(issues, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 1 if issues else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
