#!/usr/bin/env python3
"""loc-to-godot: write a Godot 4 translation CSV from a kit localisation CSV.

Godot's importer treats the first column as the key and the header row as
locale names (see the Godot 4 Internationalizing games docs). The default
key column is `id`; every other column becomes a locale unless `--langs` is
given. Empty keys are skipped. Optional `--translation-dir` also writes one
Translation resource per locale: official `.translation` binaries when
GODOT_BIN or `--godot` can run a headless CSV import, otherwise a text
`.tres` of type Translation (verified to load in Godot 4.7.2). The input is
never overwritten unless `--in-place`.
"""
import argparse, csv, json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402
import godot_cli  # noqa: E402
import godot_text  # noqa: E402


def convert(rows, cols, key_col="id", langs=None, skip_empty=True):
    if key_col not in cols:
        raise GstInputError("key column %r not in %s" % (key_col, cols))
    if langs is None:
        langs = [c for c in cols if c != key_col]
    else:
        missing = [c for c in langs if c not in cols]
        if missing:
            raise GstInputError("locale column(s) not in CSV: %s" % ", ".join(missing))
    if not langs:
        raise GstInputError("no locale columns to export")
    out_rows, skipped, dupes = [], 0, 0
    seen = {}
    for r in rows:
        key = (r.get(key_col) or "").strip()
        if not key:
            skipped += 1
            continue
        if key in seen:
            dupes += 1
            continue
        seen[key] = True
        rec = [key] + [(r.get(lang) or "") for lang in langs]
        if skip_empty and not any(rec[1:]):
            skipped += 1
            continue
        out_rows.append(rec)
    header = ["keys"] + langs
    return header, out_rows, {"keys": len(out_rows), "locales": langs, "skipped": skipped, "duplicate_keys": dupes}


def write_translation_tres(path, locale, messages):
    """Write a text Translation .tres in the layout official Godot 4.7.2 saves."""
    lines = [
        '[gd_resource type="Translation" format=3]',
        "",
        "[resource]",
        "messages = {",
    ]
    items = list(messages.items())
    for i, (key, text) in enumerate(items):
        comma = "," if i < len(items) - 1 else ""
        lines.append("[&\"\", %s]: [%s]%s" % (godot_text.string_name(key), godot_text.string_name(text), comma))
    lines += [
        "}",
        "locale = %s" % godot_text.string(locale),
        "",
    ]
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    open(path, "w", encoding="utf-8").write("\n".join(lines))


def import_translations_with_godot(csv_text, stem, locales, dest_dir, godot):
    """Headless-import a Godot translation CSV and copy the .translation files."""
    tmp = tempfile.mkdtemp(prefix="gst-loc-import-")
    try:
        proj = os.path.join(tmp, "proj")
        os.makedirs(proj)
        open(os.path.join(proj, "project.godot"), "w").write(
            "config_version=5\n\n[application]\n\nconfig/name=\"gst-loc-import\"\n"
        )
        src = os.path.join(proj, stem + ".csv")
        open(src, "w", encoding="utf-8", newline="").write(csv_text)
        r = godot_cli.run(godot, proj, ["--import", "--quit"], timeout=120, home=os.path.join(tmp, "home"))
        out = r.stdout or ""
        if r.returncode not in (0, None):
            raise GstInputError("Godot CSV import failed (exit %s): %s" % (r.returncode, out[-500:]))
        written = []
        for loc in locales:
            name = "%s.%s.translation" % (stem, loc)
            src_p = os.path.join(proj, name)
            if not os.path.isfile(src_p):
                raise GstInputError(
                    "Godot did not write %s (import exit %s). Output: %s"
                    % (name, r.returncode, out[-500:])
                )
            dest = os.path.join(dest_dir, name)
            shutil.copy2(src_p, dest)
            written.append(dest)
        return written, "translation"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a Godot 4 translation CSV from a loc CSV.")
    ap.add_argument("csv")
    ap.add_argument("-o", "--out", required=True, help="output Godot translation CSV")
    ap.add_argument("--key", default="id", help="key column (default: id)")
    ap.add_argument("--langs", help="comma-separated locale columns (default: every column except the key)")
    ap.add_argument("--keep-empty", action="store_true", help="keep rows whose translations are all empty")
    ap.add_argument("--translation-dir", metavar="DIR",
                    help="also write one Translation resource per locale in DIR")
    ap.add_argument("--godot", help="Godot 4 editor for official .translation import (default: GODOT_BIN)")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.csv, a.out, a.in_place)
    if a.json:
        safe_out.check(a.csv, a.json, a.in_place)
    rows, cols = gst_read.load_loc_csv(a.csv)
    langs = [s.strip() for s in a.langs.split(",")] if a.langs else None
    header, out_rows, rec = convert(rows, cols, a.key, langs, skip_empty=not a.keep_empty)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    w.writerows(out_rows)
    csv_text = buf.getvalue()
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        fh.write(csv_text)
    rec["out"] = a.out
    rec["translations"] = []
    rec["translation_format"] = None
    if a.translation_dir:
        os.makedirs(a.translation_dir, exist_ok=True)
        for loc in rec["locales"]:
            safe_out.check(a.csv, os.path.join(a.translation_dir, loc + ".translation"), a.in_place)
            safe_out.check(a.csv, os.path.join(a.translation_dir, loc + ".tres"), a.in_place)
        stem = os.path.splitext(os.path.basename(a.out))[0]
        godot = godot_cli.find_godot(a.godot)
        if godot:
            paths, fmt = import_translations_with_godot(csv_text, stem, rec["locales"], a.translation_dir, godot)
            rec["translations"] = paths
            rec["translation_format"] = fmt
            rec["godot"] = godot
        else:
            paths = []
            for i, loc in enumerate(rec["locales"]):
                messages = {row[0]: row[i + 1] for row in out_rows}
                dest = os.path.join(a.translation_dir, "%s.%s.tres" % (stem, loc))
                write_translation_tres(dest, loc, messages)
                paths.append(dest)
            rec["translations"] = paths
            rec["translation_format"] = "tres"
        print("%d key(s), %d locale(s) -> %s + %d %s"
              % (rec["keys"], len(rec["locales"]), a.out, len(rec["translations"]),
                 "official .translation" if rec["translation_format"] == "translation" else "Translation .tres (set GODOT_BIN for official .translation)"))
    else:
        print("%d key(s), %d locale(s) -> %s" % (rec["keys"], len(rec["locales"]), a.out))
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
