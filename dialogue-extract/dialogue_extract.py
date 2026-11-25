#!/usr/bin/env python3
"""dialogue-extract: pull spoken lines out of Yarn Spinner (.yarn) and ink (.ink) scripts into a
VO / localisation spreadsheet (CSV): stable line id, file, node/knot, speaker, text, tags, word count,
and an estimated VO duration. Existing `#line:` ids are kept; missing ones are generated
deterministically (hash of file+node+text) and can be written back with --tag-in-place.

Formats per the public Yarn Spinner (MIT) and inkle ink (MIT) syntax docs; no code from either.
"""
import argparse, csv, glob, hashlib, os, re
import os, sys

SPEAKER = re.compile(r"^([A-Za-z0-9_ .'-]{1,40}):\s+(.*)$")
LINE_TAG = re.compile(r"#line:([A-Za-z0-9_]+)")
TAG = re.compile(r"#([A-Za-z0-9_:.-]+)")


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def gen_id(file, node, text):
    return "L" + hashlib.sha1(f"{os.path.basename(file)}|{node}|{text}".encode()).hexdigest()[:8]


def clean(text):
    text = re.sub(r"\{[^}]*\}", "", text)          # inline expressions {$x}
    text = re.sub(r"\[/?[^\]]*\]", "", text)       # yarn markup [b] / ink choice brackets
    text = re.sub(r"<>", "", text)                 # ink glue
    return re.sub(r"\s+", " ", text).strip()


def parse_yarn(path):
    rows, node, in_body = [], None, False
    lines = gst_read.open_text(path).splitlines()
    for i, raw in enumerate(lines):
        s = raw.strip()
        if s.startswith("title:") and not in_body:
            node = s.split(":", 1)[1].strip()
            continue
        if s == "---":
            in_body = True
            continue
        if s == "===":
            in_body = False
            continue
        if not in_body or not s or s.startswith("//") or s.startswith("<<"):
            continue
        is_choice = s.startswith("->")
        body = s[2:].strip() if is_choice else s
        rows.append(_row(path, node, body, i, "choice" if is_choice else "line"))
    return [r for r in rows if r]


def parse_ink(path):
    rows, knot = [], "root"
    lines = gst_read.open_text(path).splitlines()
    in_comment = False
    for i, raw in enumerate(lines):
        s = raw.strip()
        if in_comment:
            if "*/" in s:
                in_comment = False
            continue
        if s.startswith("/*"):
            in_comment = "*/" not in s
            continue
        if not s or s.startswith("//") or s.startswith(("VAR ", "CONST ", "INCLUDE ", "EXTERNAL ", "~", "->", "TODO")):
            continue
        m = re.match(r"^={2,}\s*(\w+)", s)
        if m:
            knot = m.group(1)
            continue
        m = re.match(r"^=\s*(\w+)", s)
        if m:
            knot = knot.split(".")[0] + "." + m.group(1)
            continue
        kind = "line"
        m = re.match(r"^([*+]+)\s*(.*)$", s)
        if m:
            kind, s = "choice", m.group(2)
        s = re.sub(r"^-+\s*", "", s)            # gathers
        s = re.sub(r"^\([\w]+\)\s*", "", s)     # labels
        s = s.split("->")[0].strip()
        if s:
            rows.append(_row(path, knot, s, i, kind))
    return [r for r in rows if r]


def _row(path, node, body, lineno, kind):
    tags = TAG.findall(body)
    lid = LINE_TAG.search(body)
    text = TAG.sub("", body).strip()
    speaker = ""
    m = SPEAKER.match(text)
    if m:
        speaker, text = m.group(1).strip(), m.group(2)
    text = clean(text)
    if not text:
        return None
    words = len(text.split())
    return {"id": lid.group(1) if lid else gen_id(path, node, text), "has_id": bool(lid), "file": os.path.basename(path),
            "line": lineno + 1, "node": node or "", "kind": kind, "speaker": speaker, "text": text,
            "tags": " ".join(t for t in tags if not t.startswith("line:")), "words": words,
            "est_seconds": round(max(0.8, words / 2.5), 1)}


def tag_in_place(path, rows):
    lines = gst_read.open_text(path).splitlines()
    for r in rows:
        if not r["has_id"]:
            lines[r["line"] - 1] = lines[r["line"] - 1].rstrip() + f" #line:{r['id']}"
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Extract Yarn/ink lines to a VO/loc CSV.")
    ap.add_argument("inputs", nargs="+", help="files or globs (.yarn, .ink)")
    ap.add_argument("-o", "--out", default="lines.csv")
    ap.add_argument("--tag-in-place", action="store_true", help="append generated #line: ids to source files")
    ap.add_argument("--speaker", help="only lines by this speaker (VO script per actor)")
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
    _src_keys = ('inputs',)
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

    files = [f for p in a.inputs for f in (sorted(glob.glob(p)) or [p])]
    rows = []
    for f in files:
        rs = parse_yarn(f) if f.endswith(".yarn") else parse_ink(f) if f.endswith(".ink") else []
        if a.tag_in_place:
            tag_in_place(f, rs)
        rows.extend(rs)
    if a.speaker:
        rows = [r for r in rows if r["speaker"].lower() == a.speaker.lower()]
    cols = ["id", "file", "line", "node", "kind", "speaker", "text", "tags", "words", "est_seconds"]
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    spk = sorted({r["speaker"] for r in rows if r["speaker"]})
    print(f"{len(rows)} lines from {len(files)} file(s), {len(spk)} speaker(s), "
          f"~{round(sum(r['est_seconds'] for r in rows)/60,1)} min VO -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
