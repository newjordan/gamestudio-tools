#!/usr/bin/env python3
"""spritesheet-gif: render an animation from a sprite sheet plus a clips JSON to a GIF, for review links and pull-request
previews. The sheet is an atlas PNG with atlas-pack / ase-json-import JSON (hash or array layout); clips are anim-meta /
ase-json-import style ({"clips": {"walk": {"frames": [...], "fps" or "durations_ms"}}}). Phaser anims JSON is also accepted.
Trimmed frames are reconstructed onto their sourceSize canvas (spriteSourceSize offsets are honoured) so the GIF does not
jitter. A frames.json / bounce-style sheet with duration_ms is treated as one clip. --clip NAME writes one GIF; the default
is one GIF per clip named <out-dir>/<clip>.gif. --scale uses nearest-neighbour. Frames are flattened onto --bg (GIF has no
real RGBA). Duration comes from durations_ms, or 1000/fps, or --fps.
"""
import argparse, os, json, sys

from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frame-timing-check"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sprite-sheet-optimize"))
import frame_timing_check, sprite_sheet_optimize  # noqa: E402


def parse_color(s):
    s = (s or "202028").lstrip("#"); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def reconstruct(sheet, frames, name, bg):
    if name not in frames: raise SystemExit(f"clip refers to frame {name!r}, which is not in the atlas JSON")
    e = frames[name]; src = e.get("sourceSize") or {"w": e["frame"]["w"], "h": e["frame"]["h"]}
    canvas = Image.new("RGBA", (src["w"], src["h"]), (0, 0, 0, 0))
    f, s = e["frame"], e.get("spriteSourceSize") or {"x": 0, "y": 0, "w": e["frame"]["w"], "h": e["frame"]["h"]}
    crop = sheet.crop((f["x"], f["y"], f["x"] + f["w"], f["y"] + f["h"]))
    canvas.paste(crop, (s.get("x", 0), s.get("y", 0)), crop)
    if bg is not None:
        base = Image.new("RGBA", canvas.size, bg + (255,)); return Image.alpha_composite(base, canvas)
    return canvas


def load_atlas_frames(meta, path):
    # sprite_sheet_optimize.load_frames wants the raw meta and returns name/rect/src/off; we need the original dicts too
    fr = meta.get("frames")
    if isinstance(fr, dict): return fr
    if isinstance(fr, list) and fr and "frame" in fr[0]:
        return {(f.get("filename") or f.get("name") or str(i)): f for i, f in enumerate(fr)}
    if isinstance(fr, list) and fr and "duration_ms" in fr[0] and "x" in fr[0]:
        # bounce_sheet style: build frame dicts from x,y,w,h
        return {(f.get("file") or f.get("filename") or str(f.get("index", i))): {"frame": {"x": f["x"], "y": f["y"], "w": f["w"], "h": f["h"]},
                 "sourceSize": {"w": f["w"], "h": f["h"]}, "spriteSourceSize": {"x": 0, "y": 0, "w": f["w"], "h": f["h"]}} for i, f in enumerate(fr)}
    raise SystemExit("atlas JSON has no usable frames")


def durations(clip, fps_override):
    d = list(clip.get("durations_ms") or [])
    n = len(clip.get("frames") or [])
    if d and len(d) == n: return [max(1, int(x)) for x in d]
    fps = fps_override or clip.get("fps") or 12
    return [max(1, int(round(1000 / float(fps))))] * n


def render_clip(sheet, atlas_frames, clip, bg, scale=1):
    frames, durs = [], durations(clip, None)
    for name, d in zip(clip["frames"], durs):
        im = reconstruct(sheet, atlas_frames, name, bg)
        if scale != 1: im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
        frames.append((im.convert("RGBA"), d))
    return frames


def write_gif(path, frames, loop=True):
    if not frames: raise SystemExit("clip has no frames")
    ims = [f.convert("RGB") for f, _ in frames]
    ims[0].save(path, save_all=True, append_images=ims[1:], duration=[d for _, d in frames], loop=0 if loop else 1, dispose=2)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Render sheet + clips JSON to a GIF.")
    ap.add_argument("atlas", help="atlas JSON (or a bounce/frames JSON that already has x,y,w,h)"); ap.add_argument("--image", help="atlas PNG (default: meta.image next to the JSON)")
    ap.add_argument("--clips", help="clips JSON (default: the atlas file, if it already has clips or anims or duration_ms frames)")
    ap.add_argument("-o", "--out", required=True, help="output GIF (one clip) or a directory (every clip)")
    ap.add_argument("--clip", help="only this clip"); ap.add_argument("--fps", type=float, help="override frame rate for clips without durations_ms")
    ap.add_argument("--scale", type=int, default=1); ap.add_argument("--bg", default="#202028"); ap.add_argument("--once", action="store_true", help="do not loop the GIF")
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
    _src_keys = ('atlas', 'image')
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

    atlas = json.load(open(a.atlas))
    clips_src = json.load(open(a.clips)) if a.clips else atlas
    if "clips" not in clips_src and "anims" not in clips_src and not (isinstance(clips_src.get("frames"), list) and clips_src["frames"] and "duration_ms" in clips_src["frames"][0]):
        sys.exit("no clips found; pass --clips or a JSON that already contains clips")
    clips = frame_timing_check.load_clips(clips_src, a.clips or a.atlas)
    if a.fps:
        for c in clips.values():
            if not c.get("durations_ms"): c["fps"] = a.fps
    if a.clip:
        if a.clip not in clips: sys.exit(f"no clip {a.clip!r} (have: {', '.join(clips)})")
        clips = {a.clip: clips[a.clip]}
    img = a.image or os.path.join(os.path.dirname(os.path.abspath(a.atlas)), (atlas.get("meta") or {}).get("image") or "")
    if not os.path.isfile(img):
        # bounce-style JSON may sit next to a png of the same stem
        guess = os.path.splitext(a.atlas)[0] + ".png"
        if os.path.isfile(guess): img = guess
        else: sys.exit(f"atlas image not found (use --image): tried {img}")
    sheet = Image.open(img).convert("RGBA")
    atlas_frames = load_atlas_frames(atlas, a.atlas)
    bg = parse_color(a.bg)
    one = len(clips) == 1 and os.path.splitext(a.out)[1].lower() == ".gif"
    if not one: os.makedirs(a.out, exist_ok=True)
    written = []
    for name, c in clips.items():
        frames = render_clip(sheet, atlas_frames, c, bg, a.scale)
        # honour per-clip loop unless --once
        loop = (not a.once) and (c.get("loop") is not False)
        dest = a.out if one else os.path.join(a.out, name + ".gif")
        write_gif(dest, frames, loop); written.append(dest)
        print(f"{name}: {len(frames)} frame(s), {sum(d for _, d in frames)} ms -> {dest}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
