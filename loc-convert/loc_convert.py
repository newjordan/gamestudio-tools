#!/usr/bin/env python3
"""loc-convert: move localisation strings between the CSV used by this kit (id, <source lang>, <langs>...) and
other formats: gettext PO/POT (msgctxt = id, msgid = source text, msgstr = translation; works with Weblate,
Poedit, Godot), JSON per language (flat, or nested when ids contain dots), and XLIFF 1.2 per target language.
from-po merges translated .po files back into a CSV. Escapes, quotes, newlines, multi-line PO strings and
unicode round-trip.
"""
import argparse, os, csv, json, re, sys


def read_csv(path):
    rows = list(csv.DictReader(open(path, newline="", encoding="utf-8")))
    cols = list(rows[0].keys()) if rows else []
    return rows, cols


def po_quote(s):
    s = s.replace("\\", "\\\\").replace('"', '\\"').replace("\t", "\\t").replace("\r", "\\r")
    parts = s.split("\n")
    if len(parts) == 1: return f'"{s}"'
    lines = [p + "\\n" for p in parts[:-1]] + ([parts[-1]] if parts[-1] else [])      # gettext multi-line form
    return '""\n' + "\n".join(f'"{l}"' for l in lines)


def po_unquote(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            n = s[i + 1]; out.append({"n": "\n", "t": "\t", "r": "\r", '"': '"', "\\": "\\"}.get(n, n)); i += 2
        else: out.append(c); i += 1
    return "".join(out)


def write_po(rows, src, lang=None, path=None):
    head = f'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Content-Transfer-Encoding: 8bit\\n"\n' + (f'"Language: {lang}\\n"\n' if lang else "")
    body = []
    for r in rows:
        tr = r.get(lang, "") if lang else ""
        body.append(f'#: {r["id"]}\nmsgctxt {po_quote(r["id"])}\nmsgid {po_quote(r[src])}\nmsgstr {po_quote(tr)}\n')
    text = head + "\n" + "\n".join(body)
    if path: open(path, "w", encoding="utf-8", newline="\n").write(text)
    return text


def parse_po(text):
    entries, cur, field = [], {}, None
    flush = lambda: (entries.append(cur.copy()) if "msgid" in cur else None)
    for line in text.splitlines():
        line = line.strip()
        if not line: flush(); cur, field = {}, None; continue
        if line.startswith("#,"): cur["flags"] = line[2:].strip(); continue
        if line.startswith("#"): continue
        m = re.match(r'^(msgctxt|msgid|msgstr)\s+"(.*)"$', line)
        if m: field = m.group(1); cur[field] = po_unquote(m.group(2)); continue
        if line.startswith('"') and field: cur[field] += po_unquote(line[1:-1])
    flush()
    return [e for e in entries if e.get("msgid") != "" or "msgctxt" in e]


def from_po(paths_by_lang, base_rows=None, src="en"):
    rows = {r["id"]: dict(r) for r in (base_rows or [])}
    for lang, p in paths_by_lang.items():
        for e in parse_po(open(p, encoding="utf-8").read()):
            i = e.get("msgctxt") or e["msgid"]
            r = rows.setdefault(i, {"id": i, src: e["msgid"]}); r[lang] = e.get("msgstr", "")
    langs = sorted({k for r in rows.values() for k in r if k not in ("id", src)})
    return [{"id": i, src: r.get(src, ""), **{l: r.get(l, "") for l in langs}} for i, r in rows.items()], langs


def to_json(rows, lang, nested=False):
    flat = {r["id"]: r.get(lang, "") for r in rows}
    if not nested: return flat
    out = {}
    for k, v in flat.items():
        d = out; parts = k.split(".")
        for p in parts[:-1]:
            d = d.setdefault(p, {})
            if not isinstance(d, dict): raise SystemExit(f"id {k!r} collides with a string at {p!r}")
        if parts[-1] in d and isinstance(d[parts[-1]], dict): raise SystemExit(f"id {k!r} collides with a nested group")
        d[parts[-1]] = v
    return out


def esc(s): return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def to_xliff(rows, src, lang):
    u = "\n".join(f'      <trans-unit id="{esc(r["id"])}"><source>{esc(r[src])}</source><target{"" if r.get(lang) else " state=\"new\""}>{esc(r.get(lang, ""))}</target></trans-unit>' for r in rows)
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<xliff version="1.2" xmlns="urn:oasis:names:tc:xliff:document:1.2">\n  <file original="strings" source-language="{src}" target-language="{lang}" datatype="plaintext">\n    <body>\n{u}\n    </body>\n  </file>\n</xliff>\n'


def main(argv=None):
    ap = argparse.ArgumentParser(description="Strings CSV <-> PO / JSON / XLIFF.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("to-po", "to-json", "to-xliff"):
        s = sub.add_parser(n); s.add_argument("csv"); s.add_argument("--src", default=None, help="source language column (default: second column)"); s.add_argument("-o", "--outdir", required=True); s.add_argument("--langs")
        if n == "to-json": s.add_argument("--nested", action="store_true")
    s = sub.add_parser("from-po"); s.add_argument("po", nargs="+", help="files named <lang>.po"); s.add_argument("-o", "--out", required=True); s.add_argument("--src", default="en"); s.add_argument("--base")
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
    _src_keys = ('po', 'csv')
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

    if a.cmd == "from-po":
        base = read_csv(a.base)[0] if a.base else None
        rows, langs = from_po({os.path.splitext(os.path.basename(p))[0]: p for p in a.po}, base, a.src)
        with open(a.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", a.src] + langs); w.writeheader(); w.writerows(rows)
        print(f"{len(rows)} string(s), languages {langs} -> {a.out}"); return 0
    rows, cols = read_csv(a.csv); src = a.src or cols[1]; langs = a.langs.split(",") if a.langs else [c for c in cols[1:] if c != src]
    os.makedirs(a.outdir, exist_ok=True)
    if a.cmd == "to-po":
        write_po(rows, src, None, os.path.join(a.outdir, "template.pot"))
        for l in langs: write_po(rows, src, l, os.path.join(a.outdir, f"{l}.po"))
    elif a.cmd == "to-json":
        for l in langs + [src]: json.dump(to_json(rows, l, a.nested), open(os.path.join(a.outdir, f"{l}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    else:
        for l in langs: open(os.path.join(a.outdir, f"{l}.xlf"), "w", encoding="utf-8").write(to_xliff(rows, src, l))
    print(f"{len(rows)} string(s), {a.cmd} for {langs} -> {a.outdir}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
