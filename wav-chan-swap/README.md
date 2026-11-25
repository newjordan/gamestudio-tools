# wav-chan-swap

Swap or reorder channels in a multi-channel WAV. `--swap` flips the first two channels (typical stereo L/R). `--order` is a comma list of 0-based indices or of labels `L,R,C,LFE,Ls,Rs,Lb,Rb` (the same names as wav-chan-split). `smpl` loop markers are preserved. The input is never overwritten unless `--in-place`.

## Usage

```bash
python3 wav-chan-swap/wav_chan_swap.py stereo.wav -o swapped.wav --swap
python3 wav-chan-swap/wav_chan_swap.py quad.wav -o out.wav --order 2,3,0,1
```

Run `python3 wav-chan-swap/wav_chan_swap.py --help` (or `gst wav-chan-swap --help`) for every option. Requires Python 3.10+ (numpy; PCM via audio-tidy).

## Inspiration (catalogue entry)

None (new).

## Source and licence

Original code. Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Known gaps

PCM only; other RIFF chunks except a restored `smpl` loop are dropped by audio-tidy. `--order` must be a permutation of every channel (channels cannot be dropped or duplicated).

## Tests

`python3 -m pytest -q tests/test_batch24.py`
