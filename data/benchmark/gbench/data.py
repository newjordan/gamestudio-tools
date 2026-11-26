"""Read-only access to clean_v1 splits, the licence manifest and label records."""
import csv, hashlib, json, os, random, zlib
from collections import defaultdict

DATA_ROOT = os.environ.get("GBENCH_DATA_ROOT", "/workspace/gamedata")
CLEAN = os.environ.get("GBENCH_CLEAN", "/workspace/gamedata-work/clean_v1")
CLASS_MAP = os.path.join(DATA_ROOT, "ALL/class_map.json")
EVAL_SPLITS = ("train", "val", "test_seen", "test_unseen")
UNSEEN_KIND_SOURCES = ("synth", "roguelike")


def strict_unseen_mask(unseen_rows, seen_rows):
    """True for test_unseen rows whose (source, game) never appears in train/val/test_seen."""
    seen = {(r["source"], r["game"]) for r in seen_rows}
    return [(r["source"], r["game"]) not in seen for r in unseen_rows]
MUL = 1 << 26  # sealed-gz offset scheme, see gamedata/code/common/jsonlz.py


def split_path(split, clean=None):
    return os.path.join(clean or CLEAN, "splits_v1", f"{split}.jsonl")


def load_split(split, clean=None):
    with open(split_path(split, clean)) as fh:
        return [json.loads(l) for l in fh if l.strip()]


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for ch in iter(lambda: fh.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()


def load_licence_manifest(clean=None):
    p = os.path.join(clean or CLEAN, "licence_manifest.csv")
    with open(p, newline="") as fh:
        return {(r["source"], r["game"]): r for r in csv.DictReader(fh)}


def sample_per_game(rows, cap, seed, salt=""):
    """Deterministic: per game, shuffle with a seed derived from (seed, salt, game) and keep `cap` rows,
    preferring one frame per run first so runs are spread out."""
    by = defaultdict(list)
    for r in rows:
        by[(r["source"], r["game"])].append(r)
    out = []
    for key in sorted(by):
        g = sorted(by[key], key=lambda r: r["path"])
        rng = random.Random(f"{seed}|{salt}|{key[0]}|{key[1]}")
        rng.shuffle(g)
        seen, first, rest = set(), [], []
        for r in g:
            (rest if r["run"] in seen else first).append(r)
            seen.add(r["run"])
        out.extend((first + rest)[:cap])
    return out


def check_integrity(splits):
    """Leak checks the benchmark relies on. Returns dict of counts (all should be 0)."""
    games = {s: {(r["source"], r["game"]) for r in rows} for s, rows in splits.items()}
    runs = {s: {(r["source"], r["game"], r["run"]) for r in rows} for s, rows in splits.items()}
    md5 = {s: {r["md5"] for r in rows} for s, rows in splits.items()}
    out = {}
    if "train" in splits and "test_unseen" in splits:
        seen = set().union(*(games[s] for s in ("train", "val", "test_seen") if s in games))
        ov = games["test_unseen"] & seen
        # synth and roguelike hold out "unseen kinds" (genre / render / seed) rather than whole games, by design
        # (DATASET.md); every other source holds out whole games. Only the latter is a leak.
        out["unseen_games_also_seen_non_synth_roguelike"] = len({g for g in ov if g[0] not in UNSEEN_KIND_SOURCES})
    for s in ("val", "test_seen", "test_unseen"):
        if s in splits and "train" in splits:
            out[f"runs_shared_train_{s}"] = len(runs["train"] & runs[s])
            out[f"md5_shared_train_{s}"] = len(md5["train"] & md5[s])
    return out


class RecordReader:
    """Reads one label record by (rec, off). Caches the last decompressed gz member."""
    def __init__(self, root=None):
        self.root = root or DATA_ROOT
        self._key = None
        self._buf = None

    def read(self, rec, off):
        f = os.path.join(self.root, rec)
        if not os.path.exists(f) and os.path.exists(f + ".gz"):
            f = f + ".gz"
        if not f.endswith(".gz"):
            with open(f, "rb") as fh:
                fh.seek(off)
                return json.loads(fh.readline())
        m0, o = divmod(off, MUL)
        if self._key != (f, m0):
            with open(f, "rb") as fh:
                fh.seek(m0)
                d = zlib.decompressobj(31)
                buf = b""
                while not d.eof:
                    ch = fh.read(1 << 20)
                    if not ch:
                        break
                    buf += d.decompress(ch)
            self._key, self._buf = (f, m0), buf
        e = self._buf.find(b"\n", o)
        return json.loads(self._buf[o:] if e < 0 else self._buf[o:e])


def load_class_map(path=None):
    m = json.load(open(path or CLASS_MAP))
    return m["vocab"], m["map"]


def entity_sem(ent, source, cmap, game=None):
    """Resolve shared sem. Prefer a game-scoped map key `game/raw` when present
    (class_overrides.tsv / GAME_RULES are stored that way); else the bare raw class;
    else the record's own sem field; else unknown. v1.1 looked up the raw class only,
    so game-scoped entries were ignored."""
    c = ent.get("class")
    src = cmap.get(source) or {}
    if c is not None:
        if game:
            hit = src.get(f"{game}/{c}")
            if hit and hit.get("sem"):
                return hit["sem"]
        hit = src.get(c)
        if hit and hit.get("sem"):
            return hit["sem"]
    return ent.get("sem") or "unknown"
