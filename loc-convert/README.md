# loc-convert

Convert the strings CSV used by this kit to and from gettext PO/POT (msgctxt = id), per-language JSON (flat or nested), and XLIFF 1.2; merge translated .po files back into a CSV. Escapes, newlines, quotes and unicode round-trip.

## Usage

```bash
python3 loc-convert/loc_convert.py to-po strings.csv -o po/
python3 loc-convert/loc_convert.py to-json strings.csv -o json/ --nested
python3 loc-convert/loc_convert.py to-xliff strings.csv -o xliff/
python3 loc-convert/loc_convert.py from-po po/fr.po po/de.po -o merged.csv --src en
```

Run `python3 loc-convert/loc_convert.py --help` (or `gst loc-convert --help`) for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Weblate (translation platform; consumes PO and XLIFF).

## Source and licence

Original code from the public gettext PO and XLIFF 1.2 specs. Plural forms and PO comments beyond flags are not carried; fuzzy flags are read but not preserved on write.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
