# fleet-jobs

WRITE job-spec JSON for fleet models already on turbo: Qwen-Image 2.1 sprite batches, MiniMax Music cue sheets, H3 video shots or turntables, plus a validator. Never launches, connects, downloads or schedules anything.

## Usage

```bash
python3 fleet-jobs/fleet_jobs.py qwen-image prompts.csv --style "pixel art, flat colours" --variants 3 -o jobs/sprites.json
python3 fleet-jobs/fleet_jobs.py minimax-music cues.csv -o jobs/music.json
python3 fleet-jobs/fleet_jobs.py h3-video --turntable treasure_chest -o jobs/turntable.json
python3 fleet-jobs/fleet_jobs.py validate jobs/*.json
```

Run `python3 fleet-jobs/fleet_jobs.py --help` for every option. Requires Python 3.10+ with Pillow and numpy.

## Inspiration (catalogue entry)

Fleet plan: Qwen-Image 2.1, MiniMax Music and H3 video are the local models already on the fleet. GPU work goes on turbo only, never sparky or atlas.

## Source and licence

Original code. The job schema (`omnispace.fleet-job/1`) is our own convention, not any model's native API. The module has no network/subprocess/ssh imports (a test enforces this). Jobs are `queued-not-launched` until a person starts them.

Part of gamestudio-tools, custom-built for the game studio project. CPU only, no models, no network. The project licence is MIT; see LICENSE (Copyright 2026 Jordan Newman / OmniSpace Technologies LLC).

## Tests

`python3 -m pytest -q tests`
