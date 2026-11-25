# tmx-props-lint

Check that Tiled objects carry required custom properties of the expected types. The schema is a JSON file keyed by object type (`*` is a default). Exit 1 when anything is missing or mistyped, for CI. Encoded maps are decoded. Reports text, JSON or Markdown.

## Usage

```bash
python3 tmx-props-lint/tmx_props_lint.py maps/*.json --schema props.schema.json --json lint.json
```

Example schema:

```json
{"objects": {"enemy": {"required": ["hp", "speed"], "types": {"hp": "int", "speed": "float"}}}}
```

Run `python3 tmx-props-lint/tmx_props_lint.py --help` (or `gst tmx-props-lint --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new). Complements asset-lint, tmx-objects-csv and loc-placeholder-lint.

## Source and licence

Original code. Layer-level rules are not applied (only objects). Property types follow Tiled's JSON (`int`, `float`, `bool`, `string`, `color`, `file`, `object`).

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
