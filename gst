#!/usr/bin/env python3
"""gst: single entry point for the gamestudio-tools kit.

  gst list [--category CAT]  list every tool with its category and one-line purpose
  gst categories             list categories and tool counts
  gst search [--category CAT] KEYWORD [KEYWORD...]
                             find tools by keyword in the name, category or description
  gst <tool> [args...]       run a tool exactly as if you had called its script (gst atlas-pack sprites/ -o atlas)
  gst help <tool>            show a tool's own --help
  gst info <tool>            print the tool's README summary and path
  gst doctor                 check Python, Pillow, numpy and the optional extras (fonttools, ffmpeg, pytest)
  gst test [pytest args]     run the kit's test-suite
  gst version                kit version and tool count
  gst completion bash        print a bash completion script (eval "$(gst completion bash)")
  gst bundle -o DIR          write a reproducible .tar.gz of the kit plus a .sha256 file (for copying to another machine)
  gst docs -o DIR            build a static HTML docs site from every tool README, pipelines, categories, CHANGELOG and showcase previews
  gst fuzz [--fast|--long] [--debug] [--seed N]   fuzz reader tools; --debug sets GST_DEBUG=1 and classifies exceptions

Exit codes (kit-wide): 0 success, 1 issues / CI fail, 2 usage error. Tools pass their own codes through.

Tools are the folders next to this file that contain <name_with_underscores>.py. Nothing here talks to the network
or to any other machine.
"""
import ast, difflib, gzip, hashlib, importlib.util, io, os, runpy, shutil, subprocess, sys, tarfile

ROOT = os.path.dirname(os.path.realpath(__file__))
RESERVED = {"list", "help", "info", "doctor", "test", "version", "completion", "bundle", "search", "categories", "docs", "fuzz"}
BUNDLE_SKIP_DIRS = {"samples", "__pycache__", ".pytest_cache", ".git", "release-bundles", ".godot"}
BUNDLE_SKIP_FILES = {"contact_sheet.png"}


def tools():
    out = {}
    for d in sorted(os.listdir(ROOT)):
        p = os.path.join(ROOT, d, d.replace("-", "_") + ".py")
        if os.path.isfile(p) and d not in RESERVED: out[d] = p
    return out


def first_line(path):
    try:
        doc = ast.get_docstring(ast.parse(open(path, encoding="utf-8").read())) or ""
    except SyntaxError:
        return "(syntax error)"
    para = " ".join(doc.strip().split("\n\n")[0].split())               # first paragraph on one line
    prefix = os.path.basename(os.path.dirname(path)) + ": "
    if para.startswith(prefix): para = para[len(prefix):]
    para = para.split(". ")[0].rstrip(".")                                  # first sentence
    return para if len(para) <= 110 else para[:107].rsplit(" ", 1)[0] + "..."


CATEGORIES = {
    'alpha-bleed': 'sprites',
    'anim-from-folder': 'animation',
    'anim-hold': 'animation',
    'anim-meta': 'animation',
    'anim-pingpong': 'animation',
    'anim-rename': 'animation',
    'anim-retarget-fps': 'animation',
    'anim-reverse': 'animation',
    'anim-splice': 'animation',
    'anim-to-godot': 'godot',
    'ase-decode': 'animation',
    'ase-json-import': 'animation',
    'ase-to-godot': 'godot',
    'asset-lint': 'data',
    'asset-manifest': 'data',
    'asset-rename': 'data',
    'asset-unused': 'data',
    'asset-viewer': 'data',
    'atlas-convert': 'sprites',
    'atlas-merge': 'sprites',
    'atlas-pack': 'sprites',
    'atlas-rename': 'sprites',
    'atlas-sort': 'sprites',
    'atlas-to-godot': 'godot',
    'atlas-unpack': 'sprites',
    'atlas-validate': 'sprites',
    'audio-concat': 'audio',
    'audio-convert': 'audio',
    'audio-tidy': 'audio',
    'autotile-gen': 'maps',
    'bmfont-gen': 'fonts',
    'build-report': 'data',
    'channel-pack': 'images',
    'collider-preview': 'mesh',
    'colorblind-sim': 'images',
    'contact-sheet': 'images',
    'credits-roll': 'images',
    'cubemap-pack': 'images',
    'cue-sheet': 'audio',
    'curve-gen': 'data',
    'curve-trace': 'data',
    'data-diff': 'data',
    'data-to-godot': 'godot',
    'dialogue-extract': 'dialogue',
    'dialogue-graph': 'dialogue',
    'dialogue-lint': 'dialogue',
    'dialogue-stats': 'dialogue',
    'dialogue-to-ink': 'dialogue',
    'dialogue-to-yarn': 'dialogue',
    'drop-sim': 'data',
    'dungeon-gen': 'maps',
    'fleet-jobs': 'data',
    'font-check': 'fonts',
    'font-preview': 'fonts',
    'font-subset': 'fonts',
    'font-to-godot': 'godot',
    'frame-timing-check': 'animation',
    'frames-to-sheet': 'sprites',
    'game-data-lint': 'data',
    'gif-optimize': 'images',
    'gif-to-frames': 'animation',
    'glb-attr-drop': 'mesh',
    'glb-attr-rename': 'mesh',
    'glb-center': 'mesh',
    'glb-diff': 'mesh',
    'glb-extras-strip': 'mesh',
    'glb-lod': 'mesh',
    'glb-merge': 'mesh',
    'glb-quantize': 'mesh',
    'glb-rename-nodes': 'mesh',
    'glb-split': 'mesh',
    'glb-uv-transform': 'mesh',
    'glb-weld': 'mesh',
    'gltf-inspect': 'mesh',
    'gltf-strip': 'mesh',
    'godot-import-presets': 'godot',
    'godot-res-lint': 'godot',
    'godot-tileset': 'godot',
    'heightmap-tools': 'terrain',
    'hitbox-gen': 'sprites',
    'hitbox-to-godot': 'godot',
    'icon-gen': 'images',
    'image-diff': 'images',
    'input-map-lint': 'data',
    'jump-arc': 'data',
    'ldtk-to-csv': 'maps',
    'ldtk-to-tiled': 'maps',
    'level-budget': 'maps',
    'level-curve': 'data',
    'lit-preview': 'images',
    'loc-check': 'loc',
    'loc-convert': 'loc',
    'loc-diff': 'loc',
    'loc-fill': 'loc',
    'loc-fit': 'loc',
    'loc-icu-extract': 'loc',
    'loc-join': 'loc',
    'loc-key-lint': 'loc',
    'loc-merge': 'loc',
    'loc-missing': 'loc',
    'loc-placeholder-lint': 'loc',
    'loc-plurals': 'loc',
    'loc-rename': 'loc',
    'loc-sort': 'loc',
    'loc-split': 'loc',
    'loc-stats': 'loc',
    'loc-to-godot': 'godot',
    'loop-finder': 'audio',
    'loop-xfade': 'audio',
    'lut-tool': 'images',
    'map-auto-layer': 'maps',
    'map-blank': 'maps',
    'map-chunk': 'maps',
    'map-clean': 'maps',
    'map-crop': 'maps',
    'map-diff': 'maps',
    'map-fill': 'maps',
    'map-layer-merge': 'maps',
    'map-layer-rename': 'maps',
    'map-layer-split': 'maps',
    'map-merge': 'maps',
    'map-mirror': 'maps',
    'map-objects-to-godot': 'godot',
    'map-outline': 'maps',
    'map-pad': 'maps',
    'map-path': 'maps',
    'map-reach': 'maps',
    'map-reorder': 'maps',
    'map-rotate': 'maps',
    'map-scale': 'maps',
    'map-shift': 'maps',
    'map-stamp': 'maps',
    'map-to-godot': 'godot',
    'material-audit': 'mesh',
    'mesh-colliders': 'mesh',
    'mesh-pivot-fix': 'mesh',
    'nav-grid': 'maps',
    'nav-to-godot': 'godot',
    'nine-slice': 'sprites',
    'nine-slice-to-godot': 'godot',
    'normal-bake': 'images',
    'normal-fix': 'images',
    'obj-bounds': 'mesh',
    'obj-clean-uv': 'mesh',
    'obj-decimate': 'mesh',
    'obj-drop-unused': 'mesh',
    'obj-flip': 'mesh',
    'obj-merge': 'mesh',
    'obj-normals': 'mesh',
    'obj-recenter': 'mesh',
    'obj-split': 'mesh',
    'obj-subdivide': 'mesh',
    'obj-to-glb': 'mesh',
    'obj-transform': 'mesh',
    'obj-triangulate': 'mesh',
    'obj-uv-unwrap': 'mesh',
    'obj-validate': 'mesh',
    'obj-weld': 'mesh',
    'onion-skin': 'sprites',
    'palette-apply': 'sprites',
    'palette-extract': 'sprites',
    'palette-swap': 'sprites',
    'parallax-preview': 'images',
    'particle-preview': 'images',
    'patch-pack': 'images',
    'pixel-lint': 'sprites',
    'pixelize': 'sprites',
    'prefab-index': 'maps',
    'pseudoloc': 'loc',
    'room-graph': 'maps',
    'sfx-bank': 'audio',
    'sfx-envelope': 'audio',
    'sfx-gen': 'audio',
    'sfx-mix': 'audio',
    'sfx-normalize': 'audio',
    'sfx-pitch': 'audio',
    'sfx-reverse': 'audio',
    'sfx-spectrogram': 'audio',
    'sfx-variants': 'audio',
    'sheet-pad': 'sprites',
    'sprite-align': 'sprites',
    'sprite-angles': 'sprites',
    'sprite-canvas': 'sprites',
    'sprite-flip-sheet': 'sprites',
    'sprite-fx': 'sprites',
    'sprite-outline-gen': 'sprites',
    'sprite-pad': 'sprites',
    'sprite-pivot': 'sprites',
    'sprite-recolor': 'sprites',
    'sprite-reframe': 'sprites',
    'sprite-rotate': 'sprites',
    'sprite-scale': 'sprites',
    'sprite-shadow': 'sprites',
    'sprite-sheet-optimize': 'sprites',
    'sprite-slice': 'sprites',
    'sprite-stack': 'sprites',
    'sprite-trim': 'sprites',
    'sprite-unpad': 'sprites',
    'spritesheet-gif': 'animation',
    'subtitle-timing': 'dialogue',
    'team-outline': 'sprites',
    'terrain-erode': 'terrain',
    'terrain-mesh': 'terrain',
    'terrain-noise': 'terrain',
    'tex-gen': 'images',
    'text-wrap-bake': 'fonts',
    'texture-budget': 'images',
    'texture-resize': 'images',
    'texture-seamless': 'images',
    'tile-anim-gif': 'maps',
    'tile-colliders': 'maps',
    'tile-colliders-to-godot': 'godot',
    'tile-dedupe': 'maps',
    'tile-extrude': 'maps',
    'tile-preview': 'maps',
    'tile-replace': 'maps',
    'tilemap-convert': 'maps',
    'tilemap-stats': 'maps',
    'tileset-from-image': 'maps',
    'tileset-gen': 'maps',
    'tileset-merge': 'maps',
    'tileset-renumber': 'maps',
    'tileset-split': 'maps',
    'tileset-wang': 'maps',
    'tmx-anim-list': 'maps',
    'tmx-decode': 'maps',
    'tmx-embed-tileset': 'maps',
    'tmx-encode': 'maps',
    'tmx-gid-usage': 'maps',
    'tmx-infinite-to-finite': 'maps',
    'tmx-layer-export': 'maps',
    'tmx-layer-filter': 'maps',
    'tmx-layer-opacity': 'maps',
    'tmx-object-types': 'maps',
    'tmx-objects-csv': 'maps',
    'tmx-props-lint': 'maps',
    'tmx-tileset-list': 'maps',
    'tmx-to-json': 'maps',
    'tmx-world': 'maps',
    'uv-check': 'mesh',
    'vo-diff': 'dialogue',
    'voice-slate': 'dialogue',
    'wav-batch-meta': 'audio',
    'wav-chan-split': 'audio',
    'wav-chan-swap': 'audio',
    'wav-dc-remove': 'audio',
    'wav-fade': 'audio',
    'wav-gain': 'audio',
    'wav-gap-squeeze': 'audio',
    'wav-gate': 'audio',
    'wav-invert': 'audio',
    'wav-limit': 'audio',
    'wav-loop-meta': 'audio',
    'wav-loop-snap': 'audio',
    'wav-loud-apply': 'audio',
    'wav-mono': 'audio',
    'wav-pad': 'audio',
    'wav-resample': 'audio',
    'wav-silence': 'audio',
    'wav-split-silence': 'audio',
    'wav-trim': 'audio',
    'wfc-tiles': 'maps',
}

KNOWN_CATEGORIES = (
    "animation", "audio", "data", "dialogue", "fonts", "godot", "images",
    "loc", "maps", "mesh", "sprites", "terrain",
)


def category_of(name):
    return CATEGORIES.get(name, "other")


def parse_category_args(args, extra_help=""):
    """Return (category_or_None, keywords) from [--category CAT] [KEYWORD...]. Exit 2 on bad flags."""
    cat, words, i = None, [], 0
    while i < len(args):
        a = args[i]
        if a in ("-h", "--help"):
            return "__help__", []
        if a in ("--category", "-c") and i + 1 < len(args):
            cat = args[i + 1]; i += 2; continue
        if a.startswith("--category="):
            cat = a.split("=", 1)[1]; i += 1; continue
        if a.startswith("-"):
            print(f"gst: unknown option {a!r}. {extra_help}", file=sys.stderr); sys.exit(2)
        words.append(a); i += 1
    if cat is not None and cat not in KNOWN_CATEGORIES:
        print("gst: unknown category %r. Choose from: %s." % (cat, ", ".join(KNOWN_CATEGORIES)), file=sys.stderr)
        sys.exit(2)
    return cat, words


def search_haystack(name, path):
    """Lowercase name + category + first paragraph (not truncated) for keyword search."""
    try:
        doc = ast.get_docstring(ast.parse(open(path, encoding="utf-8").read())) or ""
    except SyntaxError:
        doc = ""
    para = " ".join(doc.strip().split("\n\n")[0].split())
    prefix = name + ": "
    if para.startswith(prefix): para = para[len(prefix):]
    return " ".join((name, category_of(name), name.replace("-", " "), para)).lower()




def version():
    try: return open(os.path.join(ROOT, "VERSION")).read().strip()
    except OSError: return "unknown"


def run_tool(name, args):
    path = tools()[name]
    sys.argv = [path] + list(args)
    sys.path.insert(0, os.path.dirname(path))
    try:
        runpy.run_path(path, run_name="__main__")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else (print(e.code, file=sys.stderr) or 1))
    except KeyboardInterrupt:
        raise
    except Exception as e:
        sys.path.insert(0, os.path.join(ROOT, "lib"))
        import cli_error
        if cli_error.debug_enabled():
            raise
        print(cli_error.format_error(e), file=sys.stderr)
        return 1
    return 0


def cmd_list(args):
    if args and args[0] in ("--categories",):
        return cmd_categories()
    cat, extra = parse_category_args(args, extra_help="Try `gst list --category maps`.")
    if cat == "__help__":
        print("usage: gst list [--category CAT]\n       gst list --categories")
        return 0
    if extra:
        print("gst list does not take keywords (use `gst search`).", file=sys.stderr); return 2
    t = tools()
    if cat:
        t = {n: p for n, p in t.items() if category_of(n) == cat}
        if not t:
            print(f"gst: no tools in category {cat!r}.", file=sys.stderr); return 1
    w = max(map(len, t), default=0)
    for n, p in t.items():
        print(f"{n:<{w}}  [{category_of(n)}]  {first_line(p)}")
    print(f"\n{len(t)} tools" + (f" in category {cat}" if cat else "") + ". Run `gst <tool> --help` for options; `gst search KEYWORD` to find one.")
    return 0


def cmd_categories():
    t = tools()
    counts = {c: 0 for c in KNOWN_CATEGORIES}
    other = 0
    for n in t:
        c = category_of(n)
        if c in counts: counts[c] += 1
        else: other += 1
    w = max(map(len, KNOWN_CATEGORIES))
    for c in KNOWN_CATEGORIES:
        print(f"{c:<{w}}  {counts[c]}")
    if other: print(f"{'other':<{w}}  {other}")
    print(f"\n{len(t)} tools in {len(KNOWN_CATEGORIES)} categories. Run `gst list --category CAT` or `gst search --category CAT`.")
    return 0


def cmd_search(args):
    cat, words = parse_category_args(args, extra_help="Try `gst search atlas` or `gst search --category maps`.")
    if cat == "__help__":
        print("usage: gst search [--category CAT] KEYWORD [KEYWORD...]")
        return 0
    if not words and not cat:
        print("usage: gst search [--category CAT] KEYWORD [KEYWORD...]", file=sys.stderr); return 2
    t = tools()
    if cat:
        t = {n: p for n, p in t.items() if category_of(n) == cat}
    keys = [w.lower() for w in words]
    hits = []
    for n, p in t.items():
        hay = search_haystack(n, p)
        if all(k in hay for k in keys):
            hits.append((n, p))
    if not hits:
        print("no tools matched " + " ".join(repr(w) for w in words) + (f" in category {cat}" if cat else "") + ". Try `gst list` or `gst categories`.")
        return 1
    w = max(len(n) for n, _ in hits)
    for n, p in hits:
        print(f"{n:<{w}}  [{category_of(n)}]  {first_line(p)}")
    print(f"\n{len(hits)} tool(s) matched.")
    return 0


def cmd_info(name):
    t = tools()
    if name not in t: return unknown(name)
    r = os.path.join(ROOT, name, "README.md"); print(f"{name}: {os.path.relpath(t[name], ROOT)}")
    if os.path.exists(r):
        lines = open(r, encoding="utf-8").read().splitlines(); print("\n".join(lines[:5]).strip())
    return 0


def unknown(name):
    close = difflib.get_close_matches(name, list(tools()) + sorted(RESERVED), n=3, cutoff=0.5)
    print(f"gst: unknown tool or command {name!r}." + (f" Did you mean: {', '.join(close)}?" if close else "") + " Try `gst list`.", file=sys.stderr)
    return 2


def cmd_doctor():
    ok = True
    def line(status, what, note=""): print(f"{status:<5} {what}" + (f"  ({note})" if note else ""))
    v = sys.version_info
    if v >= (3, 10): line("ok", f"python {v.major}.{v.minor}.{v.micro}")
    else: line("FAIL", f"python {v.major}.{v.minor}", "3.10 or newer is required"); ok = False
    for mod, req in (("PIL", True), ("numpy", True), ("fontTools", False), ("pytest", False)):
        if importlib.util.find_spec(mod):
            try: ver = getattr(importlib.import_module(mod), "__version__", "") or getattr(importlib.import_module(mod), "VERSION", "")
            except Exception as e: ver = f"import error: {e}"
            line("ok", f"{mod} {ver}".strip())
        elif req: line("FAIL", mod, "required: pip install -r requirements.txt"); ok = False
        else: line("warn", mod, "optional: " + {"fontTools": "font-check falls back to rendering", "pytest": "needed for `gst test`"}[mod])
    for b, why in (("ffmpeg", "audio-convert, loudness"), ("ffprobe", "audio-convert")):
        line("ok" if shutil.which(b) else "warn", b, "" if shutil.which(b) else f"optional: {why}")
    t = tools(); bad = [n for n, p in t.items() if first_line(p) == "(syntax error)"]
    line("ok" if not bad else "FAIL", f"{len(t)} tools found", ", ".join(bad)); ok = ok and not bad
    return 0 if ok else 1


def cmd_test(args):
    if not importlib.util.find_spec("pytest"): print("pytest is not installed (pip install -r requirements-dev.txt)", file=sys.stderr); return 1
    tdir = os.path.join(ROOT, "tests")
    if not os.path.isdir(tdir): print("this install has no tests/ folder (install with --with-tests)", file=sys.stderr); return 1
    return subprocess.call([sys.executable, "-m", "pytest", "-q", tdir] + list(args), cwd=ROOT)


COMPLETION = """_gst() {
  local cur="${COMP_WORDS[COMP_CWORD]}"
  if [ "$COMP_CWORD" -eq 1 ]; then COMPREPLY=( $(compgen -W "%s" -- "$cur") ); else COMPREPLY=( $(compgen -f -- "$cur") ); fi
}
complete -F _gst gst
"""


def cmd_bundle(args):
    if args[:1] in (["-h"], ["--help"]):
        print("usage: gst bundle -o DIR\nWrite a reproducible .tar.gz of the kit plus a .sha256 file.\n-o/--out is required.")
        return 0
    if not (args[:1] in (["-o"], ["--out"]) and len(args) > 1):
        print("usage: gst bundle -o DIR", file=sys.stderr); return 2
    out = args[1]
    os.makedirs(out, exist_ok=True)
    name = f"gamestudio-tools-{version()}"; path = os.path.join(out, name + ".tar.gz"); files = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = sorted(d for d in dn if d not in BUNDLE_SKIP_DIRS)
        if os.path.dirname(os.path.relpath(dp, ROOT)) == "examples":
            dn[:] = [d for d in dn if d != "work"]     # examples/<game>/work is build.sh scratch (gitignored, rebuildable)
        for f in sorted(fn):
            if f in BUNDLE_SKIP_FILES or f.endswith((".pyc", ".tar.gz", ".sha256", ".uid")): continue
            files.append(os.path.join(dp, f))
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for f in files:
            rel = os.path.relpath(f, ROOT); ti = tarfile.TarInfo(f"{name}/{rel}"); st = os.stat(f)
            ti.size = st.st_size; ti.mtime = 0; ti.uid = ti.gid = 0; ti.uname = ti.gname = ""; ti.mode = 0o755 if os.access(f, os.X_OK) else 0o644
            with open(f, "rb") as fh: tar.addfile(ti, fh)
    with open(path, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz: gz.write(raw.getvalue())
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    open(path + ".sha256", "w").write(f"{digest}  {os.path.basename(path)}\n")
    print(f"{path}  ({len(files)} files, {os.path.getsize(path)} bytes)\nsha256 {digest}")
    return 0




def cmd_fuzz(args):
    if args[:1] in (["-h"], ["--help"]):
        print("usage: gst fuzz [--fast|--long] [--debug] [--seed N] [--timeout T] [-o REPORT.json] [TOOL ...]")
        print("Feed truncated, bit-flipped, empty, random-byte and fully-random inputs to every tool that reads")
        print("WAV, PNG/GIF, Tiled JSON/TMX, GLB/glTF, OBJ, atlas JSON, CSV loc, Yarn/ink, BMFont or Aseprite.")
        print("A fully-random input (no leftover structure from the seed) must exit 1 or 2, not 0.")
        print("--fast uses tiny generated seeds (the default for the test suite). --long also mutates")
        print("files under samples/ when that folder is present (source tree only; not in the tarball).")
        return 0
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from fuzz.harness import main as fuzz_main
    return fuzz_main(args)


def cmd_docs(args):
    out, i = None, 0
    while i < len(args):
        if args[i] in ("-h", "--help"):
            print("usage: gst docs -o DIR"); return 0
        if args[i] in ("-o", "--out", "--outdir") and i + 1 < len(args):
            out = args[i + 1]; i += 2; continue
        print("usage: gst docs -o DIR", file=sys.stderr); return 2
    if not out:
        print("usage: gst docs -o DIR", file=sys.stderr); return 2
    sys.path.insert(0, os.path.join(ROOT, "lib"))
    import docs_site
    rec = docs_site.build(ROOT, out)
    print(f"docs site: {rec['tools']} tool pages, {rec['pipelines']} pipeline(s) -> {out}")
    return 0


def main(argv):
    if not argv or argv[0] in ("-h", "--help"): print(__doc__.strip()); return 0
    c, rest = argv[0], argv[1:]
    if c == "list": return cmd_list(rest)
    if c == "categories": return cmd_categories()
    if c == "search": return cmd_search(rest)
    if c == "version": print(f"gamestudio-tools {version()} ({len(tools())} tools)"); return 0
    if c == "doctor": return cmd_doctor()
    if c == "test": return cmd_test(rest)
    if c == "bundle": return cmd_bundle(rest)
    if c == "docs": return cmd_docs(rest)
    if c == "fuzz": return cmd_fuzz(rest)
    if c == "info": return cmd_info(rest[0]) if rest else unknown("")
    if c == "completion":
        if rest[:1] != ["bash"]: print("usage: gst completion bash", file=sys.stderr); return 2
        print(COMPLETION % " ".join(sorted(list(tools()) + sorted(RESERVED)))); return 0
    if c == "help":
        if not rest: print(__doc__.strip()); return 0
        c, rest = rest[0], ["--help"]
    if c in tools(): return run_tool(c, rest)
    return unknown(c)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
