#!/usr/bin/env python3
"""uv-check: UV sanity report for .glb meshes (TEXCOORD_0).

  * out-of-range: share of UVs outside 0..1 (flag unless you rely on tiling)
  * degenerate: triangles with zero UV area
  * overlap: share of covered texels hit by more than one triangle (rasterised at --res, triangles shrunk
    slightly so shared edges do not count); mirrored/instanced UVs will show up here on purpose
  * texel density: texels per world unit per triangle (needs --tex-size or an embedded image); min/median/max
    and the ratio of triangles outside +/-50% of the median, which causes visibly uneven texture resolution
Exit 1 when a threshold is exceeded (--max-overlap, --max-density-spread).
"""
import os
import argparse, io, json, struct, sys
import numpy as np

NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}
DT = {5120: "i1", 5121: "u1", 5122: "i2", 5123: "u2", 5125: "u4", 5126: "f4"}


sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
from gst_errors import GstInputError  # noqa: E402
import gst_read  # noqa: E402

def load_glb(path):
    return gst_read.load_glb(path)


def read(g, b, idx):
    a = g["accessors"][idx]; bv = g["bufferViews"][a["bufferView"]]
    dt = np.dtype("<" + DT[a["componentType"]]); n = NC[a["type"]]
    stride = bv.get("byteStride") or n * dt.itemsize; off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    raw = np.lib.stride_tricks.as_strided(np.frombuffer(b, np.uint8)[off:], shape=(a["count"], n * dt.itemsize), strides=(stride, 1))
    arr = np.ascontiguousarray(raw).view(dt).reshape(a["count"], n)
    return arr.astype(np.float64) / (np.iinfo(dt).max if a.get("normalized") else 1)


def triangles(g, b):
    P, U = [], []
    for m in g.get("meshes", []):
        for p in m["primitives"]:
            if p.get("mode", 4) != 4 or "TEXCOORD_0" not in p["attributes"]: continue
            pos, uv = read(g, b, p["attributes"]["POSITION"]), read(g, b, p["attributes"]["TEXCOORD_0"])
            idx = read(g, b, p["indices"]).reshape(-1).astype(int) if "indices" in p else np.arange(len(pos))
            P.append(pos[idx].reshape(-1, 3, 3)); U.append(uv[idx].reshape(-1, 3, 2))
    if not P: raise SystemExit("no triangles with TEXCOORD_0")
    return np.concatenate(P), np.concatenate(U)


def embedded_tex_size(g, b):
    try:
        from PIL import Image
        for im in g.get("images", []):
            if "bufferView" in im:
                bv = g["bufferViews"][im["bufferView"]]; o = bv.get("byteOffset", 0)
                return Image.open(io.BytesIO(b[o:o + bv["byteLength"]])).size
    except Exception:
        pass
    return None


def uv_area(U):
    return 0.5 * np.abs((U[:, 1, 0] - U[:, 0, 0]) * (U[:, 2, 1] - U[:, 0, 1]) - (U[:, 2, 0] - U[:, 0, 0]) * (U[:, 1, 1] - U[:, 0, 1]))


def overlap_ratio(U, res=256, shrink=0.12):
    cnt = np.zeros((res, res), np.int32)
    for t in U:
        c = t.mean(0); t = c + (t - c) * (1 - shrink)
        px = t * res
        x0, y0 = np.floor(px.min(0)).astype(int); x1, y1 = np.ceil(px.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, res - 1), min(y1, res - 1)
        if x1 < x0 or y1 < y0: continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        a, b2, c2 = px
        d = (b2[1] - c2[1]) * (a[0] - c2[0]) + (c2[0] - b2[0]) * (a[1] - c2[1])
        if abs(d) < 1e-9: continue
        l1 = ((b2[1] - c2[1]) * (xs - c2[0]) + (c2[0] - b2[0]) * (ys - c2[1])) / d
        l2 = ((c2[1] - a[1]) * (xs - c2[0]) + (a[0] - c2[0]) * (ys - c2[1])) / d
        m = (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
        cnt[y0:y1 + 1, x0:x1 + 1] += m
    covered = int((cnt > 0).sum())
    return (int((cnt > 1).sum()) / covered if covered else 0.0), covered / (res * res)


def analyse(path, tex_size=None, res=256):
    g, b = load_glb(path); P, U = triangles(g, b)
    ts = tex_size or embedded_tex_size(g, b)
    ua = uv_area(U)
    wa = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    out = {"triangles": len(U), "out_of_range": float(((U < -1e-6) | (U > 1 + 1e-6)).any(-1).any(-1).mean()),
           "degenerate": int((ua < 1e-10).sum()), "uv_used_area": float(min(ua.sum(), 1e9))}
    out["overlap"], out["coverage"] = overlap_ratio(U, res)
    ok = (ua > 1e-10) & (wa > 1e-10)
    if ts and ok.any():
        dens = np.sqrt(ua[ok] * ts[0] * ts[1] / wa[ok]); med = float(np.median(dens))
        out["texel_density"] = {"tex_size": list(ts), "min": float(dens.min()), "median": med, "max": float(dens.max()),
                                "outside_50pct": float(((dens < med * 0.5) | (dens > med * 1.5)).mean())}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="UV report for GLB files.")
    ap.add_argument("files", nargs="+"); ap.add_argument("--tex-size", help="WxH if no embedded texture")
    ap.add_argument("--res", type=int, default=256); ap.add_argument("--max-overlap", type=float); ap.add_argument("--max-density-spread", type=float)
    ap.add_argument("--json", action="store_true")
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
    _src_keys = ('files',)
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

    ts = tuple(int(v) for v in a.tex_size.lower().split("x")) if a.tex_size else None
    bad = False; allr = {}
    for f in a.files:
        r = analyse(f, ts, a.res); allr[f] = r
        if not a.json:
            print(f"== {f}: {r['triangles']} tris, UV coverage {r['coverage']:.0%}, overlap {r['overlap']:.1%}, out-of-range {r['out_of_range']:.1%}, degenerate {r['degenerate']}")
            if "texel_density" in r:
                d = r["texel_density"]; print(f"   texel density min/median/max {d['min']:.1f}/{d['median']:.1f}/{d['max']:.1f} px/unit; {d['outside_50pct']:.0%} of tris outside +/-50%")
        if a.max_overlap is not None and r["overlap"] > a.max_overlap: bad = True; print(f"   FAIL overlap {r['overlap']:.1%} > {a.max_overlap:.1%}")
        if a.max_density_spread is not None and r.get("texel_density", {}).get("outside_50pct", 0) > a.max_density_spread: bad = True; print("   FAIL texel density spread")
    if a.json: print(json.dumps(allr, indent=1))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
