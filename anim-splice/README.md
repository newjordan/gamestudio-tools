# anim-splice

Extract a frame range from an anim-meta clip (`--from` inclusive, `--to` exclusive) or concatenate named clips (`--concat walk,idle`) into a new clip. Matching duration lists are sliced or joined the same way. `--only` writes a file that contains just the new clip.

## Usage

```bash
python3 anim-splice/anim_splice.py clips.json -o out.json --clip walk --from 2 --to 5 --pretty
python3 anim-splice/anim_splice.py clips.json -o out.json --concat walk,idle --name combo --only
```

Run `python3 anim-splice/anim_splice.py --help` (or `gst anim-splice --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Overlapping or reversed ranges are refused. Concatenation drops a duration list if any source clip is missing that key. Nested clip folders are not supported.

## Tests

`python3 -m pytest -q tests/test_batch20.py`
