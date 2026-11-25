#!/usr/bin/env python3
"""credits-roll: render a scrolling credits review GIF from a UTF-8 text file.
Plain lines are body text; a line starting with # is a heading (larger); a blank line is a gap.
The roll starts just below the frame and scrolls up at --speed pixels per second until the last line
has left the top, plus a short --hold. Pillow's default font is used, or a TTF via --font. Palette GIF
flattened onto --bg. No complex-script shaping.
"""
import argparse, os, sys

from PIL import Image, ImageDraw, ImageFont


def load_font(path, size):
    if path: return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


def measure(draw, text, font):
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render a scrolling credits GIF from a text file.")
    ap.add_argument("text"); ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--width", type=int, default=320); ap.add_argument("--height", type=int, default=180)
    ap.add_argument("--speed", type=float, default=40, help="pixels per second")
    ap.add_argument("--fps", type=int, default=12); ap.add_argument("--body-size", type=int, default=14)
    ap.add_argument("--head-size", type=int, default=22); ap.add_argument("--gap", type=int, default=10)
    ap.add_argument("--hold-ms", type=int, default=400); ap.add_argument("--font")
    ap.add_argument("--color", default="f0f0f0"); ap.add_argument("--head-color", default="ffe680")
    ap.add_argument("--bg", default="101018"); ap.add_argument("--png", help="write the mid-roll frame as a PNG")
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
    _src_keys = ('text',)
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

    lines = open(a.text, encoding="utf-8").read().splitlines()
    def col(s):
        s = s.lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    fg, hg, bg = col(a.color), col(a.head_color), col(a.bg)
    body, head = load_font(a.font, a.body_size), load_font(a.font, a.head_size)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    blocks, y = [], 0
    for line in lines:
        if not line.strip():
            y += a.gap * 2; continue
        is_head = line.startswith("#")
        text = line[1:].strip() if is_head else line.strip()
        font, color = (head, hg) if is_head else (body, fg)
        w, h = measure(probe, text, font)
        blocks.append((y, text, font, color, w, h)); y += h + a.gap
    total_h = y
    travel = a.height + total_h  # start just below, end just above
    n = max(2, int(round((travel / max(a.speed, 1)) * a.fps)))
    hold = max(0, int(round(a.hold_ms / 1000 * a.fps)))
    frames = []
    for i in range(n + hold):
        # offset: 0 -> first line at bottom; travel -> last line above top
        t = min(i, n - 1) / max(n - 1, 1)
        origin = a.height - t * travel
        im = Image.new("RGB", (a.width, a.height), bg)
        dr = ImageDraw.Draw(im)
        for by, text, font, color, w, h in blocks:
            yy = origin + by
            if yy + h < 0 or yy > a.height: continue
            dr.text(((a.width - w) / 2, yy), text, font=font, fill=color)
        frames.append(im)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=int(1000 / a.fps), loop=0, dispose=2)
    print(f"{len(lines)} line(s), {len(frames)} frame(s) at {a.width}x{a.height} -> {a.out}")
    if a.png:
        mid = frames[len(frames) // 2]; mid.save(a.png)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
