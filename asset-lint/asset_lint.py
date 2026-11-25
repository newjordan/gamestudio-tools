#!/usr/bin/env python3
"""asset-lint: rule-based checks on an asset folder before it lands in the game repo.

Rules live in a small JSON file (naming regex per folder/extension, max texture size, power-of-two,
alpha required/forbidden, max file size, WAV sample rate/channels, forbidden extensions).
Exit code 1 when any error is found, so it works as a pre-commit hook or CI step.
Idea after CyberAgent's AssetRegulationManager (MIT) for Unity; this is an engine-agnostic CLI.
"""
import argparse, os, fnmatch, json, re, sys, wave
from PIL import Image

DEFAULT_RULES = {
    "rules": [
        {"glob": "**/*.png", "max_size": 2048, "pot": True, "name": "^[a-z0-9_]+\\.png$", "max_kb": 4096},
        {"glob": "**/ui/*.png", "pot": False, "alpha": "required"},
        {"glob": "**/*.jpg", "alpha": "forbidden", "max_size": 4096},
        {"glob": "**/*.wav", "sample_rates": [44100, 48000], "max_channels": 2, "name": "^[a-z0-9_]+\\.wav$"},
        {"glob": "**/*.psd", "forbid": "source files belong in the art repo, not the game repo"},
        {"glob": "**/* *", "forbid": "no spaces in paths"},
    ]
}


def is_pot(n):
    return n > 0 and (n & (n - 1)) == 0


def match(rel, pattern):
    rel = rel.replace(os.sep, "/")
    return fnmatch.fnmatch(rel, pattern) or (pattern.startswith("**/") and fnmatch.fnmatch(rel, pattern[3:]))


def effective(rel, rules):
    eff = {}
    for r in rules:
        if match(rel, r["glob"]):
            eff.update({k: v for k, v in r.items() if k != "glob"})
    return eff


def check_file(path, rel, rule):
    issues = []
    base = os.path.basename(path)
    if "forbid" in rule:
        return [("error", rule["forbid"])]
    if "name" in rule and not re.match(rule["name"], base):
        issues.append(("error", f"name does not match {rule['name']}"))
    if "max_kb" in rule and os.path.getsize(path) > rule["max_kb"] * 1024:
        issues.append(("warn", f"file is {os.path.getsize(path)//1024} KB > {rule['max_kb']} KB"))
    ext = os.path.splitext(path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".tga", ".webp", ".bmp"):
        try:
            with Image.open(path) as im:
                w, h = im.size
                has_alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        except Exception as e:
            return [("error", f"unreadable image: {e}")]
        if "max_size" in rule and max(w, h) > rule["max_size"]:
            issues.append(("error", f"{w}x{h} exceeds {rule['max_size']}"))
        if rule.get("pot") and not (is_pot(w) and is_pot(h)):
            issues.append(("warn", f"{w}x{h} is not power-of-two"))
        if rule.get("alpha") == "required" and not has_alpha:
            issues.append(("error", "alpha channel required"))
        if rule.get("alpha") == "forbidden" and has_alpha:
            issues.append(("warn", "unexpected alpha channel"))
    if ext == ".wav":
        try:
            with wave.open(path) as wf:
                sr, ch = wf.getframerate(), wf.getnchannels()
        except Exception as e:
            return issues + [("error", f"unreadable wav: {e}")]
        if "sample_rates" in rule and sr not in rule["sample_rates"]:
            issues.append(("error", f"sample rate {sr} not in {rule['sample_rates']}"))
        if "max_channels" in rule and ch > rule["max_channels"]:
            issues.append(("error", f"{ch} channels > {rule['max_channels']}"))
    return issues


def lint(root, rules):
    results = []
    for dp, _, files in os.walk(root):
        for f in sorted(files):
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root)
            rule = effective(rel, rules)
            if rule:
                for level, msg in check_file(p, rel, rule):
                    results.append({"file": rel, "level": level, "msg": msg})
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint game assets against budget/naming rules.")
    ap.add_argument("root")
    ap.add_argument("-r", "--rules", help="rules JSON (default: built-in)")
    ap.add_argument("--write-default-rules", metavar="PATH", help="dump built-in rules and exit")
    ap.add_argument("--json", help="write findings JSON")
    ap.add_argument("--strict", action="store_true", help="warnings also fail")
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
    _src_keys = ('root',)
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

    if a.write_default_rules:
        json.dump(DEFAULT_RULES, open(a.write_default_rules, "w"), indent=2)
        print(f"wrote {a.write_default_rules}")
        return 0
    rules = json.load(open(a.rules))["rules"] if a.rules else DEFAULT_RULES["rules"]
    res = lint(a.root, rules)
    for r in res:
        print(f"{r['level'].upper():5} {r['file']}: {r['msg']}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    errs = sum(r["level"] == "error" for r in res)
    warns = len(res) - errs
    print(f"{errs} error(s), {warns} warning(s)")
    return 1 if errs or (a.strict and warns) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
