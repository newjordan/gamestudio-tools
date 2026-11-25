#!/usr/bin/env python3
"""texture-budget: scan a folder of textures and report estimated GPU memory.

Each image contributes `width * height * bytes-per-pixel` (and, unless
`--no-mips`, an extra 1/3 for a full mip chain). NPOT sizes, edges over
`--max-edge`, and a total over `--fail-over-mb` are flagged. Does not
recompress or rewrite files. The folder is never overwritten.
"""
import argparse, json, os, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import safe_out  # noqa: E402

EXTS = {".png", ".jpg", ".jpeg", ".webp", ".tga", ".bmp", ".gif", ".tif", ".tiff"}

BPP = {
    "RGB": 3, "RGBA": 4, "L": 1, "LA": 2, "P": 1, "CMYK": 4,
    "I": 4, "F": 4, "PA": 2, "1": 1,
}


def is_pot(n):
    return n >= 1 and (n & (n - 1)) == 0


def collect(root):
    out = []
    if os.path.isfile(root):
        return [root]
    if not os.path.isdir(root):
        raise GstInputError("not a file or directory: %s" % root)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in (".git", "__pycache__", ".godot")]
        for fn in fns:
            if os.path.splitext(fn)[1].lower() in EXTS:
                out.append(os.path.join(dp, fn))
    return sorted(out)


def measure(path, mips=True):
    try:
        im = Image.open(path)
        w, h = im.size
        mode = im.mode or "RGBA"
        bpp = BPP.get(mode, 4)
    except GstInputError:
        raise
    except Exception as e:
        raise GstInputError("image file is not valid: %s" % e) from e
    raw = w * h * bpp
    vram = int(raw * (4 / 3)) if mips and w > 1 and h > 1 else raw
    return {
        "file": path,
        "width": w, "height": h, "mode": mode, "bpp": bpp,
        "pixels": w * h, "bytes": raw, "vram_bytes": vram,
        "npot": not (is_pot(w) and is_pot(h)),
        "max_edge": max(w, h),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Estimate VRAM for a folder of textures.")
    ap.add_argument("root")
    ap.add_argument("--no-mips", action="store_true", help="do not add a 1/3 mip-chain estimate")
    ap.add_argument("--max-edge", type=int, default=0, help="flag images whose longest edge exceeds this (0 = off)")
    ap.add_argument("--fail-over-mb", type=float, default=0, help="exit 1 if total VRAM exceeds this many MiB (0 = off)")
    ap.add_argument("--json")
    ap.add_argument("-o", "--out", help="write a text report")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    if a.out:
        safe_out.check(a.root, a.out, a.in_place)
    if a.json:
        safe_out.check(a.root, a.json, a.in_place)
    files = collect(a.root)
    if not files:
        raise GstInputError("no images found under %s" % a.root)
    rows = [measure(f, mips=not a.no_mips) for f in files]
    total = sum(r["vram_bytes"] for r in rows)
    over_edge = [r for r in rows if a.max_edge and r["max_edge"] > a.max_edge]
    npot = [r for r in rows if r["npot"]]
    rec = {
        "root": a.root, "files": len(rows),
        "vram_bytes": total, "vram_mb": round(total / (1024 * 1024), 3),
        "npot": len(npot), "over_max_edge": len(over_edge),
        "mips": not a.no_mips, "max_edge": a.max_edge,
        "textures": rows,
    }
    lines = [
        "texture-budget: %d file(s), %.2f MiB estimated VRAM%s" % (
            rec["files"], rec["vram_mb"], " (with mips)" if rec["mips"] else ""),
    ]
    for r in rows:
        flag = []
        if r["npot"]:
            flag.append("NPOT")
        if a.max_edge and r["max_edge"] > a.max_edge:
            flag.append("over-max-edge")
        extra = (" " + ",".join(flag)) if flag else ""
        lines.append("  %s  %dx%d %s  %.1f KiB%s" % (
            os.path.relpath(r["file"], a.root) if os.path.isdir(a.root) else os.path.basename(r["file"]),
            r["width"], r["height"], r["mode"], r["vram_bytes"] / 1024, extra))
    if npot:
        lines.append("%d NPOT texture(s)" % len(npot))
    if over_edge:
        lines.append("%d texture(s) over --max-edge %d" % (len(over_edge), a.max_edge))
    text = "\n".join(lines)
    print(text)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        open(a.out, "w", encoding="utf-8").write(text + "\n")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    if a.fail_over_mb and rec["vram_mb"] > a.fail_over_mb:
        return 1
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
