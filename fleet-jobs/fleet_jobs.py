#!/usr/bin/env python3
"""fleet-jobs: WRITE job-spec files for the fleet models that already live on turbo. It never launches,
connects, downloads or schedules anything. A person (or an approved routine) picks the files up later.

  qwen-image    sprite/concept prompts CSV -> Qwen-Image 2.1 batch job
  minimax-music cue sheet CSV              -> MiniMax Music job (loop-friendly cues flagged for loop-finder)
  h3-video      shots CSV, or --turntable   -> H3 video job
  validate      check job files: target must be turbo, status queued-not-launched, never sparky/atlas

The job schema ("omnispace.fleet-job/1") is our own convention, not the models' native API; a runner on
turbo maps it to the model's real inputs. This module has no network, subprocess or ssh imports (a test
enforces that), so building a job file can never touch a machine.
"""
import argparse, os, csv, hashlib, json, sys

SCHEMA = "omnispace.fleet-job/1"
TARGET = "turbo"
FORBIDDEN_HOSTS = {"sparky", "atlas"}
CONSTRAINTS = {"download_models": False, "huggingface_pull": False, "gpu_host": TARGET,
               "never_on": sorted(FORBIDDEN_HOSTS), "launch": "manual-approval-only"}


def jid(kind, items):
    return kind.split(".")[0] + "-" + hashlib.sha1(json.dumps(items, sort_keys=True).encode()).hexdigest()[:10]


def make_job(kind, model, items, out_dir, **extra):
    return {"schema": SCHEMA, "id": jid(kind, items), "kind": kind, "model": model, "target": TARGET,
            "status": "queued-not-launched", "constraints": dict(CONSTRAINTS), "outputs": {"dir": out_dir},
            "items": items, **extra}


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return [{k.strip().lower(): (v or "").strip() for k, v in r.items()} for r in csv.DictReader(f)]


def qwen_image(csv_path, out_dir, style="", negative="", size="1024x1024", variants=1, seed=1000):
    items = []
    for i, r in enumerate(rows(csv_path)):
        w, h = (r.get("size") or size).lower().split("x")
        for v in range(int(r.get("variants") or variants)):
            items.append({"name": f"{r['name']}_v{v + 1}", "prompt": ", ".join(p for p in (r["subject"], style) if p),
                          "negative_prompt": negative, "width": int(w), "height": int(h),
                          "seed": int(r["seed"]) + v if r.get("seed") else seed + i * 100 + v})
    return make_job("image.qwen-image", "Qwen-Image 2.1", items, out_dir, post=["pixelize", "palette-swap", "atlas-pack"])


def minimax_music(csv_path, out_dir, style=""):
    items = []
    for r in rows(csv_path):
        loop = (r.get("loop", "yes").lower() in ("yes", "y", "true", "1"))
        prompt = ", ".join(p for p in (r.get("mood"), f"{r['bpm']} bpm" if r.get("bpm") else "", r.get("notes"), style,
                                       "seamless loop, no fade-out ending" if loop else "") if p)
        items.append({"name": r["cue"], "prompt": prompt, "duration_s": float(r.get("length_s") or 60), "loop": loop})
    return make_job("audio.minimax-music", "MiniMax Music", items, out_dir, post=["loop-finder", "audio-tidy"])


def h3_video(out_dir, shots_csv=None, turntable=None, seconds=4.0, seed=7, style=""):
    if turntable:
        items = [{"name": f"{turntable}_orbit_{az:03d}", "prompt": ", ".join(p for p in (
                  f"{turntable}, studio turntable, camera orbit starting at {az} degrees, neutral backdrop", style) if p),
                  "duration_s": seconds, "seed": seed + i} for i, az in enumerate((0, 120, 240))]
    else:
        items = [{"name": r["shot"], "prompt": ", ".join(p for p in (r["prompt"], style) if p),
                  "duration_s": float(r.get("seconds") or seconds), "seed": int(r["seed"]) if r.get("seed") else seed + i}
                 for i, r in enumerate(rows(shots_csv))]
    return make_job("video.h3", "H3 video", items, out_dir)


def validate(job):
    errs = []
    if job.get("schema") != SCHEMA:
        errs.append("bad schema")
    if job.get("target") != TARGET:
        errs.append(f"target must be {TARGET}, got {job.get('target')!r}")
    if job.get("status") != "queued-not-launched":
        errs.append(f"status must be queued-not-launched, got {job.get('status')!r}")
    blob = json.dumps({k: job.get(k) for k in ("target", "host", "outputs", "model")}).lower()
    for h in FORBIDDEN_HOSTS:
        if h in blob:
            errs.append(f"mentions forbidden host {h}")
    c = job.get("constraints", {})
    if c.get("download_models") or c.get("huggingface_pull"):
        errs.append("model download / HF pull must be false")
    if not job.get("items"):
        errs.append("no items")
    return errs


def write(job, out_path):
    errs = validate(job)
    if errs:
        sys.exit("refusing to write invalid job: " + "; ".join(errs))
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    json.dump(job, open(out_path, "w"), indent=2)
    print(f"wrote {out_path}: {job['model']}, {len(job['items'])} item(s), target={job['target']}, status={job['status']}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write fleet job specs (never launches).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("qwen-image"); q.add_argument("csv"); q.add_argument("--style", default=""); q.add_argument("--negative", default="")
    q.add_argument("--size", default="1024x1024"); q.add_argument("--variants", type=int, default=1)
    m = sub.add_parser("minimax-music"); m.add_argument("csv"); m.add_argument("--style", default="")
    h = sub.add_parser("h3-video"); h.add_argument("csv", nargs="?"); h.add_argument("--turntable"); h.add_argument("--seconds", type=float, default=4.0); h.add_argument("--style", default="")
    v = sub.add_parser("validate"); v.add_argument("files", nargs="+")
    for s in (q, m, h):
        s.add_argument("-o", "--out", required=True, help="job JSON path")
        s.add_argument("--out-dir", default="outputs/pending", help="where the runner should put results")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
    # refuse dest == input unless --in-place
    def _paths(v):
        if not v:
            return []
        if isinstance(v, (list, tuple)):
            out = []
            for x in v:
                out.extend(_paths(x))
            return out
        return [v]
    _srcs, _dsts = [], []
    _src_keys = ('files', 'csv')
    for _k in _src_keys:
        if hasattr(a, _k):
            _srcs.extend(_paths(getattr(a, _k)))
    for _k in ('out', 'outdir', 'output', 'dest', 'json_report', 'report', 'preview', 'out_csv', 'map_out', 'json', 'cues', 'cues_json'):
        if _k in _src_keys:
            continue
        if hasattr(a, _k) and getattr(a, _k):
            _d = getattr(a, _k)
            _dsts.extend(_paths(_d))
    for _s in _srcs:
        for _d in _dsts:
            if _s and _d and os.path.abspath(str(_s)) == os.path.abspath(str(_d)) and not a.in_place:
                sys.exit("refusing to overwrite the input; pick a different output path or pass --in-place")

    if a.cmd == "validate":
        bad = 0
        for f in a.files:
            e = validate(json.load(open(f)))
            print(f"{f}: {'OK' if not e else 'INVALID ' + '; '.join(e)}")
            bad += bool(e)
        return 1 if bad else 0
    if a.cmd == "qwen-image":
        job = qwen_image(a.csv, a.out_dir, a.style, a.negative, a.size, a.variants)
    elif a.cmd == "minimax-music":
        job = minimax_music(a.csv, a.out_dir, a.style)
    else:
        if not a.csv and not a.turntable:
            ap.error("give a shots CSV or --turntable NAME")
        job = h3_video(a.out_dir, a.csv, a.turntable, a.seconds, style=a.style)
    write(job, a.out)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
