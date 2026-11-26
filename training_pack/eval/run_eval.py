#!/usr/bin/env python3
"""Independent eval for gamestudio-tools: runs every case in cases.py in its own temp dir against the gst CLI
and checks observable outputs only (exit codes, files, JSON/tscn/tres text, image size/pixels, WAV params).

  python3 run_eval.py [--kit PATH] [--only ID[,ID]] [--jobs N] [--json results.json] [-v]
"""
import warnings; warnings.filterwarnings("ignore", category=DeprecationWarning)
import argparse, concurrent.futures as cf, glob, hashlib, json, math, os, re, shutil, struct, subprocess, sys, tempfile, time, wave
from PIL import Image
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fixtures
from cases import CASES


class CheckFail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise CheckFail(msg)


def _wav(path):
    with wave.open(path, "rb") as w:
        ch, sw, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        s = struct.unpack("<%dh" % (len(raw) // 2), raw); full = 32768.0
    elif sw == 3:
        s = [int.from_bytes(raw[i:i + 3], "little", signed=True) for i in range(0, len(raw), 3)]; full = 8388608.0
    elif sw == 4:
        s = struct.unpack("<%di" % (len(raw) // 4), raw); full = 2147483648.0
    else:
        s = list(raw); full = 128.0
    return {"channels": ch, "rate": rate, "frames": n, "bits": sw * 8, "samples": s, "full": full}


def _peak_db(wv):
    p = max((abs(x) for x in wv["samples"]), default=0) / wv["full"]
    return -999.0 if p == 0 else 20 * math.log10(p)


def _jget(obj, dotted):
    for part in [p for p in dotted.split(".") if p]:
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            need(isinstance(obj, dict) and part in obj, "missing key %r" % dotted)
            obj = obj[part]
    return obj


def run_check(c, d, res, hashes):
    k, a = c[0], c[1:]
    def P(p):
        """'a|b' = first alternative that exists; a '*' pattern must match exactly one file."""
        for alt in p.split("|"):
            full = os.path.join(d, alt)
            if any(ch in alt for ch in "*?["):
                hits = sorted(glob.glob(full))
                if len(hits) == 1:
                    return hits[0]
                if len(hits) > 1:
                    raise CheckFail("%s matches %d files" % (alt, len(hits)))
            elif os.path.exists(full):
                return full
        return os.path.join(d, p.split("|")[0])
    if k == "exit":
        need(res.returncode == a[0], "exit %d, expected %d" % (res.returncode, a[0]))
    elif k == "exit_nonzero":
        need(res.returncode != 0, "exit 0, expected non-zero")
    elif k == "exists":
        need(os.path.exists(P(a[0])), "missing %s" % a[0])
    elif k == "nonempty":
        need(os.path.isfile(P(a[0])) and os.path.getsize(P(a[0])) > 0, "missing or empty %s" % a[0])
    elif k == "all_png_size":
        hits = sorted(glob.glob(os.path.join(d, a[0]))); need(hits, "no files match %s" % a[0])
        bad = [os.path.basename(h) + "=%dx%d" % Image.open(h).size for h in hits if Image.open(h).size != (a[1], a[2])]
        need(not bad, "not %dx%d: %s" % (a[1], a[2], bad[:4]))
    elif k == "img_pixel":
        px = Image.open(P(a[0])).convert("RGBA").getpixel((a[1], a[2]))
        need(all(abs(px[i] - a[3][i]) <= (a[4] if len(a) > 4 else 0) for i in range(len(a[3]))), "%s pixel %d,%d = %s, expected %s" % (a[0], a[1], a[2], px, a[3]))
    elif k == "img_close":
        x, y = Image.open(P(a[0])).convert("RGB"), Image.open(P(a[1])).convert("RGB")
        need(x.size == y.size, "size differs")
        m = max(abs(p - q) for u, v in zip(x.getdata(), y.getdata()) for p, q in zip(u, v)); need(m <= a[2], "max channel diff %d > %d" % (m, a[2]))
    elif k == "img_mean_lt":
        mean = lambda p: sum(sum(px[:3]) for px in Image.open(P(p)).convert("RGB").getdata()) / (3.0 * Image.open(P(p)).size[0] * Image.open(P(p)).size[1])
        need(mean(a[0]) < mean(a[1]), "%s is not darker than %s" % (a[0], a[1]))
    elif k == "glob":
        n = len(glob.glob(os.path.join(d, a[0]))); need(n == a[1], "%s: %d files, expected %d" % (a[0], n, a[1]))
    elif k == "glob_min":
        n = len(glob.glob(os.path.join(d, a[0]))); need(n >= a[1], "%s: %d files, expected >= %d" % (a[0], n, a[1]))
    elif k == "json":
        try:
            json.load(open(P(a[0]), encoding="utf-8"))
        except Exception as e:
            raise CheckFail("%s not valid JSON: %s" % (a[0], e))
    elif k == "json_eq":
        v = _jget(json.load(open(P(a[0]), encoding="utf-8")), a[1]); need(v == a[2], "%s %s = %r, expected %r" % (a[0], a[1], v, a[2]))
    elif k == "json_len":
        v = _jget(json.load(open(P(a[0]), encoding="utf-8")), a[1]); need(len(v) == a[2], "%s %s len %d, expected %d" % (a[0], a[1], len(v), a[2]))
    elif k == "json_len_min":
        v = _jget(json.load(open(P(a[0]), encoding="utf-8")), a[1]); need(len(v) >= a[2], "%s %s len %d, expected >= %d" % (a[0], a[1], len(v), a[2]))
    elif k == "png":
        need(os.path.isfile(P(a[0])), "missing %s" % a[0])
        im = Image.open(P(a[0])); need(im.format == "PNG", "%s is %s, not PNG" % (a[0], im.format))
        if len(a) > 1:
            need(im.size == (a[1], a[2]), "%s is %dx%d, expected %dx%d" % (a[0], im.size[0], im.size[1], a[1], a[2]))
    elif k == "img_size_multiple":
        im = Image.open(P(a[0])); need(im.size[0] % a[1] == 0 and im.size[1] % a[1] == 0, "%s size %s not a multiple of %d" % (a[0], im.size, a[1]))
    elif k == "img_pot":
        w, h = Image.open(P(a[0])).size; need(w & (w - 1) == 0 and h & (h - 1) == 0, "%s %dx%d not power of two" % (a[0], w, h))
    elif k == "img_same_size":
        need(Image.open(P(a[0])).size == Image.open(P(a[1])).size, "%s and %s differ in size" % (a[0], a[1]))
    elif k == "img_equal":
        x, y = Image.open(P(a[0])).convert("RGBA"), Image.open(P(a[1])).convert("RGBA")
        need(x.size == y.size and list(x.getdata()) == list(y.getdata()), "%s != %s" % (a[0], a[1]))
    elif k == "img_differs":
        x, y = Image.open(P(a[0])).convert("RGBA"), Image.open(P(a[1])).convert("RGBA")
        need(x.size != y.size or list(x.getdata()) != list(y.getdata()), "%s == %s (expected a change)" % (a[0], a[1]))
    elif k == "img_alpha_equal":
        x, y = Image.open(P(a[0])).convert("RGBA"), Image.open(P(a[1])).convert("RGBA")
        need(list(x.getchannel("A").getdata()) == list(y.getchannel("A").getdata()), "alpha of %s != %s" % (a[0], a[1]))
    elif k == "img_opaque_more":
        cnt = lambda p: sum(1 for v in Image.open(P(p)).convert("RGBA").getchannel("A").getdata() if v > 0)
        need(cnt(a[0]) > cnt(a[1]), "%s has no more covered pixels than %s" % (a[0], a[1]))
    elif k == "img_colors_in":
        pal = {tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) for h in open(P(a[1])).read().split()}
        bad = {px[:3] for px in Image.open(P(a[0])).convert("RGBA").getdata() if px[3] > 0} - pal
        need(not bad, "%s has %d colour(s) outside the palette, e.g. %s" % (a[0], len(bad), sorted(bad)[:3]))
    elif k == "img_frames":
        im = Image.open(P(a[0])); n = getattr(im, "n_frames", 1); need(n == a[1], "%s has %d frames, expected %d" % (a[0], n, a[1]))
    elif k == "img_mode_has_alpha":
        need("A" in Image.open(P(a[0])).getbands(), "%s has no alpha" % a[0])
    elif k == "starts":
        t = open(P(a[0]), encoding="utf-8", errors="replace").read(); need(t.startswith(a[1]), "%s does not start with %r" % (a[0], a[1]))
    elif k == "contains":
        t = open(P(a[0]), encoding="utf-8", errors="replace").read(); need(a[1] in t, "%s lacks %r" % (a[0], a[1]))
    elif k == "not_contains":
        t = open(P(a[0]), encoding="utf-8", errors="replace").read(); need(a[1] not in t, "%s contains %r" % (a[0], a[1]))
    elif k == "count":
        t = open(P(a[0]), encoding="utf-8", errors="replace").read(); n = t.count(a[1]); need(n == a[2], "%s: %r x%d, expected %d" % (a[0], a[1], n, a[2]))
    elif k == "regex":
        t = open(P(a[0]), encoding="utf-8", errors="replace").read(); need(re.search(a[1], t, re.M), "%s lacks /%s/" % (a[0], a[1]))
    elif k == "stdout_contains":
        need(a[0] in res.stdout, "output lacks %r" % a[0])
    elif k == "stdout_regex":
        need(re.search(a[0], res.stdout, re.M), "output lacks /%s/" % a[0])
    elif k == "wav":
        w = _wav(P(a[0]))
        for kk, vv in a[1].items():
            if kk == "frames_range":
                need(vv[0] <= w["frames"] <= vv[1], "%s frames %d not in %s" % (a[0], w["frames"], vv))
            else:
                need(w[kk] == vv, "%s %s=%r, expected %r" % (a[0], kk, w[kk], vv))
    elif k == "wav_peak_db":
        p = _peak_db(_wav(P(a[0]))); need(abs(p - a[1]) <= a[2], "%s peak %.2f dBFS, expected %.2f +- %.2f" % (a[0], p, a[1], a[2]))
    elif k == "wav_peak_ge":
        p = _peak_db(_wav(P(a[0]))); need(p >= a[1], "%s peak %.2f dBFS < %.2f" % (a[0], p, a[1]))
    elif k == "csv_col_sorted":
        rows = [l.split(",")[0] for l in open(P(a[0]), encoding="utf-8").read().splitlines()[1:] if l.strip()]
        need(rows == sorted(rows) and len(rows) == a[1], "%s keys %s not sorted / not %d rows" % (a[0], rows, a[1]))
    elif k == "wav_peak_le":
        p = _peak_db(_wav(P(a[0]))); need(p <= a[1], "%s peak %.2f dBFS > %.2f" % (a[0], p, a[1]))
    elif k == "wav_reversed":
        x, y = _wav(P(a[0])), _wav(P(a[1])); ch = x["channels"]
        fr = lambda s: [tuple(s[i:i + ch]) for i in range(0, len(s), ch)]
        need(fr(y["samples"]) == fr(x["samples"])[::-1], "%s is not %s reversed" % (a[1], a[0]))
    elif k == "wav_first_abs_le":
        w = _wav(P(a[0])); need(abs(w["samples"][0]) / w["full"] <= a[1], "%s first sample %.4f" % (a[0], w["samples"][0] / w["full"]))
    elif k == "files_identical":
        need(open(P(a[0]), "rb").read() == open(P(a[1]), "rb").read(), "%s and %s differ" % (a[0], a[1]))
    elif k == "smaller":
        need(os.path.getsize(P(a[0])) < os.path.getsize(P(a[1])), "%s not smaller than %s" % (a[0], a[1]))
    elif k == "csv_rows":
        rows = [l for l in open(P(a[0]), encoding="utf-8").read().splitlines() if l.strip()]
        need(len(rows) - 1 == a[1], "%s has %d data rows, expected %d" % (a[0], len(rows) - 1, a[1]))
    elif k == "csv_header_has":
        hdr = open(P(a[0]), encoding="utf-8").readline().strip().split(",")
        miss = [c for c in a[1] if c not in hdr]; need(not miss, "%s header %s lacks %s" % (a[0], hdr, miss))
    elif k == "tiled_dims":
        m = json.load(open(P(a[0]))); need((m["width"], m["height"]) == (a[1], a[2]), "%s is %dx%d" % (a[0], m["width"], m["height"]))
    elif k == "tiled_layer_count":
        m = json.load(open(P(a[0]))); L = [l for l in m["layers"] if l["name"] == a[1]]; need(L, "no layer %s" % a[1])
        n = sum(1 for g in L[0]["data"] if (g & 0x1FFFFFFF) == a[2]); need(n == a[3], "%s layer %s gid %d x%d, expected %d" % (a[0], a[1], a[2], n, a[3]))
    elif k == "tiled_mirror_h":
        s, o = json.load(open(P(a[0]))), json.load(open(P(a[1])))
        w = s["width"]; sd = [l for l in s["layers"] if l["name"] == a[2]][0]["data"]; od = [l for l in o["layers"] if l["name"] == a[2]][0]["data"]
        exp = [sd[y * w + (w - 1 - x)] for y in range(s["height"]) for x in range(w)]
        need([g & 0x1FFFFFFF for g in od] == exp, "layer %s is not a horizontal mirror" % a[2])
    elif k == "ascii_grid":
        rows = open(P(a[0])).read().splitlines(); need(len(rows) == a[2] and all(len(r) == a[1] for r in rows), "%s is not %dx%d" % (a[0], a[1], a[2]))
    elif k == "glb_magic":
        need(open(P(a[0]), "rb").read(4) == b"glTF", "%s is not a GLB" % a[0])
    elif k == "obj_faces":
        f = [l.split()[1:] for l in open(P(a[0])) if l.startswith("f ")]
        need(len(f) == a[1], "%s has %d faces, expected %d" % (a[0], len(f), a[1]))
        if len(a) > 2:
            need(all(len(x) == a[2] for x in f), "%s has faces that are not %d-gons" % (a[0], a[2]))
    elif k == "font_magic":
        need(open(P(a[0]), "rb").read(4) in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"wOFF", b"wOF2"), "%s is not a font" % a[0])
    elif k == "unchanged":
        need(hashlib.sha256(open(P(a[0]), "rb").read()).hexdigest() == hashes.get(a[0]), "input %s was modified" % a[0])
    else:
        raise CheckFail("unknown check %s" % k)


def run_case(case, kit):
    d = tempfile.mkdtemp(prefix="gst-eval-")
    try:
        fixtures.build(d, kit)
        hashes = {}
        for c in case["checks"]:
            if c[0] == "unchanged":
                hashes[c[1]] = hashlib.sha256(open(os.path.join(d, c[1]), "rb").read()).hexdigest()
        env = dict(os.environ, GST_ROOT=kit)
        shell = 'gst() { python3 "$GST_ROOT/gst" "$@"; }; '
        for pre in case.get("pre", []):
            r = subprocess.run(["bash", "-c", shell + pre], cwd=d, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
            if r.returncode != 0:
                return {"id": case["id"], "tool": case["tool"], "ok": False, "why": "setup step failed: %s -> exit %d: %s" % (pre, r.returncode, r.stdout[-400:])}
        t0 = time.time()
        r = subprocess.run(["bash", "-c", shell + case["cmd"]], cwd=d, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=120)
        out = {"id": case["id"], "tool": case["tool"], "exit": r.returncode, "secs": round(time.time() - t0, 2), "ok": True}
        for c in case["checks"]:
            try:
                run_check(c, d, r, hashes)
            except CheckFail as e:
                out.update(ok=False, why=str(e), output=r.stdout[-600:]); break
            except Exception as e:
                out.update(ok=False, why="check %s raised %s: %s" % (c[0], type(e).__name__, e), output=r.stdout[-600:]); break
        return out
    except subprocess.TimeoutExpired:
        return {"id": case["id"], "tool": case["tool"], "ok": False, "why": "timeout"}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kit", default=os.path.abspath(os.path.join(HERE, "..", "..")))
    ap.add_argument("--only"); ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--json", default=os.path.join(HERE, "results.json")); ap.add_argument("-v", action="store_true")
    a = ap.parse_args()
    cases = [c for c in CASES if not a.only or c["id"] in a.only.split(",")]
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        results = list(ex.map(lambda c: run_case(c, a.kit), cases))
    for r in results:
        if not r["ok"] or a.v:
            print("%-4s %-36s %s" % ("PASS" if r["ok"] else "FAIL", r["id"], r.get("why", "")))
            if not r["ok"] and a.v and r.get("output"):
                print("     | " + r["output"].strip().replace("\n", "\n     | "))
    p = sum(r["ok"] for r in results)
    tools = {r["tool"] for r in results}
    print("eval: %d cases, %d passed, %d failed, %d tools covered" % (len(results), p, len(results) - p, len(tools)))
    json.dump({"cases": len(results), "passed": p, "failed": len(results) - p, "tools": sorted(tools), "results": results},
              open(a.json, "w"), indent=1)
    return 0 if p == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
