# wav-loud-apply

Apply a uniform gain so a WAV hits a target integrated LUFS, capped so the true peak stays under a ceiling. Uses wav-batch-meta's meter (ITU-R BS.1770-4, not certified). Files shorter than 400 ms use the same un-gated whole-file reading and are flagged short. Does not overwrite inputs. `--dry-run` reports the planned gain only.

## Usage

```bash
python3 wav-loud-apply/wav_loud_apply.py music/*.wav --outdir normalised/ --target -16 --max-true-peak -1 --json gain.json
python3 wav-loud-apply/wav_loud_apply.py vo/line.wav --suffix _loud --target -18 --dry-run
```

Run `python3 wav-loud-apply/wav_loud_apply.py --help` (or `gst wav-loud-apply --help`) for every option. Requires Python 3.10+ with numpy.

## Inspiration (catalogue entry)

None (new). Complements wav-batch-meta (which suggests a gain but does not write a file).

## Source and licence

Original code. Same meter limits as wav-batch-meta: not a certified meter, PCM integer WAV only, no surround weights.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests` (or `gst test`)
