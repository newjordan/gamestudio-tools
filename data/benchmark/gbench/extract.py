"""Parallel feature extraction for frames and entity crops, cached to .npz (rebuildable)."""
import hashlib, json, os, random, zlib
from multiprocessing import Pool
import numpy as np
from . import data, features, occlusion

_cmap = None
_reader = None


def _init(class_map_path, root):
    global _cmap, _reader
    _, _cmap = data.load_class_map(class_map_path)
    _reader = data.RecordReader(root)


def _frame_job(args):
    path, root, norm = args
    try:
        img = features.open_image(os.path.join(root, path))
        if norm:
            img = features.apply_norm(img, norm)
        h, p, d, s = features.all_feats(img)
        return path, h, p, d, s, None
    except Exception as e:  # report, never silently drop
        return path, None, None, None, None, f"{type(e).__name__}: {e}"


def _crop_job(args):
    row, root, per_frame, min_side, seed, occ = args
    out, errs = [], []
    stats = {}
    try:
        rec = _reader.read(row["rec"], row["off"])
        ents = (rec.get("sheet") or {}).get("entities") or []
        img = None
        cand = []
        W, H = row["w"], row["h"]
        for i, e in enumerate(ents):
            b = e.get("box")
            if not b or len(b) != 4:
                continue
            sem_bare = data.entity_sem(e, row["source"], _cmap)
            sem = data.entity_sem(e, row["source"], _cmap, game=row.get("game"))
            if sem_bare != sem:
                st = stats.setdefault(row["source"], {})
                st["lookup_differed"] = st.get("lookup_differed", 0) + 1
                if sem_bare == "unknown" and sem != "unknown":
                    st["lookup_rescued"] = st.get("lookup_rescued", 0) + 1
            if sem == "unknown":
                continue
            x0, y0 = max(0, int(b[0])), max(0, int(b[1]))
            x1, y1 = min(W, int(b[0] + b[2])), min(H, int(b[1] + b[3]))
            if x1 - x0 < min_side or y1 - y0 < min_side:
                continue
            if occ is not None:
                st = stats.setdefault(row["source"], {})
                st["considered"] = st.get("considered", 0) + 1
                if occlusion.occlusion_info(e):
                    st["with_info"] = st.get("with_info", 0) + 1
                why = occlusion.occlusion_reason(e, b, W, H, occ["min_visible"], occ["min_in_frame"])
                if why:
                    st[why] = st.get(why, 0) + 1
                    continue
                st["kept"] = st.get("kept", 0) + 1
            cand.append((i, sem, (x0, y0, x1, y1)))
        rng = random.Random(f"{seed}|crop|{row['path']}")
        rng.shuffle(cand)
        cand = cand[:per_frame]
        if cand:
            img = features.to_rgb(features.open_image(os.path.join(root, row["path"]), max_side=4096))
            sx, sy = img.size[0] / W, img.size[1] / H  # jpeg draft never applied at 4096, but be safe
            for i, sem, (x0, y0, x1, y1) in cand:
                c = img.crop((int(x0 * sx), int(y0 * sy), int(x1 * sx), int(y1 * sy)))
                h, p, d, s = features.all_feats(c)
                out.append((f"{row['path']}#{i}", sem, h, p, d, s, (x1 - x0, y1 - y0)))
    except Exception as e:
        errs.append(f"{row['path']}: {type(e).__name__}: {e}")
    return row, out, errs, stats


def _key(obj):
    return hashlib.sha256(json.dumps([features.FEATURE_VERSION, obj], sort_keys=True).encode()).hexdigest()[:16]


def extract_frames(rows, cache_dir, tag, workers, log, root=None, norm=None):
    root = root or data.DATA_ROOT
    paths = [r["path"] for r in rows]
    # raw (norm=None) keeps the v1 cache key/file name so v1 caches stay valid.
    # legacy letterbox/stretch-to-256 keep the v1.1 token [paths, mode, 256].
    token = features.cache_norm_token(norm)
    f = os.path.join(cache_dir, f"frames_{tag}_{_key(paths if token is None else [paths] + (token if isinstance(token, list) else [token]))}.npz")
    if os.path.exists(f):
        log(f"cache hit {f}")
        z = np.load(f, allow_pickle=False)
        return {k: z[k] for k in z.files}
    res = {}
    errs = []
    with Pool(workers) as pool:
        for n, (p, h, ph, dh, s, err) in enumerate(pool.imap(_frame_job, [(p, root, norm) for p in paths], chunksize=16)):
            if err:
                errs.append(f"{p}: {err}")
            else:
                res[p] = (h, ph, dh, s)
            if (n + 1) % 5000 == 0:
                log(f"  {tag}: {n + 1}/{len(paths)} frames")
    keep = [i for i, p in enumerate(paths) if p in res]
    out = {
        "idx": np.array(keep, dtype=np.int64),
        "hist": np.stack([res[paths[i]][0] for i in keep]),
        "phash": np.stack([res[paths[i]][1] for i in keep]),
        "dhash": np.stack([res[paths[i]][2] for i in keep]),
        "simple": np.stack([res[paths[i]][3] for i in keep]),
    }
    for e in errs:
        log(f"  decode error: {e}")
    log(f"{tag}: {len(keep)}/{len(paths)} frames featurised, {len(errs)} errors")
    os.makedirs(cache_dir, exist_ok=True)
    np.savez(f, **out)
    return out


def extract_crops(rows, cache_dir, tag, workers, log, per_frame, min_side, seed, root=None, class_map_path=None, occ=None):
    root = root or data.DATA_ROOT
    cmp = class_map_path or data.CLASS_MAP
    f = os.path.join(cache_dir, f"crops_{tag}_{_key([[r['path'] for r in rows], per_frame, min_side, seed, data.file_sha256(class_map_path or data.CLASS_MAP)[:16]] + ([occ] if occ else []))}.npz")
    if os.path.exists(f):
        log(f"cache hit {f}")
        z = np.load(f, allow_pickle=False)
        return {k: z[k] for k in z.files}
    ids, sems, src, game, run, H, P, D, S, Z, errs = [], [], [], [], [], [], [], [], [], [], []
    jobs = [(r, root, per_frame, min_side, seed, occ) for r in rows]
    agg = {}
    with Pool(workers, initializer=_init, initargs=(cmp, root)) as pool:
        for n, (row, out, e, st) in enumerate(pool.imap(_crop_job, jobs, chunksize=8)):
            errs += e
            for src_, d_ in st.items():
                a_ = agg.setdefault(src_, {})
                for k_, v_ in d_.items():
                    a_[k_] = a_.get(k_, 0) + v_
            for cid, sem, h, p, d, s, wh in out:
                ids.append(cid); sems.append(sem); src.append(row["source"]); game.append(row["game"]); run.append(row["run"])
                H.append(h); P.append(p); D.append(d); S.append(s); Z.append(wh)
            if (n + 1) % 5000 == 0:
                log(f"  {tag}: {n + 1}/{len(rows)} frames -> {len(ids)} crops")
    for x in errs[:50]:
        log(f"  crop error: {x}")
    log(f"{tag}: {len(ids)} crops from {len(rows)} frames, {len(errs)} errors")
    out = {"id": np.array(ids), "sem": np.array(sems), "source": np.array(src), "game": np.array(game), "run": np.array(run),
           "hist": np.stack(H) if H else np.zeros((0, 512), np.float32), "phash": np.stack(P) if P else np.zeros((0, 8), np.uint8),
           "dhash": np.stack(D) if D else np.zeros((0, 8), np.uint8),
           "simple": np.stack(S) if S else np.zeros((0, features.SIMPLE_DIM), np.float32),
           "size": np.array(Z, np.float32).reshape(-1, 2),
           "occ_stats": np.array([json.dumps(agg, sort_keys=True)])}
    os.makedirs(cache_dir, exist_ok=True)
    np.savez(f, **out)
    return out


def augmented_hashes(rows, kinds, seed, workers, root=None):
    root = root or data.DATA_ROOT
    jobs = [(r["path"], k, root) for r in rows for k in kinds]
    with Pool(workers) as pool:
        res = pool.map(_aug_job, jobs, chunksize=16)
    return res


def _aug_job(args):
    path, kind, root = args
    try:
        img = features.open_image(os.path.join(root, path))
        a = features.augment(img, kind, seed=zlib.crc32(path.encode()))
        h, p, d, s = features.all_feats(a)
        return path, kind, h, p, d, s, None
    except Exception as e:
        return path, kind, None, None, None, None, f"{type(e).__name__}: {e}"
