# Loc missing, placeholders, check

A CI-friendly localisation pass: fail if a source-language string is blank in another language,
if `{placeholders}` do not match, if loc-check finds duplicates / overflow / untranslated copies, or if ICU / suffix plurals are incomplete.

## Tools

loc-merge → loc-rename → loc-split → loc-join → loc-stats → loc-diff → loc-fill → loc-missing → loc-placeholder-lint → loc-check → loc-plurals → loc-icu-extract → loc-sort → loc-key-lint

## Commands

```bash
# optional: merge two language tables first, rename keys, or diff against a previous export:
# gst loc-merge a.csv b.csv -o /tmp/pipe-loc/strings.csv --no-fail
# gst loc-rename /tmp/pipe-loc/strings.csv -o /tmp/pipe-loc/renamed.csv --map old=new
# gst loc-diff previous.csv /tmp/pipe-loc/renamed.csv --no-fail
# gst loc-split /tmp/pipe-loc/renamed.csv -o /tmp/pipe-loc/langs
# gst loc-join /tmp/pipe-loc/langs -o /tmp/pipe-loc/joined.csv
# gst loc-stats /tmp/pipe-loc/joined.csv --json /tmp/pipe-loc/stats.json
# gst loc-fill /tmp/pipe-loc/joined.csv -o /tmp/pipe-loc/filled.csv --source en --fail-if-empty

# a complete table should exit 0 from all three:
gst loc-missing samples/pipelines/loc/strings.csv
gst loc-placeholder-lint samples/pipelines/loc/strings.csv
gst loc-check samples/pipelines/loc/strings.csv --source en
gst loc-plurals samples/pipelines/loc/strings.csv
gst loc-icu-extract samples/pipelines/loc/strings.csv -o /tmp/pipe-loc/icu.csv
gst loc-sort samples/pipelines/loc/strings.csv -o /tmp/pipe-loc/strings_sorted.csv --no-fail

# a table with a missing French cell exits 1 from loc-missing:
gst loc-missing samples/pipelines/loc/strings_gap.csv; echo $?   # 1
```

`--no-fail` on loc-missing prints the report without failing CI. loc-check also reports missing
translations; loc-missing is the focused, scriptable list.

## Known gaps

Length overflow uses the same
ratio heuristics as loc-check (with a separate CJK ratio).
