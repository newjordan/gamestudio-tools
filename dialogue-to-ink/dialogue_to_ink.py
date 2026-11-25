#!/usr/bin/env python3
"""dialogue-to-ink: rebuild an ink script from a dialogue-extract CSV, keeping knot names (from the node column),
#line: ids, choice stars and leftover tags. Speakers become `Name: text` prefixes. Optional --speakers map rewrites
names. Writes one .ink (or one file per source with --split). The input CSV is never overwritten.
"""
import argparse, os, csv, json, sys
from collections import OrderedDict


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows: sys.exit("CSV is empty")
    need = {"id", "text", "node"}
    missing = need - set(rows[0])
    if missing: sys.exit("CSV missing column(s): " + ", ".join(sorted(missing)))
    return rows


def load_speakers(path):
    if not path: return {}
    if path.lower().endswith(".json"):
        return {str(k): str(v) for k, v in json.load(open(path, encoding="utf-8")).items()}
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            src = r.get("from") or r.get("speaker") or r.get("old")
            dst = r.get("to") or r.get("name") or r.get("new")
            if src: out[src] = dst or src
    return out


def knot_name(node):
    s = "".join(ch if ch.isalnum() or ch in "._" else "_" for ch in (node or "root").strip()) or "root"
    if s[0].isdigit(): s = "_" + s
    return s


def line_text(row, speakers):
    text = (row.get("text") or "").strip()
    speaker = speakers.get((row.get("speaker") or "").strip(), (row.get("speaker") or "").strip())
    tags = (row.get("tags") or "").strip()
    lid = (row.get("id") or "").strip()
    kind = (row.get("kind") or "line").strip().lower()
    body = f"{speaker}: {text}" if speaker and kind != "choice" else text
    bits = [f"* {body}" if kind == "choice" else body]
    if lid: bits.append(f"#line:{lid}")
    if tags:
        for t in tags.split():
            if t.startswith("line:"): continue
            bits.append("#" + t.lstrip("#"))
    return " ".join(bits)


def build(rows, speakers):
    groups = OrderedDict()
    for r in rows:
        node = (r.get("node") or "root").strip() or "root"
        src = (r.get("file") or "").strip()
        groups.setdefault((src, node), []).append(r)
    blocks = []
    for (src, node), rs in groups.items():
        body = "\n".join(line_text(r, speakers) for r in rs)
        blocks.append({"file": src, "node": node, "text": f"=== {knot_name(node)} ===\n{body}\n"})
    return blocks


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rebuild an ink script from a dialogue-extract CSV.")
    ap.add_argument("csv"); ap.add_argument("-o", "--out")
    ap.add_argument("--split", metavar="DIR")
    ap.add_argument("--speakers")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    if not a.out and not a.split: sys.exit("pass -o or --split")
    if a.out and os.path.abspath(a.out) == os.path.abspath(a.csv):
        sys.exit("refusing to overwrite the input CSV; pick a different -o or pass --in-place")
    blocks = build(load_rows(a.csv), load_speakers(a.speakers))
    if a.split:
        os.makedirs(a.split, exist_ok=True)
        by_file = OrderedDict()
        for b in blocks:
            key = b["file"] or "dialogue.ink"
            by_file.setdefault(key, []).append(b["text"])
        n = 0
        for src, texts in by_file.items():
            name = os.path.splitext(os.path.basename(src))[0] + ".ink"
            open(os.path.join(a.split, name), "w", encoding="utf-8").write("\n".join(texts) + "\n")
            n += 1
        print(f"{len(blocks)} knot(s) in {n} file(s) -> {a.split}")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8").write("\n".join(b["text"] for b in blocks) + "\n")
        print(f"{len(blocks)} knot(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
