# font-to-godot

Write a Godot 4 Theme `.tres` that uses an AngelCode BMFont `.fnt` as its default font. Godot's BMFont importer loads the `.fnt` as a FontFile. Optional `--copy-dir` copies the font and its page image(s).

Three BMFont encodings are accepted and detected from the file itself:

| Format | Detected by | What happens |
| --- | --- | --- |
| text (bmfont-gen, BMFont tool default) | starts with `info ` | used as is |
| binary version 3 | starts with `BMF` and version byte 3 | used as is (Godot 4.7.2 imports it and applies its kerning) |
| XML | root element `<font>` | **converted to a text `.fnt`** named `<stem>_text.fnt`, because Godot 4.7.2's importer does not read XML (checked: an XML `.fnt` loads as an empty font) |

The converted copy is written into `--copy-dir`, or next to the Theme when there is none, and the Theme points at it. Every attribute is kept, including kerning pairs. Multi-page fonts are checked and copied page by page. Binary versions other than 3 are refused with a one-line error. Every glyph rectangle is checked against its page image (see Known gaps for the exact rule).

## Usage

```bash
python3 font-to-godot/font_to_godot.py label.fnt -o ui_theme.tres --copy-dir ./fonts --res res://fonts/
```

Run `python3 font-to-godot/font_to_godot.py --help` (or `gst font-to-godot --help`) for every option. Requires Python 3.10+. Optional Godot verification uses `GODOT_BIN`.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Binary BMFont versions 1 and 2 are refused. Glyph rectangles are checked against the real size of each page image (not just the declared `scaleW`/`scaleH`): a negative rectangle, one that passes the page edge (touching it is fine), or a glyph on an undeclared page is refused with `BMFont glyph check failed: glyph id N ...`, and nothing is written. A declared scale that differs from the image is only reported (`scale_note` in `--json` and on the summary line). Overlapping glyph rectangles and glyphs with width or height 0 are accepted. The Theme only sets default_font / default_font_size; no per-control overrides. Godot still has to import the `.fnt` inside a project (a `.import` sidecar is not written, because dest_files hashes are Godot's to assign).

## Tests

`python3 -m pytest -q tests/test_batch32.py tests/test_v21.py`
