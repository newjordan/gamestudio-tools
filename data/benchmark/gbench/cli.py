"""gbench CLI.  python3 -m gbench {tasks,check,run,report}"""
import argparse, json, os, platform, random, sys, time
import numpy as np
from . import __version__, data, extract, tasks as T

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BENCH_VERSION = "1.3"
SCALES = {
    # per-game frame caps per split, crop sampling, near-dup query count
    "smoke":   dict(train=4, val=2, test_seen=3, test_unseen=3, crop_train=2, crop_eval=2, crops_per_frame=2, nd_queries=50),
    "default": dict(train=40, val=15, test_seen=30, test_unseen=30, crop_train=15, crop_eval=10, crops_per_frame=3, nd_queries=1000),
    "large":   dict(train=120, val=30, test_seen=60, test_unseen=60, crop_train=40, crop_eval=20, crops_per_frame=3, nd_queries=3000),
}
ALL_TASKS = list(T.TASKS)


class Logger:
    def __init__(self, path=None):
        self.fh = open(path, "a") if path else None
        self.t0 = time.time()

    def __call__(self, msg):
        line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')} +{time.time() - self.t0:7.1f}s] {msg}"
        print(line, flush=True)
        if self.fh:
            self.fh.write(line + "\n"); self.fh.flush()


def _paths(a):
    return dict(clean=a.clean or data.CLEAN, root=a.data_root or data.DATA_ROOT, class_map=a.class_map or os.path.join(a.data_root or data.DATA_ROOT, "ALL/class_map.json"))


def cmd_tasks(a):
    for k, v in T.TASKS.items():
        print(f"{k}: {v}")


def load_and_check(p, log):
    splits = {s: data.load_split(s, p["clean"]) for s in data.EVAL_SPLITS}
    for s, r in splits.items():
        log(f"split {s}: {len(r)} frames, {len({(x['source'], x['game']) for x in r})} games")
    integ = data.check_integrity(splits)
    log(f"integrity: {integ}")
    lic = data.load_licence_manifest(p["clean"])
    missing = sorted({(x["source"], x["game"]) for r in splits.values() for x in r} - set(lic))
    log(f"licence manifest: {len(lic)} games; eval-split games missing from manifest: {len(missing)}")
    return splits, integ, missing


def cmd_check(a):
    p = _paths(a); log = Logger()
    _, integ, missing = load_and_check(p, log)
    bad = {k: v for k, v in integ.items() if v}
    if bad or missing:
        log(f"FAIL leaks={bad} missing_licence={missing[:10]}")
        return 1
    log("OK")
    return 0


def _strict(f, m, seen_games):
    mask = np.array([(s, g) not in seen_games for s, g in zip(m["source"], m["game"])], bool)
    return {k: v[mask] for k, v in f.items()}, {k: v[mask] for k, v in m.items()}


def _meta(rows):
    return {k: np.array([r[k] for r in rows]) for k in ("source", "game", "run")}


def cmd_run(a):
    p = _paths(a)
    cfg = dict(SCALES[a.scale]); cfg.update(scale=a.scale, seed=a.seed, workers=a.workers, tasks=a.tasks, version=__version__, bench=BENCH_VERSION,
                   occ_min_visible=a.occ_min_visible, occ_min_in_frame=a.occ_min_in_frame, norm_size=extract.features.NORM_SIZE,
                   norm_protocol=getattr(a, "norm_protocol", None) or extract.features.OFFICIAL_T1_PROTOCOL)
    cfg["norm_spec"] = extract.features.resolve_protocol(cfg["norm_protocol"])
    proto_name = getattr(a, "norm_protocol", None) or extract.features.OFFICIAL_T1_PROTOCOL
    out_dir = a.out or os.path.join(HERE, "runs", a.name or f"v13_{proto_name}_{a.scale}_seed{a.seed}")
    os.makedirs(out_dir, exist_ok=True)
    log = Logger(os.path.join(out_dir, "run.log"))
    log(f"gbench {__version__} run -> {out_dir}  cfg={json.dumps(cfg)}")
    cfg["env"] = dict(python=sys.version.split()[0], numpy=np.__version__, platform=platform.platform(), cpus=os.cpu_count())
    cfg["paths"] = p
    cfg["split_sha256"] = {s: data.file_sha256(data.split_path(s, p["clean"])) for s in data.EVAL_SPLITS}
    cfg["class_map_sha256"] = data.file_sha256(p["class_map"]) if os.path.exists(p["class_map"]) else None
    splits, integ, missing = load_and_check(p, log)
    if any(integ.values()):
        log("ABORT: split leak detected"); return 2
    cache = a.cache or os.path.join(HERE, "features")
    seed = a.seed
    samp = {s: data.sample_per_game(splits[s], cfg[s], seed, salt=s) for s in data.EVAL_SPLITS}
    for s in samp:
        log(f"sample {s}: {len(samp[s])} frames (cap {cfg[s]}/game)")
    results = {"config": cfg, "integrity": integ, "licence_missing": len(missing), "tasks": {}}
    rpath = os.path.join(out_dir, "results.json")
    if a.resume and os.path.exists(rpath):
        old = json.load(open(rpath))
        if "finished" in old:
            log("resume: run already finished, nothing to do"); return 0
        if old.get("config", {}).get("seed") == cfg["seed"] and old["config"].get("scale") == cfg["scale"]:
            results["tasks"] = old.get("tasks", {})
            log(f"resume: keeping finished tasks {list(results['tasks'])}")
    todo = [t for t in a.tasks if t not in results["tasks"]]
    seen_games = {(r["source"], r["game"]) for s in ("train", "val", "test_seen") for r in splits[s]}
    need_raw = any(t in todo for t in ("T1_source_id", "T3_game_retrieval", "T4_near_dup", "T5_style_cluster"))
    F, meta = {}, {}
    if need_raw:
        for s in data.EVAL_SPLITS:
            f = extract.extract_frames(samp[s], cache, s, a.workers, log, root=p["root"])
            rows = [samp[s][i] for i in f["idx"]]
            f = dict(f); f["size"] = np.array([[r["w"], r["h"]] for r in rows], np.float32).reshape(-1, 2)
            F[s] = f; meta[s] = _meta(rows)
            results.setdefault("decode_errors", {})[s] = int(len(samp[s]) - len(rows))
        F["test_unseen_games"], meta["test_unseen_games"] = _strict(F["test_unseen"], meta["test_unseen"], seen_games)
        log(f"test_unseen_games (whole games never seen): {len(meta['test_unseen_games']['game'])} frames, {len(set(meta['test_unseen_games']['game']))} games")
    def run_task(name, fn):
        t0 = time.time(); log(f"task {name}")
        r = fn()
        results["tasks"][name] = r; results["tasks"][name]["_seconds"] = round(time.time() - t0, 1)
        log(f"task {name} done in {time.time() - t0:.1f}s: {json.dumps(r, default=str)}")
        with open(os.path.join(out_dir, "results.json"), "w") as fh:
            json.dump(results, fh, indent=1, default=str)
    proto = extract.features.resolve_protocol(cfg["norm_protocol"])

    def _labels_from_rows(rows):
        return _meta(rows)

    def t1_variant(norm):
        def run():
            FN, labels = {}, {}
            for s in data.EVAL_SPLITS:
                f = extract.extract_frames(samp[s], cache, s, a.workers, log, root=p["root"], norm=norm) if norm else F[s]
                rows = [samp[s][i] for i in f["idx"]]
                f = dict(f)
                nat = np.array([[r["w"], r["h"]] for r in rows], np.float32).reshape(-1, 2)
                if norm:  # what the model sees: a constant size; the native size is kept only for the metadata control
                    f["native_size"] = nat
                    f["size"] = np.full_like(nat, extract.features.NORM_SIZE)
                else:
                    f["size"] = nat
                FN[s] = f
                labels[s] = _labels_from_rows(rows)
                if norm and s in F:
                    assert np.array_equal(f["idx"], F[s]["idx"]), "norm/raw frame sets differ (decode errors differ)"
                results.setdefault("decode_errors", {})[s] = int(len(samp[s]) - len(rows))
            if norm:
                FN["test_unseen_games"], labels["test_unseen_games"] = _strict(FN["test_unseen"], labels["test_unseen"], seen_games)
            else:
                FN["test_unseen_games"] = F["test_unseen_games"]
                labels["test_unseen_games"] = meta["test_unseen_games"]
            r, hp = T.classification(FN, {s: labels[s]["source"] for s in FN}, seed, log)
            hp["norm_protocol"] = cfg["norm_protocol"] if norm else None
            hp["norm_spec"] = extract.features.resolve_protocol(norm) if norm else None
            out = {"results": r, "hparams": hp}
            if norm:
                K = len(hp["classes"])
                ctl = {sp: r[sp]["size_knn_k10"]["bal_acc"] for sp in r}
                out["shortcut_check"] = {"norm_mode": norm if isinstance(norm, str) else extract.features.resolve_protocol(norm),
                                         "size_control_bal_acc": ctl, "chance_bal_acc": 1 / K,
                                         "size_control_near_chance": bool(all(v <= 2 / K for v in ctl.values()))}
                log(f"  shortcut check ({hp['norm_spec']}): {out['shortcut_check']}")
            return out
        return run
    if "T1_source_id" in todo:
        run_task("T1_source_id", t1_variant(None))
    if "T1_norm" in todo:
        run_task("T1_norm", t1_variant(extract.features.protocol_with_mode(proto, "letterbox")))
    if "T1_norm_stretch" in todo:
        run_task("T1_norm_stretch", t1_variant(extract.features.protocol_with_mode(proto, "stretch")))
    if "T6_resleak" in todo or "T6_resleak_stretch" in todo:
        def t6(norm):
            def run():
                FN = {}
                for s in data.EVAL_SPLITS:
                    f = extract.extract_frames(samp[s], cache, s, a.workers, log, root=p["root"], norm=norm)
                    rows = [samp[s][i] for i in f["idx"]]
                    f = dict(f)
                    f["native_size"] = np.array([[r["w"], r["h"]] for r in rows], np.float32).reshape(-1, 2)
                    f["size"] = np.full_like(f["native_size"], extract.features.NORM_SIZE)
                    FN[s] = f
                    results.setdefault("decode_errors", {})[s] = int(len(samp[s]) - len(rows))
                meta_u = _meta([samp["test_unseen"][i] for i in FN["test_unseen"]["idx"]])
                FN["test_unseen_games"], _ = _strict(FN["test_unseen"], meta_u, seen_games)
                r, hp = T.resolution_leak(FN, {s: FN[s]["native_size"] for s in FN}, seed, log)
                hp["norm_mode"] = extract.features.resolve_protocol(norm)
                hp["norm_protocol"] = cfg["norm_protocol"]
                hp["norm_spec"] = extract.features.resolve_protocol(norm)
                # size-only control must be near chance (constant 256)
                K = len(hp.get("buckets") or [])
                if r:
                    ctl = {sp: r[sp]["size_knn_k10"]["bal_acc"] for sp in r}
                    hp["size_control_near_chance"] = bool(all(v <= 2 / max(K, 1) for v in ctl.values()))
                    hp["size_control_bal_acc"] = ctl
                    hp["chance_bal_acc"] = 1 / K if K else None
                    log(f"  resleak shortcut check ({hp['norm_spec']}): size_control_near_chance={hp['size_control_near_chance']} {ctl}")
                return {"results": r, "hparams": hp}
            return run
        if "T6_resleak" in todo:
            run_task("T6_resleak", t6(extract.features.protocol_with_mode(proto, "letterbox")))
        if "T6_resleak_stretch" in todo:
            run_task("T6_resleak_stretch", t6(extract.features.protocol_with_mode(proto, "stretch")))

    def t2_variant(occ):
        def run():
            C = {}
            for s in data.EVAL_SPLITS:
                cap = cfg["crop_train"] if s == "train" else cfg["crop_eval"]
                rows = data.sample_per_game(splits[s], cap, seed, salt="crop_" + s)
                C[s] = extract.extract_crops(rows, cache, s, a.workers, log, cfg["crops_per_frame"], 8, seed, root=p["root"], class_map_path=p["class_map"], occ=occ)
            m = np.array([(a_, b_) not in seen_games for a_, b_ in zip(C["test_unseen"]["source"], C["test_unseen"]["game"])], bool)
            C["test_unseen_games"] = {k: v[m] for k, v in C["test_unseen"].items() if k != "occ_stats"}
            r, hp = T.classification({s: dict(C[s]) for s in C}, {s: C[s]["sem"] for s in C}, seed, log)
            hp["n_crops"] = {s: int(len(C[s]["sem"])) for s in C}
            hp["sem_counts_test_unseen"] = {k: int(v) for k, v in zip(*np.unique(C["test_unseen"]["sem"], return_counts=True))}
            hp["sem_counts_train"] = {k: int(v) for k, v in zip(*np.unique(C["train"]["sem"], return_counts=True))}
            hp["extract_stats"] = {s: json.loads(str(C[s]["occ_stats"][0])) for s in data.EVAL_SPLITS if "occ_stats" in C[s]}
            if occ:
                hp["occ_filter"] = dict(occ)
                hp["occ_stats"] = hp["extract_stats"]
            return {"results": r, "hparams": hp}
        return run
    if "T2_sprite_sem" in todo:
        run_task("T2_sprite_sem", t2_variant(None))
    if "T2_sprite_sem_occ" in todo:
        run_task("T2_sprite_sem_occ", t2_variant({"min_visible": a.occ_min_visible, "min_in_frame": a.occ_min_in_frame}))
    if "T3_game_retrieval" in todo:
        run_task("T3_game_retrieval", lambda: {"results": T.game_retrieval(F, meta, seed, log)})
    if "T4_near_dup" in todo:
        def t4():
            g_rows = [samp["test_unseen"][i] for i in F["test_unseen"]["idx"]]
            rng = random.Random(f"{seed}|neardup")
            qi = sorted(rng.sample(range(len(g_rows)), min(cfg["nd_queries"], len(g_rows))))
            res = extract.augmented_hashes([g_rows[i] for i in qi], extract.features.AUG_KINDS + extract.features.HARD_KINDS, seed, a.workers, root=p["root"])
            pos = {r["path"]: i for i, r in enumerate(g_rows)}
            ok = [x for x in res if x[-1] is None]
            log(f"near-dup queries: {len(ok)} ok, {len(res) - len(ok)} errors")
            Q = {"hist": np.stack([x[2] for x in ok]), "phash": np.stack([x[3] for x in ok]), "dhash": np.stack([x[4] for x in ok]), "simple": np.stack([x[5] for x in ok])}
            r = T.near_dup(F["test_unseen"], Q, np.array([pos[x[0]] for x in ok]), np.array([x[1] for x in ok]), seed)
            return {"results": r, "gallery": len(g_rows), "queries_per_kind": len(qi)}
        run_task("T4_near_dup", t4)
    if "T5_style_cluster" in todo:
        run_task("T5_style_cluster", lambda: {"results": {s: T.style_cluster(F[s], meta[s]["game"], meta[s]["source"], seed) for s in ("test_unseen_games", "test_unseen")}})
    results["finished"] = time.strftime("%Y-%m-%d %H:%M:%S %Z")
    with open(os.path.join(out_dir, "results.json"), "w") as fh:
        json.dump(results, fh, indent=1, default=str)
    log(f"done; results at {os.path.join(out_dir, 'results.json')}")
    return 0


def fmt(v):
    return "–" if v is None else f"{v:.3f}" if isinstance(v, float) else str(v)


SPL = (("test_seen", "seen"), ("test_unseen", "unseen"), ("test_unseen_games", "unseen-games"))
CLF_TASKS = ("T1_source_id", "T1_norm", "T1_norm_stretch", "T2_sprite_sem", "T2_sprite_sem_occ", "T6_resleak", "T6_resleak_stretch")
T4_MILD, T4_HARD = ("rescale", "jpeg", "bright", "crop"), ("h_rescale", "h_jpeg", "h_colour", "h_crop", "h_noise", "h_combo")


def _get(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def _table(R):
    """Flatten one results.json into {(task, split, method, metric): value}. v1 (gbench 0.1.0) T4 pooled key `all` is mapped to `mild_all`."""
    out = {}
    tk = R["tasks"]
    for t in CLF_TASKS:
        if t in tk:
            for sp, d in tk[t]["results"].items():
                for m, v in d.items():
                    for met in ("acc", "macro_f1", "bal_acc"):
                        out[(t, sp, m, met)] = v[met]
    if "T3_game_retrieval" in tk:
        for sp, d in tk["T3_game_retrieval"]["results"].items():
            for m, v in d.items():
                for met in ("R@1", "R@10", "mAP"):
                    out[("T3_game_retrieval", sp, m, met)] = v[met]
    if "T4_near_dup" in tk:
        for sp, d in tk["T4_near_dup"]["results"].items():
            for m, v in d.items():
                for met in ("R@1", "mAP"):
                    out[("T4_near_dup", "mild_all" if sp == "all" else sp, m, met)] = v[met]
    if "T5_style_cluster" in tk:
        for sp, d in tk["T5_style_cluster"]["results"].items():
            for m, v in d.items():
                for met in ("NMI_game", "ARI_game", "purity_game", "NMI_source"):
                    out[("T5_style_cluster", sp, m, met)] = v[met]
    return out


def _cell(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return "–"
    if len(vals) == 1:
        return f"{vals[0]:.3f}"
    return f"{np.mean(vals):.3f} ± {np.std(vals, ddof=1):.3f}"


def render_tables(tabs, title_note, tasks=None):
    """tabs: list of flattened tables (one per seed). Cells are mean ± sample sd when >1 seed."""
    L = []
    keys = set().union(*tabs)
    def methods(t):
        seen = []
        for tab in tabs:
            for (tt, sp, m, met) in tab:
                if tt == t and m not in seen:
                    seen.append(m)
        return seen
    def cell(t, sp, m, met):
        return _cell([tab.get((t, sp, m, met)) for tab in tabs])
    want = lambda t: any(k[0] == t for k in keys) and (tasks is None or t in tasks)
    for t in CLF_TASKS:
        if not want(t):
            continue
        mets = ("acc", "macro_f1", "bal_acc") if t.startswith("T1") or t.startswith("T6") else ("acc", "macro_f1")
        L += [f"#### {t} {title_note}", "", "| method | " + " | ".join(f"{lab} {m}" for _, lab in SPL for m in mets) + " |", "|---" * (1 + len(SPL) * len(mets)) + "|"]
        for m in methods(t):
            L.append(f"| {m} | " + " | ".join(cell(t, sp, m, met) for sp, _ in SPL for met in mets) + " |")
        L.append("")
    t = "T3_game_retrieval"
    if want(t):
        L += [f"#### {t} {title_note}", "", "| method | " + " | ".join(f"{lab} {m}" for _, lab in SPL for m in ("R@1", "mAP")) + " |", "|---" * 7 + "|"]
        for m in methods(t):
            L.append(f"| {m} | " + " | ".join(cell(t, sp, m, met) for sp, _ in SPL for met in ("R@1", "mAP")) + " |")
        L.append("")
    t = "T4_near_dup"
    if want(t):
        have = {k[1] for k in keys if k[0] == t}
        for tier, kinds in (("mild", T4_MILD), ("hard", T4_HARD)):
            ks = [k for k in kinds if k in have] + ([f"{tier}_all"] if f"{tier}_all" in have else [])
            if not ks:
                continue
            L += [f"#### {t}, {tier} tier {title_note} (R@1; last column pooled R@1 and mAP)", "", "| method | " + " | ".join(ks[:-1]) + f" | {ks[-1]} R@1 | {ks[-1]} mAP |", "|---" * (len(ks) + 2) + "|"]
            for m in methods(t):
                L.append(f"| {m} | " + " | ".join(cell(t, k, m, "R@1") for k in ks) + f" | {cell(t, ks[-1], m, 'mAP')} |")
            L.append("")
    t = "T5_style_cluster"
    if want(t):
        mets = ("NMI_game", "ARI_game", "purity_game", "NMI_source")
        for sp in ("test_unseen_games", "test_unseen"):
            L += [f"#### {t} on {sp} {title_note}", "", "| method | " + " | ".join(mets) + " |", "|---" * 5 + "|"]
            for m in methods(t):
                L.append(f"| {m} | " + " | ".join(cell(t, sp, m, met) for met in mets) + " |")
            L.append("")
    return L



def render_t2_compare(tabs_old, tabs_new, title_note):
    """v1.1 vs v1.2 T2 (unfiltered and occlusion-filtered)."""
    if not tabs_old or not tabs_new:
        return []
    L = []
    methods = []
    for tab in tabs_new + tabs_old:
        for t, sp, m, met in tab:
            if t.startswith("T2") and m not in methods:
                methods.append(m)
    cell = lambda tabs, t, sp, m, met: _cell([tab.get((t, sp, m, met)) for tab in tabs])
    for t, lab in (("T2_sprite_sem", "T2 unfiltered"), ("T2_sprite_sem_occ", "T2 with occlusion filter")):
        if not any(k[0]==t for tab in tabs_new+tabs_old for k in tab):
            continue
        L += [f"#### {lab} before (v1.1) / after (v1.2) {title_note}", "",
              "| method | " + " | ".join(f"{lab2} v1.1 {met} | {lab2} v1.2 {met}" for _, lab2 in SPL for met in ("macro_f1","acc")) + " |",
              "|---" * (1 + 4*len(SPL)) + "|"]
        for m in methods:
            L.append(f"| {m} | " + " | ".join(
                f"{cell(tabs_old,t,sp,m,met)} | {cell(tabs_new,t,sp,m,met)}"
                for sp,_ in SPL for met in ("macro_f1","acc")) + " |")
        L.append("")
    return L


def render_t1_compare(tabs, title_note):
    """Side-by-side T1 raw vs letterbox vs stretch (same frames, same seeds)."""
    keys = set().union(*tabs)
    if not any(k[0] == "T1_norm" for k in keys):
        return []
    variants = (("T1_source_id", "raw v1"), ("T1_norm", "norm letterbox"), ("T1_norm_stretch", "norm stretch"))
    ms = []
    for t, _ in variants:
        for k in sorted(keys):
            if k[0] == t and k[2] not in ms:
                ms.append(k[2])
    cell = lambda t, sp, m, met: _cell([tab.get((t, sp, m, met)) for tab in tabs])
    L = []
    for sp, lab in (("test_unseen_games", "unseen-games"), ("test_seen", "seen")):
        L += [f"#### T1 raw vs normalised, {lab} {title_note}", "", "| method | " + " | ".join(f"{v} {met}" for _, v in variants for met in ("macro_f1", "bal_acc")) + " |", "|---" * 7 + "|"]
        for m in ms:
            L.append(f"| {m} | " + " | ".join(cell(t, sp, m, met) for t, _ in variants for met in ("macro_f1", "bal_acc")) + " |")
        L.append("")
    return L



def render_lookup_stats(runs):
    tot = {}
    for R in runs:
        st = _get(R, "tasks", "T2_sprite_sem", "hparams", "extract_stats") or {}
        for sp, d in st.items():
            for src, c in d.items():
                t = tot.setdefault(src, {})
                for k, v in c.items():
                    if k in ("lookup_differed", "lookup_rescued", "considered", "kept"):
                        t[k] = t.get(k, 0) + v
    if not any(t.get("lookup_differed") for t in tot.values()):
        return []
    L = ["#### T2 game-scoped lookup (v1.2): entities whose label changes vs raw-class-only lookup, summed over splits and seeds of this group", "",
         "| source | considered | lookup differed | rescued from unknown |", "|---|---|---|---|"]
    for src, c in sorted(tot.items(), key=lambda kv: -kv[1].get("lookup_differed", 0)):
        if not c.get("lookup_differed"):
            continue
        L.append(f"| {src} | {c.get('considered', '–') if isinstance(c.get('considered'), int) else '–'} | {c.get('lookup_differed', 0):,} | {c.get('lookup_rescued', 0):,} |")
    L.append("")
    return L


def render_occ_stats(runs):
    """Sum occ_stats over runs and splits: per source entities considered, how many carry an occlusion field, drops by reason."""
    from .occlusion import REASONS
    tot = {}
    for R in runs:
        st = _get(R, "tasks", "T2_sprite_sem_occ", "hparams", "occ_stats")
        for sp, d in (st or {}).items():
            for src, c in d.items():
                t = tot.setdefault(src, {})
                for k, v in c.items():
                    t[k] = t.get(k, 0) + v
    if not tot:
        return []
    L = ["#### T2 occlusion filter: what it removed (entities passing the size and class filters, summed over splits and seeds)", "",
         "| source | considered | carry a visibility/occlusion field | " + " | ".join(REASONS) + " | kept |", "|---" * (4 + len(REASONS)) + "|"]
    for src, c in sorted(tot.items(), key=lambda kv: -kv[1].get("considered", 0)):
        n = c.get("considered", 0)
        L.append(f"| {src} | {n:,} | {c.get('with_info', 0) / n:.0%} | " + " | ".join(f"{c.get(r, 0):,}" for r in REASONS) + f" | {c.get('kept', 0) / n:.1%} |")
    L.append("")
    return L


def compare_versions(g_old, g_new, tasks=None, label="Protocol check"):
    """Count shared (task, split, method, metric) cells that agree per seed. `tasks` restricts the comparison."""
    L = []
    old = {R["config"]["seed"]: _table(R) for _, R in g_old}
    new = {R["config"]["seed"]: _table(R) for _, R in g_new}
    shared = sorted(set(old) & set(new))
    if not shared:
        return L
    tot = 0; bad = []
    for sd in shared:
        for k, v in old[sd].items():
            if tasks is not None and k[0] not in tasks:
                continue
            if k in new[sd]:
                tot += 1
                if abs(v - new[sd][k]) > 1e-9:
                    bad.append((sd, k, v, new[sd][k]))
    L += [f"**{label}:** {tot} (seed, task, split, method, metric) cells exist in both sides for seeds {shared}; {tot - len(bad)} are identical to 1e-9, {len(bad)} differ."]
    for sd, k, a, b in bad[:20]:
        L.append(f"- seed {sd} {k}: v1 {a:.6f} vs v1.1 {b:.6f}")
    L.append("")
    return L



def _metric(R, task, split, method, met):
    return _get(R, "tasks", task, "results", split, method, met)


def render_antileak_compare(runs_by_label, title_note):
    """One row per normalisation protocol. T6 bal_acc (lower toward chance .333 is better);
    T1 unseen-games macro-F1 / bal_acc is the cost on the real task."""
    if not runs_by_label:
        return []
    split = "test_unseen_games"
    t6_methods = ("logreg_hist+simple", "hist_knn_k1")
    t1_methods = ("logreg_hist+simple", "hist_knn_k1")
    L = [f"### T6 leak vs T1 cost, unseen-games {title_note}", "",
         "T6 balanced accuracy is chance at 1/3; lower is less leak. T1 numbers are the cost of the same protocol on source-ID. Each protocol is a mean ± sample sd over its seeds. Baseline letterbox-256 is the v1.1/v1.2 T1-norm / T6-resleak protocol.",
         "",
         "| Protocol | T6 letterbox logreg bal_acc | T6 letterbox hist_k1 bal_acc | T6 stretch logreg bal_acc | T6 stretch hist_k1 bal_acc | T1 logreg macro-F1 | T1 logreg bal_acc | T1 hist_k1 macro-F1 | T1 hist_k1 bal_acc | n seeds |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    def cells(rs, task, method, met):
        vals = []
        for _, R in rs:
            v = _metric(R, task, split, method, met)
            if v is not None:
                vals.append(v)
        return _cell(vals) if vals else "–"
    for label, rs in runs_by_label:
        n = len(rs)
        row = [label,
               cells(rs, "T6_resleak", "logreg_hist+simple", "bal_acc"),
               cells(rs, "T6_resleak", "hist_knn_k1", "bal_acc"),
               cells(rs, "T6_resleak_stretch", "logreg_hist+simple", "bal_acc"),
               cells(rs, "T6_resleak_stretch", "hist_knn_k1", "bal_acc"),
               cells(rs, "T1_norm", "logreg_hist+simple", "macro_f1"),
               cells(rs, "T1_norm", "logreg_hist+simple", "bal_acc"),
               cells(rs, "T1_norm", "hist_knn_k1", "macro_f1"),
               cells(rs, "T1_norm", "hist_knn_k1", "bal_acc"),
               str(n)]
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    return L


def _antileak_rows_from_groups(groups):
    """Collect (label, [(path,R)...]) for the comparison table, baseline first."""
    rows = []
    # v1.2 T6 + v1.1 T1 share the letterbox-256 protocol; prefer a v1.2 row if T6 exists, and
    # merge T1 from v1.1 if v1.2 runs lack T1 (v1.2 did not rerun T1).
    def runs(bench, scale="default"):
        return groups.get((str(bench), scale), [])
    base = []
    # Build synthetic baseline entries: use v1.2 for T6, v1.1 for T1 if needed
    v12 = runs("1.2")
    v11 = runs("1.1")
    if v12 or v11:
        merged = []
        # pair by seed
        by_seed = {}
        for p, R in v12:
            by_seed[R["config"]["seed"]] = json.loads(json.dumps(R))  # copy
            by_seed[R["config"]["seed"]]["_path"] = p
        if v11:
            for p, R in v11:
                seed = R["config"]["seed"]
                if seed in by_seed:
                    if "T1_norm" not in by_seed[seed].get("tasks", {}) and "T1_norm" in R.get("tasks", {}):
                        by_seed[seed]["tasks"]["T1_norm"] = R["tasks"]["T1_norm"]
                        if "T1_norm_stretch" in R["tasks"] and "T1_norm_stretch" not in by_seed[seed]["tasks"]:
                            by_seed[seed]["tasks"]["T1_norm_stretch"] = R["tasks"]["T1_norm_stretch"]
                elif "T1_norm" in R.get("tasks", {}):
                    by_seed[seed] = json.loads(json.dumps(R))
                    by_seed[seed]["_path"] = p
        merged = [(by_seed[s]["_path"], by_seed[s]) for s in sorted(by_seed)]
        if merged:
            rows.append(("letterbox-256 (v1.1 T1 / v1.2 T6)", merged))
    # v1.3 protocols
    v13 = runs("1.3")
    by_proto = {}
    for p, R in v13:
        by_proto.setdefault(R["config"].get("norm_protocol", "letterbox"), []).append((p, R))
    for proto in list(extract.features.ANTILEAK_PROTOCOLS) + [k for k in by_proto if k not in extract.features.ANTILEAK_PROTOCOLS and k != "letterbox"]:
        if proto in by_proto:
            official = " (official T1)" if proto == extract.features.OFFICIAL_T1_PROTOCOL else ""
            rows.append((f"{proto}{official}", by_proto[proto]))
    return rows


def render_report(results_paths):
    runs = [(p, json.load(open(p))) for p in results_paths]
    L = ["# gbench results", "", "Generated by `python3 -m gbench report` from the results.json files listed below. Every number is copied by code from a run's results.json, which the run also wrote to its run.log; nothing is typed by hand.",
         "Splits: seen = test_seen (held-back runs of training games); unseen = released test_unseen (whole held-out games, plus unseen genre/render/seed variants of synth and roguelike games); unseen-games = the strict subset of test_unseen whose game never appears in train/val/test_seen.", ""]
    groups = {}
    for p, R in runs:
        groups.setdefault((R["config"].get("bench", "1.0"), R["config"]["scale"]), []).append((p, R))
    order = sorted(groups, key=lambda k: (tuple(int(x) for x in str(k[0]).split(".")), k[1]))
    for (bench, scale) in order:
        rs = groups[(bench, scale)]
        seeds = sorted({R["config"]["seed"] for _, R in rs})
        c = rs[0][1]["config"]
        L += [f"## Benchmark v{bench}, scale `{scale}` — seeds {seeds}", "",
              f"Per-game frame caps: train {c['train']}, val {c['val']}, test_seen {c['test_seen']}, test_unseen {c['test_unseen']}; crops: {c['crop_train']} train / {c['crop_eval']} eval frames per game, up to {c['crops_per_frame']} crops each; near-dup queries {c['nd_queries']} per perturbation. gbench {c['version']}, numpy {c['env']['numpy']}, Python {c['env']['python']}, {c['env']['cpus']} CPUs.", ""]
        for p, R in rs:
            n = {}
            t1 = _get(R, "tasks", "T1_source_id", "results")
            if t1:
                n = {sp: next(iter(t1[sp].values()))["n"] for sp in t1}
            t2 = _get(R, "tasks", "T2_sprite_sem", "hparams", "n_crops")
            t2o = _get(R, "tasks", "T2_sprite_sem_occ", "hparams", "n_crops")
            chk = {t: _get(R, "tasks", t, "shortcut_check", "size_control_near_chance") for t in ("T1_norm", "T1_norm_stretch") if t in R["tasks"]}
            L.append(f"- seed {R['config']['seed']}: `{p}` (log `{os.path.join(os.path.dirname(p), 'run.log')}`), finished {R.get('finished', 'UNFINISHED')}; protocol {R['config'].get('norm_protocol', 'letterbox')}; frames scored {n}; crops {t2}" + (f"; crops with occlusion filter {t2o}" if t2o else "") + (f"; size-control-near-chance {chk}" if chk else "") + f"; logreg L2 (val) T1 {_get(R, 'tasks', 'T1_source_id', 'hparams', 'logreg_l2')}, T2 {_get(R, 'tasks', 'T2_sprite_sem', 'hparams', 'logreg_l2')}; decode errors {R.get('decode_errors')}; leak checks {R['integrity']}; task seconds " + ", ".join(f"{k} {v.get('_seconds')}" for k, v in R['tasks'].items()))
        L.append("")
        if bench == "1.1" and ("1.0", scale) in groups:
            L += compare_versions(groups[("1.0", scale)], rs, label="Protocol check (v1 vs v1.1)")
        if bench == "1.2" and ("1.1", scale) in groups:
            L += compare_versions(groups[("1.1", scale)], rs, tasks=("T3_game_retrieval",), label="Protocol check (v1.1 vs v1.2, T3 only: T3 does not use class labels)")
            L += render_t2_compare([_table(R) for _, R in groups[("1.1", scale)]], [_table(R) for _, R in rs], f"({scale}, mean ± sd over seeds)" if len(rs)>1 else f"({scale})")
        elif bench == "1.2" and ("1.0", scale) in groups:
            L += compare_versions(groups[("1.0", scale)], rs, tasks=("T3_game_retrieval",), label="Protocol check (v1 vs v1.2, T3 only: T3 does not use class labels)")
        if bench == "1.3" and ("1.2", scale) in groups:
            L += compare_versions(groups[("1.2", scale)], rs, tasks=("T3_game_retrieval",), label="Protocol check (v1.2 vs v1.3, T3 only: T3 does not use T1-norm)")
        elif bench == "1.3" and ("1.0", scale) in groups:
            L += compare_versions(groups[("1.0", scale)], rs, tasks=("T3_game_retrieval",), label="Protocol check (v1 vs v1.3, T3 only: T3 does not use T1-norm)")
        if bench == "1.3":
            by_proto = {}
            for p, R in rs:
                by_proto.setdefault(R["config"].get("norm_protocol", "letterbox"), []).append((p, R))
            # comparison table once, the first time we see v1.3
            if scale == "default" or not any(x.startswith("### T6 leak vs T1 cost") for x in L):
                L += render_antileak_compare(_antileak_rows_from_groups(groups), f"({scale}, mean ± sd over seeds)")
            L += render_occ_stats([R for _, R in rs])
            L += render_lookup_stats([R for _, R in rs])
            order = []
            off = extract.features.OFFICIAL_T1_PROTOCOL
            if off in by_proto:
                order.append(off)
            for p_ in extract.features.ANTILEAK_PROTOCOLS:
                if p_ in by_proto and p_ not in order:
                    order.append(p_)
            for p_ in by_proto:
                if p_ not in order:
                    order.append(p_)
            for proto in order:
                rs_p = by_proto[proto]
                seeds_p = [R["config"]["seed"] for _, R in rs_p]
                note_p = f"({scale}, protocol `{proto}`" + (", mean ± sd over seeds" if len(rs_p) > 1 else f", seed {seeds_p[0]}") + ")"
                tag = " — official T1" if proto == extract.features.OFFICIAL_T1_PROTOCOL else ""
                L += [f"### Protocol `{proto}`{tag}", ""]
                L += render_t1_compare([_table(R) for _, R in rs_p], note_p)
                L += render_tables([_table(R) for _, R in rs_p], note_p)
            continue
        note = f"({scale}, " + ("mean ± sd over seeds" if len(rs) > 1 else f"seed {seeds[0]}") + ")"
        L += render_t1_compare([_table(R) for _, R in rs], note)
        L += render_tables([_table(R) for _, R in rs], note)
        L += render_occ_stats([R for _, R in rs])
        L += render_lookup_stats([R for _, R in rs])
    return "\n".join(L)


CARD_BEGIN, CARD_END = "<!-- gbench:results:begin -->", "<!-- gbench:results:end -->"


def update_card(card, paths):
    """Replace the block between the markers in BENCHMARK.md with the default-scale tables (generated, not typed)."""
    runs = [json.load(open(p)) for p in paths]
    default_runs = [(p, json.load(open(p))) for p in paths if json.load(open(p))["config"]["scale"] == "default"]
    # rebuild groups for the antileak table
    groups = {}
    for pth in paths:
        R = json.load(open(pth))
        groups.setdefault((R["config"].get("bench", "1.0"), R["config"]["scale"]), []).append((pth, R))
    rs = [R for _, R in groups.get((BENCH_VERSION, "default"), [])]
    if not rs and not any(k[0] == "1.3" for k in groups):
        return
    body = [CARD_BEGIN, "_Generated by `python3 -m gbench report` from finished runs/*/results.json; mean ± sample sd over seeds. Full per-run detail is in RESULTS.md._", ""]
    body += render_antileak_compare(_antileak_rows_from_groups(groups), "(default scale, mean ± sd over seeds)")
    official = extract.features.OFFICIAL_T1_PROTOCOL
    off = [(p, R) for p, R in groups.get((BENCH_VERSION, "default"), []) if R["config"].get("norm_protocol") == official]
    if off:
        body += [f"### Official T1 protocol `{official}` (default scale)", ""]
        body += render_t1_compare([_table(R) for _, R in off], f"(default, `{official}`)") + render_tables([_table(R) for _, R in off], f"(default, `{official}`)")
    body.append(CARD_END)
    txt = open(card).read()
    i, j = txt.find(CARD_BEGIN), txt.find(CARD_END)
    if i < 0 or j < 0:
        return
    open(card, "w").write(txt[:i] + "\n".join(body) + txt[j + len(CARD_END):])
    print(f"updated {card}")


def cmd_classmap(a):
    from . import classmap
    p = _paths(a)
    doc = json.load(open(p["class_map"]))
    cmap = doc["map"] if isinstance(doc, dict) and "map" in doc else doc
    txt = classmap.render(classmap.audit(cmap)) + classmap.render_changes(doc if isinstance(doc, dict) else {})
    out = a.out or os.path.join(HERE, "CLASSMAP_AUDIT.md")
    open(out, "w").write(txt)
    print(f"wrote {out}")
    return 0


def cmd_report(a):
    rd = os.path.join(HERE, "runs")
    paths = a.results or sorted(os.path.join(rd, d, "results.json") for d in os.listdir(rd)
                                if not d.startswith(("smoke", "test", "v11_smoke")) and os.path.exists(os.path.join(rd, d, "results.json")))
    paths = [p for p in paths if a.results or "finished" in json.load(open(p))]
    txt = render_report(paths)
    out = a.out or os.path.join(HERE, "RESULTS.md")
    open(out, "w").write(txt + "\n")
    card = os.path.join(HERE, "BENCHMARK.md")
    if not a.out and not a.results and os.path.exists(card):
        update_card(card, paths)
    print(f"wrote {out} from {len(paths)} run(s)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gbench", description=__doc__)
    ap.add_argument("--clean", help="clean_v1 dir (read-only)"); ap.add_argument("--data-root", help="image root"); ap.add_argument("--class-map")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tasks")
    sub.add_parser("check")
    r = sub.add_parser("run")
    r.add_argument("--scale", choices=list(SCALES), default="default"); r.add_argument("--seed", type=int, default=0)
    r.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    r.add_argument("--tasks", nargs="+", default=ALL_TASKS, choices=ALL_TASKS)
    r.add_argument("--name"); r.add_argument("--out"); r.add_argument("--cache")
    r.add_argument("--resume", action="store_true", help="keep finished tasks of an unfinished run in --out and skip them")
    r.add_argument("--norm-protocol", default=extract.features.OFFICIAL_T1_PROTOCOL, choices=list(extract.features.PROTOCOLS),
                   help="T1/T6 normalisation protocol (default: official v1.3 protocol; letterbox/stretch = v1.2; bn* = anti-leak)")
    r.add_argument("--occ-min-visible", type=float, default=0.5, help="T2 occlusion filter: drop entities visible less than this")
    r.add_argument("--occ-min-in-frame", type=float, default=0.8, help="T2 occlusion filter: drop boxes with less than this share inside the frame")
    cm = sub.add_parser("classmap"); cm.add_argument("--out")
    rp = sub.add_parser("report"); rp.add_argument("results", nargs="*"); rp.add_argument("--out")
    a = ap.parse_args(argv)
    return {"tasks": cmd_tasks, "check": cmd_check, "run": cmd_run, "report": cmd_report, "classmap": cmd_classmap}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
