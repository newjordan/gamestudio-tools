#!/usr/bin/env python3
"""godot-import-presets: bulk-write Godot 4 `.import` files so pixel art, UI, albedo and normal
textures (and loopable WAVs) get the right import settings without clicking through the editor.

  rules.json: {"rules": [{"glob": "art/sprites/**/*.png", "preset": "pixel"}, ...]}  (first match wins)
Presets: pixel (lossless, no mipmaps, fix alpha border), ui (lossless, no mipmaps), albedo3d (VRAM
compressed, mipmaps), normal3d (VRAM compressed normal map, mipmaps), wav-loop / wav-oneshot.
`--project-snippet` prints the project.godot lines for nearest-neighbour defaults (the safest route).

STATUS: verified in official Godot 4.7.2.stable.official.ed1daf0bf (`--headless --import`; the editor
fills in uid/dest paths). `**` in rule globs is path-style (zero or more directories). Use --dry-run,
try one folder first. Existing .import files are skipped unless --force.
"""
import argparse, os, fnmatch, json, sys

TEX = {
    "importer": "texture", "type": "CompressedTexture2D",
    "base": {"compress/mode": 0, "compress/high_quality": False, "compress/lossy_quality": 0.7,
             "compress/hdr_compression": 1, "compress/normal_map": 0, "compress/channel_pack": 0,
             "mipmaps/generate": False, "mipmaps/limit": -1, "roughness/mode": 0, "roughness/src_normal": "",
             "process/fix_alpha_border": True, "process/premult_alpha": False, "process/normal_map_invert_y": False,
             "process/hdr_as_srgb": False, "process/hdr_clamp_exposure": False, "process/size_limit": 0,
             "detect_3d/compress_to": 1},
}
PRESETS = {
    "pixel": ("texture", {}),
    "ui": ("texture", {"process/fix_alpha_border": True}),
    "albedo3d": ("texture", {"compress/mode": 2, "compress/high_quality": True, "mipmaps/generate": True}),
    "normal3d": ("texture", {"compress/mode": 2, "compress/normal_map": 1, "mipmaps/generate": True,
                             "roughness/mode": 0, "process/fix_alpha_border": False}),
    # Godot 4 WAV importer edit/loop_mode: 0 Detect From WAV, 1 Disabled, 2 Forward, 3 Ping-Pong, 4 Backward.
    # wav-loop keeps loop points embedded in a smpl chunk (wav-loop-meta / loop-finder) by using Detect;
    # a WAV without one loops whole-file Forward. wav-oneshot is Disabled so a stray smpl chunk never loops.
    "wav-loop": ("wav", {"edit/loop_mode": 2, "edit/loop_begin": 0, "edit/loop_end": -1}),
    "wav-oneshot": ("wav", {"edit/loop_mode": 1}),
}
WAV_BASE = {"force/8_bit": False, "force/mono": False, "force/max_rate": False, "force/max_rate_hz": 44100,
            "edit/trim": False, "edit/normalize": False, "edit/loop_mode": 0, "edit/loop_begin": 0,
            "edit/loop_end": -1, "compress/mode": 0}


def wav_has_loop(path):
    """True when a RIFF/WAVE file carries a smpl chunk with at least one loop."""
    try:
        with open(path, "rb") as f:
            head = f.read(12)
            if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
                return False
            while True:
                ch = f.read(8)
                if len(ch) < 8:
                    return False
                cid, size = ch[:4], int.from_bytes(ch[4:], "little")
                if cid == b"smpl":
                    body = f.read(min(size, 64))
                    return len(body) >= 32 and int.from_bytes(body[28:32], "little") > 0
                f.seek(size + (size & 1), 1)
    except OSError:
        return False


def fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, str):
        return '"' + v.replace('"', '\\"') + '"'
    return repr(v)


def render(res_path, preset, overrides=None):
    kind, delta = PRESETS[preset]
    if kind == "texture":
        params = {**TEX["base"], **delta, **(overrides or {})}
        importer, typ = TEX["importer"], TEX["type"]
    else:
        params = {**WAV_BASE, **delta, **(overrides or {})}
        importer, typ = "wav", "AudioStreamWAV"
    lines = ["[remap]", "", f'importer="{importer}"', f'type="{typ}"', "", "[deps]", "", f'source_file="{res_path}"', "",
             "[params]", ""]
    lines += [f"{k}={fmt(v)}" for k, v in params.items()]
    return "\n".join(lines) + "\n"


def glob_match(rel, pattern):
    """Path-style glob: * matches one path segment, ** matches zero or more directories."""
    rel = rel.replace("\\", "/")
    pattern = pattern.replace("\\", "/")
    if pattern.startswith("**/") and glob_match(rel, pattern[3:]):
        return True
    return _glob_parts(rel.split("/"), pattern.split("/"))


def _glob_parts(parts, pats):
    if not pats:
        return not parts
    if pats[0] == "**":
        if len(pats) == 1:
            return True
        return any(_glob_parts(parts[i:], pats[1:]) for i in range(len(parts) + 1))
    if not parts:
        return False
    if fnmatch.fnmatchcase(parts[0], pats[0]):
        return _glob_parts(parts[1:], pats[1:])
    return False


def plan(root, rules):
    out = []
    for dp, _, files in os.walk(root):
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/")
            for r in rules:
                if glob_match(rel, r["glob"]):
                    out.append((rel, r["preset"], r.get("params")))
                    break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write Godot 4 .import files from glob rules.")
    ap.add_argument("project", nargs="?", help="Godot project root (contains project.godot)")
    ap.add_argument("-r", "--rules", help="rules JSON")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--project-snippet", action="store_true", help="print project.godot pixel-art defaults")
    a = ap.parse_args(argv)
    if a.project_snippet:
        print('[rendering]\n\ntextures/canvas_textures/default_texture_filter=0\n2d/snap/snap_2d_transforms_to_pixel=true\n2d/snap/snap_2d_vertices_to_pixel=true')
        return 0
    if not a.project or not a.rules:
        ap.error("project and --rules are required")
    rules = json.load(open(a.rules))["rules"]
    for r in rules:
        if r["preset"] not in PRESETS:
            sys.exit(f"unknown preset {r['preset']}; choose from {', '.join(PRESETS)}")
    written = skipped = 0
    for rel, preset, params in plan(a.project, rules):
        dest = os.path.join(a.project, rel + ".import")
        if os.path.exists(dest) and not a.force:
            skipped += 1
            continue
        if preset == "wav-loop" and not (params or {}).get("edit/loop_mode") and \
                wav_has_loop(os.path.join(a.project, rel)):
            params = {**(params or {}), "edit/loop_mode": 0}     # Detect: honour the embedded loop points
        txt = render("res://" + rel, preset, params)
        if a.dry_run:
            print(f"[dry-run] {rel}.import  <- {preset}")
        else:
            open(dest, "w").write(txt)
        written += 1
    print(f"{'would write' if a.dry_run else 'wrote'} {written} .import file(s), skipped {skipped} existing")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
