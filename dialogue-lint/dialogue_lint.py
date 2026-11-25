#!/usr/bin/env python3
"""dialogue-lint: validate Yarn Spinner and ink scripts for broken jumps and empty nodes.

Yarn: collects `title:` nodes, `[[Target]]` / `[[text|Target]]` jumps and
`<<jump Target>>` commands; reports jumps to missing nodes, empty bodies,
unmatched `[[` / `<<`, and (as warnings) nodes nothing jumps to except the
first. ink: collects `== knot` / `= stitch` and `->` diverts; reports
missing targets and empty knots. Exit 1 on errors (or warnings with
`--strict`). Does not rewrite files.
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402
import safe_out  # noqa: E402

YARN_JUMP = re.compile(r"\[\[(?:([^\|\]]+)\|)?([^\]]+)\]\]")
YARN_CMD_JUMP = re.compile(r"<<\s*jump\s+([^\s>]+)\s*>>")
INK_KNOT = re.compile(r"^={2,}\s*(\w+)")
INK_STITCH = re.compile(r"^=\s*(\w+)")
INK_DIVERT = re.compile(r"->\s*([\w.]+)")


def lint_yarn(path, text):
    findings, nodes, order, bodies, jumps = [], {}, [], {}, []
    node, in_body, buf = None, False, []
    unmatched = 0
    for i, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if s.startswith("title:") and not in_body:
            node = s.split(":", 1)[1].strip()
            if not node:
                findings.append({"level": "error", "file": path, "line": i, "msg": "empty title"})
            elif node in nodes:
                findings.append({"level": "error", "file": path, "line": i, "msg": "duplicate node %r" % node})
            else:
                nodes[node] = i
                order.append(node)
                bodies[node] = 0
            continue
        if s == "---":
            in_body = True
            continue
        if s == "===":
            in_body = False
            node = None
            continue
        if not in_body:
            continue
        if s.count("[[") != s.count("]]") or s.count("<<") != s.count(">>"):
            unmatched += 1
            findings.append({"level": "error", "file": path, "line": i, "msg": "unmatched [[ or << in node %r" % node})
        if s and not s.startswith("//"):
            if node:
                bodies[node] = bodies.get(node, 0) + 1
        for m in YARN_JUMP.finditer(raw):
            target = (m.group(2) or "").strip()
            if target:
                jumps.append((i, node, target))
        for m in YARN_CMD_JUMP.finditer(raw):
            jumps.append((i, node, m.group(1).strip()))
    targets = set()
    for line, src, dest in jumps:
        targets.add(dest)
        if dest not in nodes:
            findings.append({"level": "error", "file": path, "line": line,
                             "msg": "jump to missing node %r (from %r)" % (dest, src)})
    start = order[0] if order else None
    for n in order:
        if bodies.get(n, 0) == 0:
            findings.append({"level": "warn", "file": path, "line": nodes[n], "msg": "empty node %r" % n})
        if n != start and n not in targets:
            findings.append({"level": "warn", "file": path, "line": nodes[n], "msg": "orphan node %r (nothing jumps here)" % n})
    if not nodes:
        findings.append({"level": "error", "file": path, "line": 1, "msg": "no Yarn nodes (title:) found"})
    return findings, {"nodes": len(nodes), "jumps": len(jumps)}


def lint_ink(path, text):
    findings, knots, order, bodies, diverts = [], {"root": 1}, ["root"], {"root": 0}, []
    current = "root"
    in_comment = False
    for i, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if in_comment:
            if "*/" in s:
                in_comment = False
            continue
        if s.startswith("/*"):
            in_comment = "*/" not in s
            continue
        m = INK_KNOT.match(s)
        if m:
            current = m.group(1)
            if current in knots and current != "root":
                findings.append({"level": "error", "file": path, "line": i, "msg": "duplicate knot %r" % current})
            knots[current] = i
            if current not in order:
                order.append(current)
            bodies.setdefault(current, 0)
            continue
        m = INK_STITCH.match(s)
        if m:
            parent = current.split(".")[0]
            current = parent + "." + m.group(1)
            knots[current] = i
            if current not in order:
                order.append(current)
            bodies.setdefault(current, 0)
            continue
        if not s or s.startswith("//"):
            continue
        for m in INK_DIVERT.finditer(s):
            dest = m.group(1)
            diverts.append((i, current, dest))
        # count non-empty content
        if not s.startswith(("=", "->", "~", "VAR ", "CONST ", "INCLUDE ", "EXTERNAL ")):
            bodies[current] = bodies.get(current, 0) + 1
    def known(dest, src):
        if dest in knots:
            return True
        if dest.startswith("."):
            parent = src.split(".")[0]
            return (parent + dest) in knots
        if "." not in dest:
            # relative stitch?
            parent = src.split(".")[0]
            return (parent + "." + dest) in knots
        return False
    for line, src, dest in diverts:
        if dest in ("END", "DONE", "END_GAME"):
            continue
        if not known(dest, src):
            findings.append({"level": "error", "file": path, "line": line,
                             "msg": "divert to missing knot/stitch %r (from %r)" % (dest, src)})
    for n in order:
        if n == "root":
            continue
        if bodies.get(n, 0) == 0:
            findings.append({"level": "warn", "file": path, "line": knots[n], "msg": "empty knot/stitch %r" % n})
    real = [k for k in knots if k != "root"]
    if not real:
        findings.append({"level": "error", "file": path, "line": 1, "msg": "no ink knots (== name) found"})
    return findings, {"knots": len(real), "diverts": len(diverts)}


def lint_file(path):
    text = gst_read.open_text(path)
    low = path.lower()
    if low.endswith(".yarn"):
        return lint_yarn(path, text)
    if low.endswith(".ink"):
        return lint_ink(path, text)
    raise GstInputError("unsupported dialogue file (use .yarn or .ink): %s" % path)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Validate Yarn and ink scripts for broken jumps and empty nodes.")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.json:
        safe_out.check_any(a.inputs, a.json, a.in_place)
    findings, stats = [], []
    for path in a.inputs:
        if os.path.isdir(path):
            files = []
            for dp, dns, fns in os.walk(path):
                dns[:] = [d for d in dns if d not in (".git", "__pycache__")]
                for fn in fns:
                    if os.path.splitext(fn)[1].lower() in (".yarn", ".ink"):
                        files.append(os.path.join(dp, fn))
            if not files:
                raise GstInputError("no .yarn or .ink files under %s" % path)
        else:
            files = [path]
        for f in files:
            recs, st = lint_file(f)
            findings.extend(recs)
            st["file"] = f
            stats.append(st)
    for f in findings:
        print("%s  %s:%s  %s" % (f["level"].upper(), f["file"], f["line"], f["msg"]))
    n_err = sum(1 for f in findings if f["level"] == "error")
    n_warn = sum(1 for f in findings if f["level"] == "warn")
    print("%d file(s): %d error(s), %d warning(s)" % (len(stats), n_err, n_warn))
    rec = {"files": stats, "findings": findings, "errors": n_err, "warnings": n_warn}
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 1 if n_err or (a.strict and n_warn) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
