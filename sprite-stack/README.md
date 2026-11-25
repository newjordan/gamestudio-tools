# sprite-stack

Composite named layers (shadow, body, outline, fx, ...) into one sprite per stem. Inputs are `{stem}.{layer}.png` in one folder or `{layer}/{stem}.png`. Frames of different sizes share a max-size canvas and are aligned by `--anchor`.

## Usage

```bash
python3 sprite-stack/sprite_stack.py parts -o stacked --layers shadow,body,outline --layout dotted
```

Run `python3 sprite-stack/sprite_stack.py --help` (or `gst sprite-stack --help`) for every option. Requires Python 3.10+.

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

Blend mode is plain alpha composite (no multiply/add). Layer names cannot contain dots when using the dotted layout because the suffix is `.{layer}`. Different colour spaces / bit depths are converted to RGBA8.

## Tests

`python3 -m pytest -q tests/test_batch21.py`
