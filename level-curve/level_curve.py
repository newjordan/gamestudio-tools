#!/usr/bin/env python3
"""level-curve: build and sanity-check XP / stat / cost curves for N levels.
--kind linear  value = base + step*(L-1)         --kind poly  value = base * L^power
--kind exp     value = base * growth^(L-1)       --kind custom  --anchors "1:100,10:1500,50:90000" (geometric interpolation between anchors)
Columns: level, value (per level), cumulative, ratio to the previous level. --target-total T rescales so the cumulative sum over
all levels is T. --nice rounds to 2 significant digits (designer-friendly numbers); --round N rounds to N decimals (default 0).
--per-hour R estimates hours per level and in total at R units per hour. Warnings: values that fall, ratio spikes above
--spike times the median ratio, and total hours above --max-hours. Output: CSV, JSON, and an SVG chart (--log for a log axis).
"""
import argparse, os, csv, json, math, sys
import numpy as np


def raw(kind, n, base=100.0, step=50.0, power=2.0, growth=1.15, anchors=None):
    L = np.arange(1, n + 1, dtype=float)
    if kind == "linear": return base + step * (L - 1)
    if kind == "poly": return base * L ** power
    if kind == "exp": return base * growth ** (L - 1)
    if kind == "custom":
        if not anchors or len(anchors) < 2: raise SystemExit("custom needs --anchors with at least two level:value pairs")
        xs, ys = zip(*sorted(anchors)); 
        if min(ys) <= 0: raise SystemExit("custom anchors must be positive")
        if xs[0] > 1 or xs[-1] < n: raise SystemExit(f"anchors must cover levels 1..{n}")
        return np.exp(np.interp(L, xs, np.log(ys)))
    raise SystemExit(f"unknown kind {kind}")


def nice(v):
    out = []
    for x in v: out.append(0.0 if x == 0 else round(x, 1 - int(math.floor(math.log10(abs(x))))))
    return np.array(out)


def build(kind, n, target_total=None, use_nice=False, decimals=0, per_hour=None, **kw):
    v = raw(kind, n, **kw)
    if target_total: v = v * (target_total / v.sum())
    v = nice(v) if use_nice else np.round(v, decimals)
    cum = np.cumsum(v); ratio = np.concatenate([[np.nan], v[1:] / np.where(v[:-1] == 0, np.nan, v[:-1])])
    rows = [{"level": i + 1, "value": float(v[i]) if decimals or use_nice else int(v[i]), "cumulative": float(cum[i]) if decimals or use_nice else int(cum[i]), "ratio": None if np.isnan(ratio[i]) else round(float(ratio[i]), 4)} for i in range(n)]
    if per_hour:
        h = v / per_hour; hc = np.cumsum(h)
        for i, r in enumerate(rows): r["hours"] = round(float(h[i]), 3); r["hours_cumulative"] = round(float(hc[i]), 3)
    return rows


def warnings(rows, spike=1.5, max_hours=None):
    w = []; vals = [r["value"] for r in rows]; rs = [r["ratio"] for r in rows if r["ratio"] is not None]
    for i in range(1, len(vals)):
        if vals[i] < vals[i - 1]: w.append(f"level {i + 1}: value falls ({vals[i - 1]} -> {vals[i]})")
    if rs:
        med = float(np.median(rs))
        for r in rows:
            if r["ratio"] is not None and r["ratio"] > med * spike and r["ratio"] > 1.0: w.append(f"level {r['level']}: ratio {r['ratio']} is {r['ratio'] / med:.1f}x the median ratio {med:.3f}")
    if max_hours and rows and "hours_cumulative" in rows[-1] and rows[-1]["hours_cumulative"] > max_hours: w.append(f"total {rows[-1]['hours_cumulative']} h exceeds {max_hours} h")
    return w


def svg(rows, log=False, w=640, h=320):
    v = np.array([r["value"] for r in rows], float); y = np.log10(np.maximum(v, 1e-9)) if log else v; lo, hi = y.min(), y.max(); span = max(hi - lo, 1e-9)
    pts = " ".join(f"{30 + i / max(len(v) - 1, 1) * (w - 50):.1f},{h - 25 - (yy - lo) / span * (h - 50):.1f}" for i, yy in enumerate(y))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}"><rect width="100%" height="100%" fill="#fff"/><polyline points="{pts}" fill="none" stroke="#235" stroke-width="2"/><text x="30" y="16" font-size="12">value per level{" (log)" if log else ""}: {rows[0]["value"]} to {rows[-1]["value"]}, total {rows[-1]["cumulative"]}</text></svg>'


def main(argv=None):
    ap = argparse.ArgumentParser(description="Level / XP curve generator and checker.")
    ap.add_argument("--kind", required=True, choices=["linear", "poly", "exp", "custom"]); ap.add_argument("--levels", type=int, default=50)
    ap.add_argument("--base", type=float, default=100); ap.add_argument("--step", type=float, default=50); ap.add_argument("--power", type=float, default=2.0); ap.add_argument("--growth", type=float, default=1.15)
    ap.add_argument("--anchors"); ap.add_argument("--target-total", type=float); ap.add_argument("--nice", action="store_true"); ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--per-hour", type=float); ap.add_argument("--spike", type=float, default=1.5); ap.add_argument("--max-hours", type=float)
    ap.add_argument("--csv"); ap.add_argument("--json"); ap.add_argument("--svg"); ap.add_argument("--log", action="store_true"); ap.add_argument("--strict", action="store_true")
    a = ap.parse_args(argv); anchors = [tuple(float(x) for x in p.split(":")) for p in a.anchors.split(",")] if a.anchors else None
    rows = build(a.kind, a.levels, a.target_total, a.nice, a.round, a.per_hour, base=a.base, step=a.step, power=a.power, growth=a.growth, anchors=anchors); w = warnings(rows, a.spike, a.max_hours)
    print(f"{a.levels} levels: first {rows[0]['value']}, last {rows[-1]['value']}, cumulative {rows[-1]['cumulative']}" + (f", {rows[-1]['hours_cumulative']} h" if a.per_hour else ""))
    for x in w: print("WARN", x)
    if a.csv:
        with open(a.csv, "w", newline="") as f: wr = csv.DictWriter(f, fieldnames=list(rows[0])); wr.writeheader(); wr.writerows(rows)
    if a.json: json.dump({"kind": a.kind, "rows": rows, "warnings": w}, open(a.json, "w"), indent=1)
    if a.svg: open(a.svg, "w").write(svg(rows, a.log))
    return 1 if a.strict and w else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
