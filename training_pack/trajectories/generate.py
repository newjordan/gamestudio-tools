#!/usr/bin/env python3
"""Generate and re-verify tool-use trajectories for gamestudio-tools.

Every trajectory is executed in a fresh temp project. stdout, stderr, exit
codes and sha256 of produced files are captured from that run. A step whose
exit code is not the one the catalog expected drops the whole trajectory;
the reason is appended to dropped.jsonl. Nothing is invented.

  python3 generate.py                 # run the catalog, write shards + stats
  python3 generate.py --verify        # re-run stored commands and compare
  python3 generate.py --only ID       # one trajectory (repeat the flag to add)
  python3 generate.py --jobs N

Absolute temp paths in captured text are rewritten to ``{project}`` and the
kit root to ``{kit}`` so the record does not depend on the machine path.
Re-verify applies the same rewrite before comparing.

No model weights are downloaded and no training job is launched.
"""
import argparse, hashlib, json, os, shlex, shutil, subprocess, sys, tempfile, time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(os.path.dirname(HERE))
SHARD_DIR = os.path.join(HERE, "shards")
STATS_PATH = os.path.join(HERE, "stats.json")
DROPPED_PATH = os.path.join(HERE, "dropped.jsonl")
MAX_SHARD = 4_500_000
STREAM_CAP = 12_000
CMD_TIMEOUT = 90

sys.path.insert(0, HERE)
import fixtures  # noqa: E402
import catalog  # noqa: E402


def categories():
    text = open(os.path.join(KIT, "gst"), encoding="utf-8").read()
    start = text.index("CATEGORIES = {")
    end = text.index("\n}", start)
    return dict(pair for pair in __import__("re").findall(r"'([^']+)': '([^']+)'", text[start:end]))


CATS = categories()


def _norm(text, project):
    if not text:
        return ""
    text = text.replace(project, "{project}")
    # trailing slash variants and the real kit path
    text = text.replace(KIT, "{kit}")
    return text


def _cap(text):
    if text is None:
        return ""
    if len(text) <= STREAM_CAP:
        return text
    extra = len(text) - STREAM_CAP
    return text[:STREAM_CAP] + "\n...[truncated %d bytes]\n" % extra


def _hash_needles(root):
    """Absolute paths that show up inside reports and undo logs. Longer first."""
    pairs = [
        (os.path.abspath(root).encode(), b"{project}"),
        (os.path.abspath(KIT).encode(), b"{kit}"),
    ]
    pairs.sort(key=lambda p: len(p[0]), reverse=True)
    return pairs


def _snapshot(root):
    needles = _hash_needles(root)
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__", ".godot")]
        for name in filenames:
            path = os.path.join(dirpath, name)
            if not os.path.isfile(path) or os.path.islink(path):
                # still hash a symlink's target content if it is a real file copy; skip links
                if os.path.islink(path):
                    continue
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            data = open(path, "rb").read()
            for old, new in needles:
                data = data.replace(old, new)
            out[rel] = (hashlib.sha256(data).hexdigest(), os.path.getsize(path))
    return out


def _produced(before, after):
    files = []
    for rel, (digest, size) in sorted(after.items()):
        if before.get(rel) != (digest, size):
            files.append({"path": rel, "sha256": digest, "bytes": size})
    removed = sorted(set(before) - set(after))
    return files, removed


def run_gst(project, argv, timeout=CMD_TIMEOUT):
    cmd = [sys.executable, os.path.join(KIT, "gst"), *argv]
    env = os.environ.copy()
    env["PYTHONHASHSEED"] = "0"
    env["LC_ALL"] = "C"
    env["SOURCE_DATE_EPOCH"] = "0"
    env.pop("GST_DEBUG", None)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(
            cmd, cwd=project, env=env, capture_output=True, text=True,
            errors="replace", timeout=timeout,
        )
        code = proc.returncode
        out, err = proc.stdout, proc.stderr
    except subprocess.TimeoutExpired as e:
        code = 124
        out = e.stdout or ""
        err = (e.stderr or "") + "\n[timeout after %ss]\n" % timeout
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
    elapsed = int((time.monotonic() - t0) * 1000)
    return code, _cap(_norm(out, project)), _cap(_norm(err, project)), elapsed


def _expect_ok(expect, code):
    if expect == "nonzero":
        return code != 0
    return code == expect


def _families(steps):
    fams = []
    tools = []
    for step in steps:
        tool = step["argv"][0]
        if tool not in tools:
            tools.append(tool)
        fam = CATS.get(tool)
        if fam and fam not in fams:
            fams.append(fam)
    return fams, tools


def _first_error_line(stderr, stdout):
    for line in (stderr or "").splitlines():
        s = line.strip()
        if s:
            return s[:180]
    for line in (stdout or "").splitlines():
        s = line.strip()
        if s:
            return s[:180]
    return "(no error text)"


def execute_spec(spec):
    """Run one spec. Returns (record, None) or (None, drop)."""
    project = tempfile.mkdtemp(prefix="gst-traj-")
    try:
        fixtures.build(project, KIT)
        steps_out = []
        for index, step in enumerate(spec["steps"]):
            before = _snapshot(project)
            code, out, err, elapsed = run_gst(project, step["argv"])
            after = _snapshot(project)
            files, removed = _produced(before, after)
            reasoning = step["reasoning"]
            if step.get("kind") == "fix" and "{error}" in reasoning:
                # the previous step is the failed attempt; quote its first error line
                prev = steps_out[-1]
                reasoning = reasoning.replace("{error}", _first_error_line(prev["stderr"], prev["stdout"]))
            if not _expect_ok(step["expect"], code):
                return None, {
                    "id": spec["id"],
                    "request": spec["request"],
                    "primary_family": spec["primary_family"],
                    "recovery": spec["recovery"],
                    "step_index": index,
                    "kind": step["kind"],
                    "command": "gst " + shlex.join(step["argv"]),
                    "expect": step["expect"],
                    "exit_code": code,
                    "stdout": out,
                    "stderr": err,
                    "reason": "step %d (%s) exited %s, expected %s" % (
                        index, step["kind"], code, step["expect"]),
                }
            rec = {
                "index": index,
                "kind": step["kind"],
                "reasoning": reasoning,
                "command": "gst " + shlex.join(step["argv"]),
                "argv": list(step["argv"]),
                "exit_code": code,
                "stdout": out,
                "stderr": err,
                "elapsed_ms": elapsed,
                "files": files,
            }
            if removed:
                rec["removed"] = removed
            steps_out.append(rec)
        fams, tools = _families(spec["steps"])
        record = {
            "id": spec["id"],
            "request": spec["request"],
            "primary_family": spec["primary_family"],
            "families": fams,
            "tools": tools,
            "recovery": bool(spec["recovery"]),
            "steps": steps_out,
        }
        return record, None
    finally:
        shutil.rmtree(project, ignore_errors=True)


def _worker(spec):
    try:
        return execute_spec(spec)
    except Exception as e:
        return None, {
            "id": spec["id"],
            "request": spec["request"],
            "primary_family": spec["primary_family"],
            "recovery": spec["recovery"],
            "step_index": None,
            "command": "",
            "expect": None,
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "reason": "harness exception: %s: %s" % (type(e).__name__, e),
        }


def write_outputs(records, dropped):
    os.makedirs(SHARD_DIR, exist_ok=True)
    for name in os.listdir(SHARD_DIR):
        if name.endswith(".jsonl"):
            os.remove(os.path.join(SHARD_DIR, name))
    records = sorted(records, key=lambda r: r["id"])
    dropped = sorted(dropped, key=lambda r: r["id"])
    # one shard per primary family; split a family that would pass 4.5 MB
    by_fam = defaultdict(list)
    for rec in records:
        by_fam[rec["primary_family"]].append(rec)
    shards = []
    for fam in sorted(by_fam):
        blob_parts = []
        part = 1
        current = []
        current_bytes = 0
        for rec in by_fam[fam]:
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"
            encoded = line.encode("utf-8")
            if current and current_bytes + len(encoded) > MAX_SHARD:
                shards.append(_emit_shard(fam, part, current))
                part += 1
                current, current_bytes = [], 0
            current.append(line)
            current_bytes += len(encoded)
        if current:
            shards.append(_emit_shard(fam, part, current))
    with open(DROPPED_PATH, "w", encoding="utf-8") as f:
        for rec in dropped:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
    stats = _stats(records, dropped, shards)
    with open(STATS_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, sort_keys=True)
        f.write("\n")
    return stats


def _emit_shard(fam, part, lines):
    name = "trajectories-%s.jsonl" % fam if part == 1 else "trajectories-%s-%02d.jsonl" % (fam, part)
    path = os.path.join(SHARD_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    size = os.path.getsize(path)
    if size >= 5_000_000:
        raise SystemExit("shard %s is %d bytes, over the 5 MB cap" % (name, size))
    return {"file": "shards/" + name, "bytes": size, "trajectories": len(lines), "primary_family": fam}


def _stats(records, dropped, shards):
    by_tool_steps = Counter()
    by_tool_traj = Counter()
    by_fam_steps = Counter()
    by_fam_traj = Counter()
    primary = Counter()
    step_count = 0
    for rec in records:
        primary[rec["primary_family"]] += 1
        seen_tools = set()
        seen_fams = set(rec["families"])
        for fam in seen_fams:
            by_fam_traj[fam] += 1
        for step in rec["steps"]:
            step_count += 1
            tool = step["argv"][0]
            by_tool_steps[tool] += 1
            if tool not in seen_tools:
                by_tool_traj[tool] += 1
                seen_tools.add(tool)
            fam = CATS.get(tool, "other")
            by_fam_steps[fam] += 1
    n = len(records)
    recovery = sum(1 for r in records if r["recovery"])
    version = open(os.path.join(KIT, "VERSION"), encoding="utf-8").read().strip()
    return {
        "kit_version": version,
        "trajectory_count": n,
        "recovery_count": recovery,
        "recovery_fraction": round(recovery / n, 4) if n else 0,
        "step_count": step_count,
        "dropped_count": len(dropped),
        "tools_covered": len(by_tool_traj),
        "families_covered": sorted(by_fam_traj),
        "primary_family": dict(sorted(primary.items())),
        "by_family": {
            fam: {"trajectories": by_fam_traj[fam], "steps": by_fam_steps[fam]}
            for fam in sorted(set(by_fam_traj) | set(by_fam_steps))
        },
        "by_tool": {
            tool: {"trajectories": by_tool_traj[tool], "steps": by_tool_steps[tool]}
            for tool in sorted(by_tool_traj)
        },
        "shards": shards,
        "notes": {
            "path_rewrite": "absolute temp directory -> {project}; kit root -> {kit}",
            "sha256": "file bytes after that same path rewrite, so a report that stores an absolute path still matches",
            "recovery": "a recovery trajectory's first gst command fails, the next step is the correction",
            "dropped": "dropped.jsonl lists trajectories whose measured exit did not match the catalog",
        },
    }


def load_records():
    records = []
    if not os.path.isdir(SHARD_DIR):
        return records
    for name in sorted(os.listdir(SHARD_DIR)):
        if not name.endswith(".jsonl"):
            continue
        with open(os.path.join(SHARD_DIR, name), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


def verify_record(record):
    """Re-execute a stored trajectory. Returns a list of mismatch strings."""
    # same prefix length as execute_spec: reports that embed the absolute path
    # keep a stable on-disk size only when the temp directory name is the same length
    project = tempfile.mkdtemp(prefix="gst-traj-")
    problems = []
    try:
        fixtures.build(project, KIT)
        for step in record["steps"]:
            before = _snapshot(project)
            code, out, err, _elapsed = run_gst(project, step["argv"])
            after = _snapshot(project)
            files, removed = _produced(before, after)
            if code != step["exit_code"]:
                problems.append("%s step %d exit %s != stored %s (%s)" % (
                    record["id"], step["index"], code, step["exit_code"], step["command"]))
                break
            if out != step["stdout"] or err != step["stderr"]:
                problems.append("%s step %d stdout/stderr drifted (%s)" % (
                    record["id"], step["index"], step["command"]))
                break
            got = {(f["path"], f["sha256"], f["bytes"]) for f in files}
            exp = {(f["path"], f["sha256"], f["bytes"]) for f in step["files"]}
            if got != exp or removed != step.get("removed", []):
                problems.append("%s step %d produced files drifted (%s)" % (
                    record["id"], step["index"], step["command"]))
                break
    except Exception as e:
        problems.append("%s harness exception: %s" % (record["id"], e))
    finally:
        shutil.rmtree(project, ignore_errors=True)
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate or re-verify gst tool-use trajectories.")
    ap.add_argument("--verify", action="store_true", help="re-run stored trajectories and compare")
    ap.add_argument("--only", action="append", default=[], help="restrict to these trajectory ids")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--list", action="store_true", help="print catalog ids and exit")
    args = ap.parse_args(argv)
    specs = catalog.specs()
    if args.only:
        want = set(args.only)
        specs = [s for s in specs if s["id"] in want]
        if not specs:
            print("no matching trajectories", file=sys.stderr)
            return 2
    if args.list:
        for s in specs:
            print("%s  %s  recovery=%s  %s" % (s["id"], s["primary_family"], s["recovery"], s["request"]))
        print("%d specs" % len(specs))
        return 0
    if args.verify:
        records = load_records()
        if args.only:
            want = set(args.only)
            records = [r for r in records if r["id"] in want]
        if not records:
            print("no stored trajectories to verify", file=sys.stderr)
            return 2
        problems = []
        jobs = max(1, args.jobs)
        if jobs == 1:
            for rec in records:
                problems.extend(verify_record(rec))
        else:
            import concurrent.futures as cf
            with cf.ProcessPoolExecutor(max_workers=jobs) as pool:
                for batch in pool.map(verify_record, records):
                    problems.extend(batch)
        if problems:
            print("verify failed: %d" % len(problems))
            for line in problems[:40]:
                print(line)
            return 1
        print("verified %d trajectories" % len(records))
        return 0

    jobs = max(1, args.jobs)
    records, dropped = [], []
    if jobs == 1:
        for spec in specs:
            rec, drop = _worker(spec)
            (records if rec else dropped).append(rec or drop)
            print("%s %s" % ("ok " if rec else "DROP", spec["id"]), flush=True)
    else:
        import concurrent.futures as cf
        with cf.ProcessPoolExecutor(max_workers=jobs) as pool:
            for spec, (rec, drop) in zip(specs, pool.map(_worker, specs)):
                (records if rec else dropped).append(rec or drop)
                print("%s %s" % ("ok " if rec else "DROP", spec["id"]), flush=True)
    stats = write_outputs(records, dropped)
    print("trajectories %d  recovery %d (%.3f)  dropped %d  steps %d  tools %d" % (
        stats["trajectory_count"], stats["recovery_count"], stats["recovery_fraction"],
        stats["dropped_count"], stats["step_count"], stats["tools_covered"]))
    if stats["trajectory_count"] < 300:
        print("fewer than 300 kept trajectories", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
