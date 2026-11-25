#!/usr/bin/env python3
"""icon-gen: one square master PNG (ideally 1024x1024) -> every app icon a release needs.
Outputs under --outdir:
  windows/icon.ico (16..256), macos/icon.icns, web/favicon.ico + favicon-<n>.png + icon-192/512.png + icon-maskable-512.png
  android/mipmap-<density>/ic_launcher.png (48..192) + playstore-512.png (+ adaptive foreground at 432 px with the 66% safe zone)
  ios/Icon-<size>.png (no alpha, flattened on --bg; includes the 1024 marketing icon)
Resizing uses Lanczos. Non-square masters are padded to a square and a warning is printed. Maskable and iOS
icons use --bg for the background; --pad adds transparent margin around the art for web/android icons.
"""
import argparse, os, sys
from PIL import Image

ANDROID = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
IOS = [20, 29, 40, 58, 60, 76, 80, 87, 120, 152, 167, 180, 1024]
ICO = [16, 24, 32, 48, 64, 128, 256]
WEB = [16, 32, 48, 180, 192, 512]


def hexc(s): s = s.lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (255,)


def square(img):
    img = img.convert("RGBA"); w, h = img.size
    if w == h: return img, False
    s = max(w, h); c = Image.new("RGBA", (s, s), (0, 0, 0, 0)); c.paste(img, ((s - w) // 2, (s - h) // 2)); return c, True


def padded(img, pct):
    if not pct: return img
    s = img.width; inner = round(s * (1 - 2 * pct / 100)); c = Image.new("RGBA", (s, s), (0, 0, 0, 0)); c.paste(img.resize((inner, inner), Image.LANCZOS), ((s - inner) // 2,) * 2); return c


def at(img, n): return img.resize((n, n), Image.LANCZOS)


def flatten(img, bg):
    c = Image.new("RGBA", img.size, bg); c.alpha_composite(img); return c.convert("RGB")


def generate(master, outdir, bg="#ffffff", pad=0):
    img, warned = square(master); bgc = hexc(bg); made = []
    def put(rel, im):
        p = os.path.join(outdir, rel); os.makedirs(os.path.dirname(p), exist_ok=True); im.save(p); made.append(rel)
    big = padded(at(img, 1024), pad) if pad else at(img, 1024)
    p = os.path.join(outdir, "windows", "icon.ico"); os.makedirs(os.path.dirname(p), exist_ok=True); big.save(p, sizes=[(s, s) for s in ICO]); made.append("windows/icon.ico")
    p = os.path.join(outdir, "macos", "icon.icns"); os.makedirs(os.path.dirname(p), exist_ok=True); at(img, 1024).save(p); made.append("macos/icon.icns")
    p = os.path.join(outdir, "web", "favicon.ico"); os.makedirs(os.path.dirname(p), exist_ok=True); big.save(p, sizes=[(16, 16), (32, 32), (48, 48)]); made.append("web/favicon.ico")
    for n in WEB: put(f"web/favicon-{n}.png" if n < 192 else f"web/icon-{n}.png", at(big, n))
    safe = Image.new("RGBA", (512, 512), bgc); safe.alpha_composite(at(img, round(512 * 0.8)), (round(512 * 0.1),) * 2); put("web/icon-maskable-512.png", safe)
    for d, n in ANDROID.items(): put(f"android/mipmap-{d}/ic_launcher.png", at(big, n))
    put("android/playstore-512.png", at(big, 512))
    fg = Image.new("RGBA", (432, 432), (0, 0, 0, 0)); fg.alpha_composite(at(img, round(432 * 0.66)), (round(432 * 0.17),) * 2); put("android/adaptive-foreground-432.png", fg)
    for n in IOS: put(f"ios/Icon-{n}.png", flatten(at(img, n), bgc))
    return made, warned


def main(argv=None):
    ap = argparse.ArgumentParser(description="App icon set generator.")
    ap.add_argument("master"); ap.add_argument("-o", "--outdir", required=True); ap.add_argument("--bg", default="#ffffff"); ap.add_argument("--pad", type=float, default=0, help="percent margin per side")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv); m = Image.open(a.master)
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
    _src_keys = ('master',)
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

    if min(m.size) < 512: print(f"WARN master is {m.size[0]}x{m.size[1]}; 1024x1024 or larger gives clean results")
    made, warned = generate(m, a.outdir, a.bg, a.pad)
    if warned: print("WARN master is not square; it was centred on a transparent square")
    print(f"{len(made)} file(s) -> {a.outdir}"); return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
