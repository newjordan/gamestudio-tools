# VO script to slate to trim to loudness

Extract spoken lines from a Yarn script, build a per-speaker recording slate, then (once takes are
on disk, named after the slate targets) strip DC, trim silence, and apply a target loudness.

## Tools

dialogue-extract → voice-slate → wav-dc-remove → wav-trim → wav-silence → wav-gate → wav-limit → wav-resample → wav-mono → wav-invert → wav-gain → wav-loud-apply / sfx-normalize --lufs → wav-chan-swap → wav-fade → wav-pad → (optional sfx-reverse / wav-loop-snap)

## Commands

```bash
mkdir -p /tmp/pipe-vo/takes
gst dialogue-extract samples/pipelines/vo/intro.yarn -o /tmp/pipe-vo/lines.csv
gst voice-slate /tmp/pipe-vo/lines.csv -o /tmp/pipe-vo/slate
# After the session, drop recorded WAVs into takes/ using the `target` names in the slate CSVs, then:
gst wav-dc-remove /tmp/pipe-vo/takes -o /tmp/pipe-vo/dc
gst wav-trim /tmp/pipe-vo/dc -o /tmp/pipe-vo/trim
# optional: gst wav-resample /tmp/pipe-vo/trim --outdir /tmp/pipe-vo/sr --rate 48000
# optional: gst wav-mono /tmp/pipe-vo/trim --outdir /tmp/pipe-vo/mono --mode mix
# optional: gst wav-invert /tmp/pipe-vo/trim/take.wav -o /tmp/pipe-vo/inv/take.wav
# optional: gst wav-silence /tmp/pipe-vo/trim/take.wav -o /tmp/pipe-vo/padded.wav --at 0 --duration 0.25
# optional: gst wav-gate /tmp/pipe-vo/padded.wav -o /tmp/pipe-vo/gated.wav --thresh-db -40
# optional: gst wav-limit /tmp/pipe-vo/gated.wav -o /tmp/pipe-vo/limited.wav --ceiling-db -0.1
# optional: gst wav-gain /tmp/pipe-vo/trim --outdir /tmp/pipe-vo/gain --gain -3 --max-true-peak -1.0
gst wav-loud-apply /tmp/pipe-vo/trim -o /tmp/pipe-vo/loud --target -16 --json /tmp/pipe-vo/loud.json
# or: gst sfx-normalize /tmp/pipe-vo/trim --outdir /tmp/pipe-vo/loud --lufs -16 --max-true-peak -1
# optional per-take fade and pad to a slate length:
# gst wav-fade /tmp/pipe-vo/loud/ava_l1.wav -o /tmp/pipe-vo/faded/ava_l1.wav --in 0.01 --fade-out 0.05
# gst wav-pad  /tmp/pipe-vo/faded/ava_l1.wav -o /tmp/pipe-vo/padded/ava_l1.wav --to-duration 1.0
```

The integration test synthesises the takes so the second half of the chain can run without a studio
session. LUFS uses the same uncertified ITU-R BS.1770-4 meter as wav-batch-meta.

## Known gaps

The meter is not certified. PCM WAV only; other RIFF chunks are dropped by the WAV writers. Voice
slate estimates are a words-per-second guess, not a performance.
