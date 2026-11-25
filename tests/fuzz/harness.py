"""Stdlib-only fuzz harness.

Feeds empty, truncated, bit-flipped and random-byte inputs derived from tiny
seeds (and, in long mode, from samples/) to every catalogued reader tool.

A case is a CRASH when:
  - stderr contains a Python traceback, or
  - the process exits with a code other than 0, 1 or 2, or
  - the process times out or is killed by a signal.

Exit 0 (accepted) and exit 1 or 2 with no traceback are OK, except that a
fully-random input (no leftover structure from the seed) must exit 1 or 2.
Exit 0 on fully-random bytes is classified as accepted-garbage (a crash).
"""
from __future__ import annotations

import json, os, random, re, resource, shutil, subprocess, sys, tempfile, traceback

from .catalog import iter_targets, tool_name
from .mutate import MUTATORS, apply
from .seeds import KINDS, generate

TRACE_RE = re.compile(r"^Traceback \(most recent call last\):", re.M)
EXC_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*): (.*)$", re.M)
# last-ditch: TypeName with no message
EXC_BARE_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Exit|Warning))$", re.M)


def parse_exception(stderr):
    """Return (type_name, message) from a Python traceback, or (None, None)."""
    err = stderr or ""
    if "Traceback (most recent call last):" not in err:
        return None, None
    # Walk from the last traceback header so chained 'During handling' is last-wins.
    last = err.rfind("Traceback (most recent call last):")
    tail = err[last:]
    typ, msg = None, None
    for m in EXC_RE.finditer(tail):
        typ, msg = m.group(1), m.group(2).strip()
    if typ:
        return typ, msg
    for line in reversed(tail.splitlines()):
        s = line.strip()
        m = EXC_BARE_RE.match(s)
        if m:
            return m.group(1), ""
    return "UnknownError", (tail.strip().splitlines()[-1] if tail.strip() else "")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SEED_DIR = os.path.join(os.path.dirname(__file__), "seeds")
GST = os.path.join(ROOT, "gst")

# extensions written for each kind (mutated file name)
EXT = {
    "wav": ".wav", "png": ".png", "gif": ".gif", "tiled": ".json", "tmx": ".tmx",
    "glb": ".glb", "gltf": ".gltf", "obj": ".obj", "atlas": ".json",
    "loc": ".csv", "yarn": ".yarn", "ink": ".ink", "fnt": ".fnt", "fntxml": ".fnt", "fntbin": ".fnt", "colliders": ".json", "tiledzstd": ".json", "tmxzstd": ".tmx", "ase": ".ase",
    "tsx": ".tsx", "tiledanim": ".json", "tmxext": ".tmx", "asejson": ".json",
}

# Keep child processes from eating the box if a mutated header claims a huge image.
MEM_LIMIT = 512 * 1024 * 1024
FAST_MUTATIONS = ("empty", "truncated", "bit-flipped", "random-byte", "fully-random")
LONG_MUTATIONS = ("empty", "truncated", "bit-flipped", "random-byte", "fully-random")


def _limit_resources():
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEM_LIMIT, MEM_LIMIT))
    except (ValueError, OSError):
        pass
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
    except (ValueError, OSError):
        pass


def _write_sidecars(work, kind, valid_seed):
    """Write helper files some tools require besides the mutated input."""
    pal = os.path.join(work, "palette.hex")
    open(pal, "w").write("ff0000\n00ff00\n0000ff\nffffff\n000000\n")
    remap = os.path.join(work, "remap.csv")
    open(remap, "w").write("from,to\n1,2\n")
    rules = os.path.join(work, "rules.json")
    open(rules, "w").write('{"rules":[]}\n')
    schema = os.path.join(work, "schema.json")
    open(schema, "w").write("{}\n")
    text = os.path.join(work, "text.txt")
    open(text, "w").write("AB Hello\n")
    pmap = os.path.join(work, "swap.json")
    open(pmap, "w").write("ff0000:00ff00\n")
    from .seeds import write_tiled
    nav_map = write_tiled(os.path.join(work, "navmap.json"))
    # a map whose only tileset is the (fuzzed) input.tsx next to it
    tsxmap = os.path.join(work, "tsxmap.json")
    json.dump({"type": "map", "width": 2, "height": 2, "tilewidth": 8, "tileheight": 8, "orientation": "orthogonal",
               "tilesets": [{"firstgid": 1, "source": "input.tsx"}],
               "layers": [{"type": "objectgroup", "name": "o", "objects": [
                   {"id": 1, "gid": 1, "x": 0, "y": 8, "width": 8, "height": 8},
                   {"id": 2, "gid": 2 | 0x80000000, "x": 8, "y": 8, "width": 8, "height": 8}]}]}, open(tsxmap, "w"))
    return {
        "map": nav_map,
        "tsxmap": tsxmap,
        "palette": pal,
        "remap": remap,
        "rules": rules,
        "schema": schema,
        "text": text,
        "swap": pmap,
    }


def _sidecar_for(entry, files):
    name = tool_name(entry)
    if name == "palette-apply":
        return files["palette"]
    if name == "palette-swap":
        return files["swap"]
    if name == "map-auto-layer":
        return files["rules"]
    if name == "tile-replace":
        return files["remap"]
    if name == "tmx-props-lint":
        return files["schema"]
    if name == "font-check":
        return files["text"]
    if entry["name"] == "nav-to-godot-colliders":
        return files["map"]
    if entry["name"] == "map-objects-to-godot-tsx":
        return files["tsxmap"]
    return files["text"]


def collect_sample_seeds(samples_dir):
    """Pick small representative sample files, grouped by kind. Stdlib only."""
    out = {k: [] for k in KINDS}
    if not samples_dir or not os.path.isdir(samples_dir):
        return out
    max_bytes = 256 * 1024
    want = {
        ".wav": "wav", ".png": "png", ".gif": "gif", ".tmx": "tmx",
        ".glb": "glb", ".gltf": "gltf", ".obj": "obj", ".yarn": "yarn",
        ".ink": "ink", ".fnt": "fnt", ".ase": "ase", ".aseprite": "ase",
    }
    for dp, dn, fn in os.walk(samples_dir):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
        for f in fn:
            path = os.path.join(dp, f)
            try:
                if os.path.getsize(path) > max_bytes:
                    continue
            except OSError:
                continue
            ext = os.path.splitext(f)[1].lower()
            kind = want.get(ext)
            if ext == ".json":
                # cheap sniff
                try:
                    head = open(path, "rb").read(256).lstrip()
                except OSError:
                    continue
                if b'"frames"' in head and b'"meta"' in head or b'"frames"' in open(path, "rb").read(4096):
                    kind = "atlas"
                elif b'"type"' in head or b'"layers"' in head or b'"tilewidth"' in head:
                    # could be tiled or something else; peek a bit more
                    blob = open(path, "rb").read(4096)
                    if b'"tilewidth"' in blob or b'"tilesets"' in blob or b'"infinite"' in blob:
                        kind = "tiled"
                    else:
                        kind = None
                elif b'"id"' in head and (b"en" in head or b","):
                    kind = None  # loc is csv
                else:
                    kind = None
            elif ext == ".csv":
                try:
                    line = open(path, "r", encoding="utf-8", errors="replace").readline()
                except OSError:
                    continue
                if line.lower().startswith("id,") or ",en," in line.lower() or line.lower().startswith("key,"):
                    kind = "loc"
                else:
                    kind = None
            if kind:
                out[kind].append(path)
    # cap per kind so the long run stays bounded
    for k in out:
        out[k] = sorted(out[k])[:12]
    return out


def classify(rc, stdout, stderr, timed_out):
    if timed_out:
        return "timeout"
    err = stderr or ""
    if TRACE_RE.search(err) or "Traceback (most recent call last)" in err:
        return "traceback"
    if rc is None:
        return "signal"
    if rc < 0:
        return "signal"
    if rc in (0, 1, 2):
        return "ok"
    return "bad-exit"


def run_case(tool_path, argv, timeout, env_extra=None, cwd=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    try:
        p = subprocess.run(
            [sys.executable, tool_path] + argv,
            capture_output=True, timeout=timeout, env=env,
            preexec_fn=_limit_resources, cwd=cwd,
        )
        out = p.stdout.decode("utf-8", "replace") if isinstance(p.stdout, bytes) else (p.stdout or "")
        err = p.stderr.decode("utf-8", "replace") if isinstance(p.stderr, bytes) else (p.stderr or "")
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired as e:
        out = (e.stdout or b"")
        err = (e.stderr or b"")
        if isinstance(out, bytes):
            out = out.decode("utf-8", "replace")
        if isinstance(err, bytes):
            err = err.decode("utf-8", "replace")
        return None, out, err, True
    except Exception as e:
        return 99, "", "harness: %s: %s" % (type(e).__name__, e), False


def _copy_companions(seed_path, dest_dir):
    """Copy sidecar assets that sit next to a seed (atlas png, tiles.png, label.png, gltf bin)."""
    d = os.path.dirname(os.path.abspath(seed_path))
    if not os.path.isdir(d):
        return
    for name in os.listdir(d):
        src = os.path.join(d, name)
        if not os.path.isfile(src):
            continue
        if src == os.path.abspath(seed_path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in (".png", ".gif", ".bin", ".gltf", ".glb", ".csv", ".tsx", ".tsj", ".mtl"):
            dst = os.path.join(dest_dir, name)
            if not os.path.exists(dst):
                try:
                    shutil.copy2(src, dst)
                except OSError:
                    pass


def expand_argv(template, mapping):
    out = []
    for part in template:
        for k, v in mapping.items():
            part = part.replace("{" + k + "}", v)
        out.append(part)
    return out


def iter_seeds_for(kind, generated, sample_map, long_mode, rng, cap_fast=1, cap_long=4):
    items = list(generated.get(kind) or [])
    if long_mode:
        items.extend(sample_map.get(kind) or [])
    # unique, existing
    seen, uniq = set(), []
    for p in items:
        ap = os.path.abspath(p)
        if ap not in seen and os.path.isfile(ap):
            seen.add(ap)
            uniq.append(ap)
    cap = cap_long if long_mode else cap_fast
    if len(uniq) > cap:
        uniq = list(rng.sample(uniq, cap)) if cap else uniq[:cap]
    return uniq


_EXC_TYPE_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_VALIDATED_TYPES = {"GstInputError", "SystemExit"}


def parse_one_liner(line):
    """Recover (type, message) from cli_error.format_error output, or (None, line)."""
    line = (line or "").strip()
    if not line:
        return None, ""
    if ": " in line:
        typ, msg = line.split(": ", 1)
        if typ not in ("",) and typ[0].isupper() and _EXC_TYPE_RE.match(typ):
            return typ, msg
    if _EXC_TYPE_RE.match(line) and line[0].isupper() and (line.endswith("Error") or line.endswith("Exception") or line in ("SystemExit", "KeyboardInterrupt")):
        return line, ""
    return None, line


def _short_type(typ):
    if not typ:
        return typ
    return typ.rsplit(".", 1)[-1]


def is_generic_hit(typ, kind_c):
    """True when cli_error caught a non-GstInputError Exception."""
    name = _short_type(typ)
    if name in (None, "", "GstInputError", "SystemExit"):
        return False
    return True


def fuzz(root=ROOT, seed=1, fast=True, timeout=2.0, only=None, samples=True,
         report_path=None, mutations=None, debug=False):
    rng = random.Random(seed)
    gen_dir = os.path.join(root, "tests", "fuzz", "seeds")
    generated = generate(gen_dir)
    sample_map = {k: [] for k in KINDS}
    if samples and not fast:
        sample_map = collect_sample_seeds(os.path.join(root, "samples"))
    muts = mutations or (FAST_MUTATIONS if fast else LONG_MUTATIONS)
    results = []  # dicts
    counts = {}   # tool -> {ok, traceback, timeout, signal, bad-exit}

    work_root = tempfile.mkdtemp(prefix="gst-fuzz-")
    try:
        case_i = 0
        for entry in iter_targets(only):
            name = tool_name(entry)
            kind = entry["kind"]
            tool_path = os.path.join(root, name, name.replace("-", "_") + ".py")
            if not os.path.isfile(tool_path):
                continue
            counts.setdefault(name, {"ok": 0, "traceback": 0, "timeout": 0, "signal": 0, "bad-exit": 0, "accepted-garbage": 0})
            seeds = iter_seeds_for(kind, generated, sample_map, long_mode=not fast, rng=rng)
            if not seeds:
                continue
            valid2_list = list(generated.get(kind) or [])
            for src in seeds:
                raw = open(src, "rb").read()
                for mname in muts:
                    case_i += 1
                    # independent rng stream per case
                    crng = random.Random("%s|%s|%s|%s|%s|%s" % (seed, name, kind, os.path.basename(src), mname, case_i))
                    mutated = apply(mname, raw, crng)
                    work = os.path.join(work_root, "%s_%d" % (name, case_i))
                    os.makedirs(work, exist_ok=True)
                    in_path = os.path.join(work, "input" + EXT[kind])
                    open(in_path, "wb").write(mutated)
                    _copy_companions(src, work)
                    # second valid input (unmutated) for two-input tools
                    other = None
                    for cand in valid2_list:
                        if os.path.abspath(cand) != os.path.abspath(src):
                            other = cand
                            break
                    if other is None:
                        other = src
                    in2 = os.path.join(work, "input2" + EXT[kind])
                    shutil.copy2(other, in2)
                    _copy_companions(other, work)
                    out_file = os.path.join(work, "out" + EXT.get(kind, ".out"))
                    out_dir = os.path.join(work, "outdir")
                    os.makedirs(out_dir, exist_ok=True)
                    files = _write_sidecars(work, kind, src)
                    sidecar = _sidecar_for(entry, files)
                    mapping = {
                        "input": in_path,
                        "input2": in2,
                        "out": out_file,
                        "outdir": out_dir,
                        "sidecar": sidecar,
                    }
                    argv = expand_argv(entry["argv"], mapping)
                    env_extra = {"GST_DEBUG": "1"} if debug else {"GST_DEBUG": "0"}
                    rc, stdout, stderr, timed_out = run_case(tool_path, argv, timeout, env_extra=env_extra, cwd=work)
                    kind_c = classify(rc, stdout, stderr, timed_out)
                    # Fully random bytes must not be accepted as a valid asset.
                    if mname == "fully-random" and kind_c == "ok" and rc == 0:
                        kind_c = "accepted-garbage"
                    counts[name][kind_c] = counts[name].get(kind_c, 0) + 1
                    typ, msg = parse_exception(stderr)
                    # When the wrapper swallowed the exception (no traceback), recover the type from the one-liner.
                    if typ is None and (stderr or "").strip() and rc == 1:
                        typ, msg = parse_one_liner((stderr or "").strip().splitlines()[0])
                    rec = {
                        "tool": name, "alias": entry["name"], "kind": kind,
                        "mutation": mname, "seed": os.path.relpath(src, root) if src.startswith(root) else src,
                        "rc": rc, "class": kind_c,
                        "exc_type": typ,
                        "exc_msg": (msg or "")[:240],
                        "generic": is_generic_hit(typ, kind_c),
                        "stderr": (stderr or "").strip()[:400],
                    }
                    results.append(rec)
    finally:
        shutil.rmtree(work_root, ignore_errors=True)

    crashes = [r for r in results if r["class"] != "ok"]
    generic = [r for r in results if r.get("generic")]
    # "crash" in the report sense: traceback / bad-exit / signal / timeout
    report = {
        "seed": seed, "fast": fast, "timeout": timeout, "debug": debug,
        "cases": len(results),
        "ok": sum(1 for r in results if r["class"] == "ok"),
        "crashes": len(crashes),
        "generic_hits": len(generic),
        "by_class": {
            c: sum(1 for r in results if r["class"] == c)
            for c in ("ok", "traceback", "timeout", "signal", "bad-exit", "accepted-garbage")
        },
        "by_tool": counts,
        "crash_cases": crashes if not debug else [c for c in crashes if c["class"] != "traceback"],
        "generic_cases": generic,
        "by_root_cause": classify_root_causes(results),
    }
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)) or ".", exist_ok=True)
        json.dump(report, open(report_path, "w"), indent=2)
    return report


def classify_root_causes(results):
    """Group exceptions by reader kind, then by type + normalized message."""
    out = {}
    for rec in results:
        typ = rec.get("exc_type")
        if not typ and rec["class"] == "ok":
            # clean SystemExit / usage / accepted: skip unless stderr is a one-line error
            err = (rec.get("stderr") or "").strip()
            if rec.get("rc") in (1, 2) and err and "Traceback" not in err:
                typ = "SystemExit"
                rec = dict(rec, exc_type=typ, exc_msg=err.splitlines()[0][:240])
            else:
                continue
        if not typ:
            typ = rec["class"] if rec["class"] != "ok" else "accepted"
        kind = rec.get("kind") or "other"
        msg = rec.get("exc_msg") or ""
        # normalize hex addresses and paths so identical bugs group
        norm = re.sub(r"/[^\s]+", "<path>", msg)
        norm = re.sub(r"0x[0-9a-fA-F]+", "0xN", norm)
        norm = re.sub(r"\d+", "N", norm)
        key = typ + ": " + (norm[:160] if norm else "(no message)")
        bucket = out.setdefault(kind, {})
        recs = bucket.setdefault(key, {"count": 0, "generic": 0, "tools": {}})
        recs["count"] += 1
        if rec.get("generic"):
            recs["generic"] += 1
        recs["tools"][rec["tool"]] = recs["tools"].get(rec["tool"], 0) + 1
    return out


def format_root_causes(report):
    lines = []
    causes = report.get("by_root_cause") or {}
    if not causes:
        return "root causes: (none)"
    for kind in sorted(causes):
        lines.append("kind %s:" % kind)
        items = sorted(causes[kind].items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        for key, rec in items:
            tools = ", ".join("%s=%d" % (t, n) for t, n in sorted(rec["tools"].items(), key=lambda x: -x[1])[:8])
            flag = " generic=%d" % rec["generic"] if rec["generic"] else ""
            lines.append("  %d%s  %s  [%s]" % (rec["count"], flag, key, tools))
    return "\n".join(lines)


def format_summary(report, include_cases=True):
    lines = [
        "fuzz cases=%d ok=%d crashes=%d generic=%d (traceback=%d timeout=%d signal=%d bad-exit=%d accepted-garbage=%d) seed=%s debug=%s"
        % (report["cases"], report["ok"], report["crashes"], report.get("generic_hits", 0),
           report["by_class"]["traceback"], report["by_class"]["timeout"],
           report["by_class"]["signal"], report["by_class"]["bad-exit"],
           report["by_class"].get("accepted-garbage", 0),
           report["seed"], report.get("debug", False)),
    ]
    # per-tool crash counts
    rows = []
    for name, c in sorted(report["by_tool"].items()):
        ncrash = c.get("traceback", 0) + c.get("timeout", 0) + c.get("signal", 0) + c.get("bad-exit", 0) + c.get("accepted-garbage", 0)
        if ncrash:
            rows.append((ncrash, name, c))
    if rows:
        lines.append("crashes by tool:")
        for ncrash, name, c in sorted(rows, key=lambda x: (-x[0], x[1])):
            parts = ["%s=%d" % (k, c[k]) for k in ("traceback", "timeout", "signal", "bad-exit", "accepted-garbage") if c.get(k)]
            lines.append("  %s  %d  (%s)" % (name, ncrash, ", ".join(parts)))
    else:
        lines.append("crashes by tool: (none)")
    if include_cases and report.get("crash_cases"):
        lines.append("first crashes:")
        for rec in report["crash_cases"][:40]:
            err = rec["stderr"].replace("\n", " | ")[:160]
            lines.append("  %s %s %s rc=%s %s" % (rec["tool"], rec["mutation"], rec["class"], rec["rc"], err))
    if report.get("by_root_cause"):
        lines.append(format_root_causes(report))
    lines.append("generic-wrapper hits: %d" % report.get("generic_hits", 0))
    return "\n".join(lines)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Fuzz kit tools that parse common game-asset formats.")
    ap.add_argument("--fast", action="store_true", help="tiny generated seeds only (default for the test suite)")
    ap.add_argument("--long", action="store_true", help="also mutate files under samples/ when present")
    ap.add_argument("--debug", action="store_true",
                    help="set GST_DEBUG=1 in child processes (re-raise; classify exceptions)")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=0)
    ap.add_argument("-o", "--out", help="write a JSON report")
    ap.add_argument("tools", nargs="*", help="limit to these tool names")
    a = ap.parse_args(argv)
    fast = not a.long
    if a.fast:
        fast = True
    timeout = a.timeout or (2.0 if fast else 4.0)
    only = set(a.tools) if a.tools else None
    report = fuzz(root=ROOT, seed=a.seed, fast=fast, timeout=timeout, only=only,
                  samples=not fast, report_path=a.out, debug=a.debug)
    print(format_summary(report))
    # Under --debug, tracebacks are expected (that is the classification run).
    if a.debug:
        return 0
    return 0 if report["crashes"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
