#!/usr/bin/env python3
"""data-to-godot: write a Godot 4 Resource `.tres` plus a small script from a CSV or JSON table.

The script extends Resource and exports `columns` (PackedStringArray) and
`rows` (Array of Dictionary). CSV uses the header row as keys. JSON may be
an array of objects, `{"rows":[...]}`, or a `{id: object}` map (the key is
stored as `id`). Cell types are inferred (int, float, bool, string). The
input is never overwritten unless `--in-place`.
"""
from __future__ import annotations

import argparse, json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import godot_text  # noqa: E402

SCRIPT = (
    "extends Resource\n"
    "\n"
    "@export var columns: PackedStringArray\n"
    "@export var rows: Array[Dictionary]\n"
)


def infer(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return float(value)
    s = str(value).strip()
    if s == "":
        return ""
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    body = s[1:] if s[:1] in "+-" else s
    if body.isdigit():
        try:
            return int(s)
        except ValueError:
            pass
    if any(ch in s for ch in ".eE"):
        try:
            return float(s)
        except ValueError:
            pass
    return s


def load_table(path):
    low = path.lower()
    if low.endswith((".json", ".jsn")):
        doc = gst_read.load_json(path, "data table")
        if isinstance(doc, list):
            rows = []
            for i, it in enumerate(doc):
                if not isinstance(it, dict):
                    raise GstInputError("JSON row %d is not an object" % i)
                rows.append({str(k): v for k, v in it.items()})
            return rows
        doc = gst_read.require_object(doc, "data table")
        if isinstance(doc.get("rows"), list):
            rows = []
            for i, it in enumerate(doc["rows"]):
                if not isinstance(it, dict):
                    raise GstInputError("JSON rows[%d] is not an object" % i)
                rows.append({str(k): v for k, v in it.items()})
            return rows
        rows = []
        for key, it in doc.items():
            if key == "columns":
                continue
            if not isinstance(it, dict):
                raise GstInputError("JSON value for %r is not an object" % key)
            rec = {"id": key}
            rec.update({str(k): v for k, v in it.items()})
            rows.append(rec)
        if not rows:
            raise GstInputError("JSON data table is empty")
        return rows
    rows, cols = gst_read.load_loc_csv(path)
    out = []
    for r in rows:
        out.append({c: r.get(c) or "" for c in cols})
    return out


def columns_of(rows):
    seen, cols = set(), []
    for r in rows:
        for k in r:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    return cols


def write_script(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write(SCRIPT)


def write_tres(path, script_res, columns, rows):
    packed = "PackedStringArray(" + ", ".join(godot_text.string(c) for c in columns) + ")"
    dicts = []
    for r in rows:
        typed = {k: infer(r.get(k)) for k in columns}
        dicts.append(godot_text.literal(typed))
    arr = "Array[Dictionary]([%s])" % ", ".join(dicts)
    lines = [
        '[gd_resource type="Resource" load_steps=2 format=3]',
        "",
        '[ext_resource type="Script" path="%s" id="1_script"]' % script_res,
        "",
        "[resource]",
        'script = ExtResource("1_script")',
        "columns = %s" % packed,
        "rows = %s" % arr,
        "",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 Resource .tres plus script from a CSV or JSON table.")
    ap.add_argument("table")
    ap.add_argument("-o", "--out", required=True, help="output .tres")
    ap.add_argument("--script", help="output .gd path (default: <out stem>.gd)")
    ap.add_argument("--res", default="res://", help="res:// path or prefix for the script")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    script_path = a.script or (os.path.splitext(a.out)[0] + ".gd")
    safe_out.check(a.table, a.out, a.in_place)
    safe_out.check(a.table, script_path, a.in_place)
    if a.json:
        safe_out.check(a.table, a.json, a.in_place)
    rows = load_table(a.table)
    if not rows:
        raise GstInputError("data table is empty")
    cols = columns_of(rows)
    write_script(script_path)
    if a.res.startswith("res://") and a.res.lower().endswith(".gd"):
        script_res = a.res
    else:
        script_res = godot_text.res_path(a.res, os.path.basename(script_path))
    write_tres(a.out, script_res, cols, rows)
    rec = {"out": a.out, "script": script_path, "script_res": script_res,
           "rows": len(rows), "columns": cols}
    print("%d row(s), %d column(s) -> %s" % (len(rows), len(cols), a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
