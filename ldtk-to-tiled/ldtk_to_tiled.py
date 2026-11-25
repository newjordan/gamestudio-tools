#!/usr/bin/env python3
"""ldtk-to-tiled: convert an LDtk project (or a single level) to Tiled JSON maps. Tile and
auto-layers become tile layers (LDtk flip bits are mapped to Tiled H/V flip flags). Entity
layers become object groups. Tilesets are taken from the project's `defs.tilesets` with packed
firstgids. Writes one JSON map per level; inputs are never overwritten unless `--in-place`.
"""
import argparse, os, json, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "ldtk-to-csv"))
import safe_out  # noqa: E402
import ldtk_to_csv as ldtk  # noqa: E402

HFLIP = 0x80000000
VFLIP = 0x40000000


def tileset_table(defs):
    """-> list of {uid, name, image, tilecount, columns, w, h, firstgid}"""
    out, gid = [], 1
    for ts in (defs or {}).get("tilesets") or []:
        tw, th = ts.get("tileGridSize") or 16, ts.get("tileGridSize") or 16
        pw, ph = ts.get("pxWid") or 0, ts.get("pxHei") or 0
        cols = (pw // tw) if tw else 0
        rows = (ph // th) if th else 0
        count = int(ts.get("__cWid", cols) or cols) * int(ts.get("__cHei", rows) or rows)
        if not count and tw:
            count = cols * rows
        rec = {"uid": ts.get("uid"), "name": ts.get("identifier") or f"tileset{gid}",
               "image": ts.get("relPath") or ts.get("identifier") or "",
               "tilewidth": tw, "tileheight": th, "tilecount": count or 1,
               "columns": cols or 1, "imagewidth": pw, "imageheight": ph,
               "firstgid": gid, "margin": ts.get("padding") or 0, "spacing": ts.get("spacing") or 0}
        out.append(rec)
        gid += rec["tilecount"]
    return out


def flags_of(f):
    """LDtk tile `f`: bit 0 flipX, bit 1 flipY."""
    f = int(f or 0)
    g = 0
    if f & 1:
        g |= HFLIP
    if f & 2:
        g |= VFLIP
    return g


def layer_gids(l, firstgid):
    w, h, gs = l["__cWid"], l["__cHei"], l["__gridSize"]
    if l["__type"] == "IntGrid":
        v = l.get("intGridCsv") or []
        return [int(x) for x in v], None
    tiles = l.get("gridTiles") or l.get("autoLayerTiles") or []
    data = [0] * (w * h)
    for t in tiles:
        x, y = t["px"][0] // gs, t["px"][1] // gs
        if 0 <= x < w and 0 <= y < h:
            data[y * w + x] = (int(t["t"]) + firstgid) | flags_of(t.get("f"))
    return data, l.get("__tilesetDefUid")


def objects(layers):
    groups = []
    oid = 1
    for l in layers:
        if l.get("__type") != "Entities":
            continue
        objs = []
        for e in l.get("entityInstances") or []:
            fields = {f["__identifier"]: f.get("__value") for f in e.get("fieldInstances") or []}
            props = [{"name": k, "value": v if not isinstance(v, (dict, list)) else json.dumps(v),
                      "type": "string" if isinstance(v, (dict, list)) else ("int" if isinstance(v, int) and not isinstance(v, bool) else ("float" if isinstance(v, float) else ("bool" if isinstance(v, bool) else "string")))}
                     for k, v in fields.items()]
            objs.append({"id": oid, "name": e.get("__identifier") or "", "type": e.get("__identifier") or "",
                         "x": e["px"][0], "y": e["px"][1], "width": e.get("width", 0), "height": e.get("height", 0),
                         "properties": props})
            oid += 1
        groups.append({"type": "objectgroup", "name": l.get("__identifier") or "entities", "objects": objs})
    return groups


def convert_level(level, layers, tilesets, next_layer_id=1):
    tl = [l for l in layers if l.get("__type") != "Entities"]
    if not tl and not any(l.get("__type") == "Entities" for l in layers):
        return None
    gs = (tl[0]["__gridSize"] if tl else (layers[0].get("__gridSize") if layers else 16))
    w = tl[0]["__cWid"] if tl else layers[0].get("__cWid", 0)
    h = tl[0]["__cHei"] if tl else layers[0].get("__cHei", 0)
    uid_to_ts = {t["uid"]: t for t in tilesets if t.get("uid") is not None}
    tiled_layers = []
    for l in tl:
        uid = l.get("__tilesetDefUid")
        fg = uid_to_ts[uid]["firstgid"] if uid in uid_to_ts else 1
        data, _ = layer_gids(l, fg if l.get("__type") != "IntGrid" else 1)
        # IntGrid values are not tileset gids; leave as raw ints (0 = empty)
        if l.get("__type") == "IntGrid":
            data, _ = layer_gids(l, 1)
        tiled_layers.append({"id": next_layer_id, "name": l.get("__identifier") or "layer",
                             "type": "tilelayer", "width": w, "height": h, "x": 0, "y": 0,
                             "opacity": 1, "visible": not l.get("visible") is False, "data": data})
        next_layer_id += 1
    tiled_layers.extend(objects(layers))
    ts_out = []
    for t in tilesets:
        rec = {k: t[k] for k in ("name", "firstgid", "tilewidth", "tileheight", "tilecount",
                                 "columns", "image", "imagewidth", "imageheight", "margin", "spacing")
               if k in t and t[k] is not None}
        ts_out.append(rec)
    return {
        "type": "map", "orientation": "orthogonal", "width": w, "height": h,
        "tilewidth": gs, "tileheight": gs, "infinite": False, "renderorder": "right-down",
        "layers": tiled_layers, "tilesets": ts_out,
        "properties": [{"name": "ldtk_identifier", "type": "string",
                        "value": level.get("identifier") or ""}],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Convert an LDtk project to Tiled JSON maps.")
    ap.add_argument("ldtk")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--levels-dir", help="folder of external LDtk level files")
    ap.add_argument("--level", help="convert only this level identifier")
    ap.add_argument("--pretty", action="store_true")
    ap.add_argument("--json")
    safe_out.add_flag(ap)
    a = ap.parse_args(argv)
    safe_out.check(a.ldtk, a.outdir, a.in_place)
    if a.json:
        safe_out.check(a.ldtk, a.json, a.in_place)
    proj = json.load(open(a.ldtk, encoding="utf-8"))
    # a single .ldtkl level file may have layerInstances at the top
    if "layerInstances" in proj and "defs" not in proj:
        levels = [proj]
        tilesets = tileset_table({})
        base = os.path.dirname(os.path.abspath(a.ldtk))
    else:
        levels = proj.get("levels") or []
        tilesets = tileset_table(proj.get("defs") or {})
        base = os.path.dirname(os.path.abspath(a.ldtk))
    os.makedirs(a.outdir, exist_ok=True)
    written = []
    for level in levels:
        ident = level.get("identifier") or "level"
        if a.level and ident != a.level:
            continue
        layers = ldtk.level_layers(level, a.levels_dir, base)
        m = convert_level(level, layers, tilesets)
        if not m:
            continue
        dest = os.path.join(a.outdir, ident + ".json")
        safe_out.check(a.ldtk, dest, a.in_place)
        json.dump(m, open(dest, "w"), indent=(2 if a.pretty else None),
                  separators=(None if a.pretty else (",", ":")))
        written.append(ident)
    if a.level and not written:
        sys.exit(f"level {a.level!r} not found or had no layers")
    rec = {"levels": written, "tilesets": len(tilesets), "outdir": a.outdir}
    print(f"{len(written)} level(s) -> {a.outdir}")
    if a.json:
        json.dump(rec, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
