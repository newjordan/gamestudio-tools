#!/usr/bin/env python3
"""Write build.annotated.sh: build.sh with a comment above every gst call naming the tool and what it produces.
Only comment lines are added (check: grep -v '^ *# \\[gst' build.annotated.sh | diff - build.sh)."""
import re, shlex, sys, os
H = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(H, "build.sh")).read().splitlines()
OUT_FLAGS = ["-o", "--out", "--outdir", "--write-tileset", "--script", "--translation-dir", "--copy-dir", "--cells-json",
             "--json", "--md", "--csv", "--png", "--report", "--preview", "--log"]
PRIMARY = {"-o", "--out", "--outdir", "--write-tileset", "--script", "--translation-dir"}
def describe(cmd):
    try: tok = shlex.split(cmd, posix=True)
    except ValueError: tok = cmd.split()
    i = tok.index("gst"); tool = tok[i + 1]
    sub = tok[i + 2] if tool in ("lut-tool", "asset-rename", "wav-loop-meta", "sfx-bank", "colorblind-sim", "asset-manifest") else None
    if tool in ("tex-gen", "sfx-gen"): sub = tok[i + 2]
    prim, side = [], []
    for j, t in enumerate(tok):
        if t in OUT_FLAGS and j + 1 < len(tok):
            (prim if t in PRIMARY else side).append(tok[j + 1])
    if tool == "godot-import-presets": prim.append("<project>/*.import files")
    if tool == "asset-rename" and "--apply" in tok: prim.append("renamed files in place (dry run without --apply)")
    if tool == "sfx-normalize" and not prim: prim.append(tok[-1])
    BASENAME = {"dungeon-gen": ".txt/.png/.json/_tiles.png", "tileset-gen": ".png/.json", "frames-to-sheet": ".png/.json",
                "atlas-pack": ".png/.json", "bmfont-gen": ".fnt/.png"}
    if tool in BASENAME and prim:
        prim = [prim[0] + " {" + BASENAME[tool] + "}"] + prim[1:]
    name = tool + (" " + sub if sub else "")
    if prim or side:
        parts = []
        if prim: parts.append("produces " + ", ".join(prim))
        if side: parts.append("report " + ", ".join(side))
        return "# [gst %s] %s" % (name, "; ".join(parts))
    return "# [gst %s] check/inspect only: no asset written, a non-zero exit stops the build (set -e)" % name
out, i = [], 0
while i < len(src):
    line = src[i]
    if re.match(r"^\s*(for .*; do )?gst \S", line) and not line.lstrip().startswith("gst()"):
        full, k = line, i
        while full.rstrip().endswith("\\") and k + 1 < len(src):
            k += 1; full = full.rstrip()[:-1] + " " + src[k]
        body = re.sub(r"^\s*for .*?; do ", "", full)
        body = body.split(" | ")[0].split(" > ")[0].split(" || ")[0].split("; done")[0].split("; tail")[0]
        indent = re.match(r"^\s*", line).group(0)
        out.append(indent + describe(body))
    out.append(line); i += 1
hdr = ["# ANNOTATED COPY of examples/sample-topdown/build.sh (gamestudio-tools 2.5.0). Every '# [gst <tool>]' line names",
       "# the kit tool the next command runs and the file(s) it produces. $P = project/, $W = work/ (scratch), $S = work/sprites,",
       "# $A = work/audio. Non-gst lines (python3 src/*.py, cp, Godot) are the sample's own authored steps."]
open(os.path.join(H, "build.annotated.sh"), "w").write("\n".join([out[0]] + hdr + out[1:]) + "\n")
print(sum(1 for l in out if l.lstrip().startswith("# [gst")), "gst calls annotated")
