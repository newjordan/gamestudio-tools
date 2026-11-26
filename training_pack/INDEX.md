# training_pack (gamestudio-tools 2.5.0, built on 7f6ae09)

| Path | What |
|---|---|
| `bugfix_transcripts/bugfix_transcripts.jsonl` | 6 worked bug-fix transcripts, one JSON record per bug: symptom, repro + real output on 2.4.0, investigation (file:line), root cause, git diff, regression test, test output on 2.4.0 (fail) and 2.5.0 (pass), repro on 2.5.0, measured notes |
| `bugfix_transcripts/bugfix_transcripts.md` | the same transcripts, readable |
| `bugfix_transcripts/repro/bug*.sh` | repro scripts (`GST_ROOT=<kit> bash bugN.sh`) |
| `bugfix_transcripts/runs/`, `diffs/` | raw measured outputs and `git diff f750fe6 7f6ae09 -- <file>` |
| `bugfix_transcripts/rerun.sh`, `make_transcripts.py` | re-measure (needs a 2.4.0 worktree at /tmp/gst240 and GODOT_BIN) and rebuild the JSONL/MD |
| `build/build.sh` | verbatim copy of `examples/sample-topdown/build.sh` |
| `build/build.annotated.sh` | same script plus a `# [gst <tool>] produces ...` line above each of its 121 gst calls (86 tools); comments only (`annotate.py` regenerates it) |
| `build/verify_result.txt` | the `build.sh --verify` run |
| `eval/` | independent eval: `cases.py` (source of truth) / `cases.jsonl` (148 cases, 113 tools: prompt, command, checks), `fixtures.py`, `run_eval.py` (`python3 run_eval.py [--only ID] [-v]`), `results.json`, `found_bugs.jsonl` |

The eval was written from `gst help`, `gst info`, tool READMEs, the sample's data files and observed CLI output. No tool `.py` was read for it. The only kit source seen while building this pack was the six 2.5.0 fix diffs used in the transcripts.
