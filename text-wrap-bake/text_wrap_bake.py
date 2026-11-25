#!/usr/bin/env python3
"""text-wrap-bake: pre-wrap localisation strings to a pixel width with a real font, and write the wrapped text back to a
CSV (newlines in the cells) so a simple in-game text renderer can draw them without measuring. Uses loc-fit's wrapper
(greedy word wrap, character wrap for CJK or a single word that is too wide). Limits: --width PX for every string, or a
limits CSV (id,max_px) with glob ids, as in loc-fit. By default markup tags are stripped and placeholders ({name}, %d)
are replaced with --placeholder before wrapping, and that visible text is what is written (the form a markup-unaware
renderer would show). --raw wraps the cell as stored, keeping tags and placeholders, and may mis-measure markup.
Strings that already fit are copied unchanged. Writes a new CSV (-o); the input is never overwritten. A JSON report lists
which cells changed and how many lines they became. Measuring uses Pillow's basic font metrics (see loc-fit).
"""
import argparse, os, csv, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "loc-fit"))
import loc_fit  # noqa: E402


def bake(rows, langs, font, limits, default, placeholder="0000", raw=False, id_col="id"):
    out, report = [], []
    for r in rows:
        nr = dict(r); sid = r.get(id_col, "")
        px, _ = loc_fit.limit_for(sid, limits, default, 1)
        for lang in langs:
            text = r.get(lang) or ""
            if not text or px is None: continue
            visible = text if raw else loc_fit.prepare(text, placeholder)
            w = loc_fit.measure(font, visible) if "\n" not in visible else max(loc_fit.measure(font, p) for p in visible.split("\n"))
            lines = loc_fit.wrap(font, visible, px) if (w > px or "\n" in visible) else [visible]
            baked = "\n".join(lines)
            if baked != text:
                nr[lang] = baked
                report.append({"id": sid, "lang": lang, "lines": len(lines), "width_px": round(w, 1), "limit_px": px, "changed": True})
        out.append(nr)
    return out, report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Pre-wrap localisation strings to a pixel width and write them back to a CSV.")
    ap.add_argument("csv"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--font", help="TTF/OTF (default: Pillow's built-in font)"); ap.add_argument("--size", type=int, default=16)
    ap.add_argument("--width", type=float, help="default pixel width for every string"); ap.add_argument("--limits", help="CSV: id,max_px (id may be a glob)")
    ap.add_argument("--langs", help="comma list (default: every column except id)"); ap.add_argument("--placeholder", default="0000")
    ap.add_argument("--raw", action="store_true"); ap.add_argument("--json")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    with open(a.csv, newline="", encoding="utf-8") as f: rd = csv.DictReader(f); rows = list(rd); cols = list(rd.fieldnames or [])
    if "id" not in cols: sys.exit("CSV needs an 'id' column")
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.csv): sys.exit("refusing to overwrite the input; pick a different -o or pass --in-place")
    langs = a.langs.split(",") if a.langs else [c for c in cols if c != "id"]
    limits = loc_fit.load_limits(a.limits)
    if not limits and a.width is None: sys.exit("give --width PX and/or --limits FILE")
    baked, report = bake(rows, langs, loc_fit.load_font(a.font, a.size), limits, a.width, a.placeholder, a.raw)
    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore", lineterminator="\n"); w.writeheader(); w.writerows(baked)
    print(f"{len(report)} cell(s) wrapped of {len(rows)} row(s) x {len(langs)} language(s) -> {a.out}")
    if a.json: json.dump(report, open(a.json, "w"), indent=1, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
