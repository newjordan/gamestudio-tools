#!/usr/bin/env python3
"""particle-preview: bake a simple 2D particle burst (or a short stream) to a review GIF.
Particles are emitted at the origin with a heading and spray, a speed range, gravity, and a lifetime.
A --sprite PNG is drawn with nearest-neighbour (rotated to the velocity if --rotate-sprite); otherwise
square pixels (or circles with --circle) are used. --rate > 0 emits continuously (particles per second)
instead of a single burst of --count. Seeded, CPU only. Palette GIF flattened onto --bg.
"""
import argparse, os, math, random, sys

from PIL import Image, ImageDraw

def hsv(h, s, v, a=255):
    i = int(h * 6); f = h * 6 - i; p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i % 6]
    return (int(r * 255), int(g * 255), int(b * 255), a)


def parse_color(s, a=255):
    s = s.lstrip("#")
    if len(s) == 6: return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4)) + (a,)
    if len(s) == 8: return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4, 6))
    raise SystemExit(f"bad colour {s}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Bake a 2D particle burst to a GIF.")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--width", type=int, default=128); ap.add_argument("--height", type=int, default=128)
    ap.add_argument("--origin", default="", help="x,y (default: centre, slightly above mid)")
    ap.add_argument("--count", type=int, default=24); ap.add_argument("--rate", type=float, default=0, help="emit per second (0 = one burst)")
    ap.add_argument("--heading", type=float, default=-90, help="degrees, 0 is right, -90 is up")
    ap.add_argument("--spray", type=float, default=40, help="total spray width in degrees")
    ap.add_argument("--speed", type=float, default=80, help="pixels per second")
    ap.add_argument("--speed-var", type=float, default=0.3); ap.add_argument("--gravity", type=float, default=180, help="px/s^2, down is positive")
    ap.add_argument("--lifetime-ms", type=int, default=800); ap.add_argument("--life-var", type=float, default=0.25)
    ap.add_argument("--size", type=int, default=4); ap.add_argument("--sprite"); ap.add_argument("--rotate-sprite", action="store_true")
    ap.add_argument("--circle", action="store_true"); ap.add_argument("--color", default="ffcc55")
    ap.add_argument("--bg", default="201820"); ap.add_argument("--frames", type=int, default=24); ap.add_argument("--fps", type=int, default=12)
    ap.add_argument("--seed", type=int, default=1); ap.add_argument("--png", help="also write the first frame as a PNG")
    a = ap.parse_args(argv)
    rng = random.Random(a.seed)
    ox, oy = (a.width / 2, a.height * 0.6) if not a.origin else map(float, a.origin.split(","))
    sprite = Image.open(a.sprite).convert("RGBA") if a.sprite else None
    color = parse_color(a.color); bg = parse_color(a.bg)
    dt = 1.0 / a.fps; n = max(1, a.frames); duration_s = n * dt
    # pre-build particle params
    parts = []
    if a.rate > 0:
        t = 0.0
        while t < duration_s:
            parts.append(t); t += 1.0 / a.rate if a.rate else duration_s
    else:
        parts = [0.0] * a.count
    particles = []
    for born in parts:
        ang = math.radians(a.heading + (rng.random() - 0.5) * a.spray)
        spd = a.speed * (1 + (rng.random() * 2 - 1) * a.speed_var)
        life = (a.lifetime_ms / 1000) * (1 + (rng.random() * 2 - 1) * a.life_var)
        particles.append((born, math.cos(ang) * spd, math.sin(ang) * spd, max(0.05, life)))
    frames = []
    for i in range(n):
        t = i * dt
        im = Image.new("RGBA", (a.width, a.height), bg)
        layer = Image.new("RGBA", (a.width, a.height), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        for born, vx, vy, life in particles:
            age = t - born
            if age < 0 or age > life: continue
            fade = 1 - (age / life)
            x = ox + vx * age
            y = oy + vy * age + 0.5 * a.gravity * age * age
            alpha = max(0, min(255, int(color[3] * fade)))
            if sprite is not None:
                sp = sprite
                if a.rotate_sprite:
                    # rotate so +x of the sprite points along current velocity
                    cvx, cvy = vx, vy + a.gravity * age
                    deg = -math.degrees(math.atan2(cvy, cvx))
                    sp = sp.rotate(deg, resample=Image.NEAREST, expand=True)
                sp = sp.copy(); sp.putalpha(Image.eval(sp.split()[-1], lambda p: int(p * fade)))
                layer.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))
            else:
                s = max(1, int(a.size * (0.5 + 0.5 * fade)))
                col = (color[0], color[1], color[2], alpha)
                box = [int(x - s / 2), int(y - s / 2), int(x + s / 2), int(y + s / 2)]
                if a.circle: dr.ellipse(box, fill=col)
                else: dr.rectangle(box, fill=col)
        im.alpha_composite(layer); frames.append(im.convert("RGB"))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=int(1000 / a.fps), loop=0, dispose=2)
    print(f"{len(particles)} particle(s), {n} frame(s) at {a.width}x{a.height} -> {a.out}")
    if a.png: frames[0].save(a.png); print(f"first frame -> {a.png}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
