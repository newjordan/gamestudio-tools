import csv, gzip, json, os, sys
import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PALETTES = {  # one base colour per game so the task is learnable
    ("srcA", "g1"): (200, 30, 30), ("srcA", "g2"): (30, 200, 30), ("srcA", "g3"): (220, 220, 40),
    ("srcB", "g4"): (30, 30, 200), ("srcB", "g5"): (200, 30, 200), ("srcB", "g6"): (30, 200, 200),
}
SPLIT_OF = {"g1": "train", "g2": "train", "g4": "train", "g5": "train", "g3": "test_unseen", "g6": "test_unseen"}


SIZE = {"srcA": (64, 48), "srcB": (96, 48)}  # sources differ in frame size -> raw size shortcut exists in the toy data


def _frame(rng, base, kind):
    w_, h_ = SIZE[kind]
    a = np.zeros((h_, w_, 3), np.uint8) + np.array(base, np.uint8)
    a = np.clip(a.astype(int) + rng.integers(-20, 20, a.shape), 0, 255).astype(np.uint8)
    ents = []
    for i in range(3):
        x, y = int(rng.integers(0, 40)), int(rng.integers(0, 28))
        w, h = 16, 16
        col = (255, 255, 255) if i % 2 == 0 else (0, 0, 0)
        a[y:y + h, x:x + w] = col
        ent = {"class": "hero" if i % 2 == 0 else "rock", "box": [x, y, w, h]}
        if kind == "srcA" and i == 1:
            ent["visible_frac"] = 0.2  # mostly hidden -> removed by the occlusion filter
        elif kind == "srcA" and i == 0:
            ent["visibility"] = 1.0
        ents.append(ent)
    if kind == "srcB":  # stripes so sources differ in texture too
        a[::4] = a[::4] // 2
    return Image.fromarray(a), ents


@pytest.fixture(scope="session")
def fake(tmp_path_factory):
    root = tmp_path_factory.mktemp("data")
    clean = root / "clean"
    (clean / "splits_v1").mkdir(parents=True)
    (root / "ALL").mkdir()
    json.dump({"vocab": ["character", "prop", "unknown"],
               "map": {s: {"hero": {"sem": "character"}, "rock": {"sem": "prop"}} for s in ("srcA", "srcB")}},
              open(root / "ALL/class_map.json", "w"))
    rng = np.random.default_rng(0)
    splits = {s: [] for s in ("train", "val", "test_seen", "test_unseen", "reserve", "licence_review")}
    lic = []
    for (src, game), base in PALETTES.items():
        gdir = root / src / game
        (gdir / "frames").mkdir(parents=True)
        recs = []
        gz = src == "srcB"
        for run in range(4):
            sp = SPLIT_OF[game]
            if sp == "train":
                sp = ["train", "train", "val", "test_seen"][run]
            for t in range(4):
                img, ents = _frame(rng, base, src)
                rel = f"{src}/{game}/frames/r{run}_{t}.png"
                img.save(root / rel)
                recs.append({"image": rel, "source": src, "game": game, "sheet": {"entities": ents}})
                splits[sp].append({"path": rel, "source": src, "game": game, "run": f"r{run}", "t": t, "w": SIZE[src][0], "h": SIZE[src][1],
                                   "rec": f"{src}/{game}/records.jsonl", "md5": f"{src}{game}{run}{t}", "_i": len(recs) - 1})
        lines = [(json.dumps(r) + "\n").encode() for r in recs]
        if not gz:
            offs, o = [], 0
            for lb in lines:
                offs.append(o); o += len(lb)
            open(gdir / "records.jsonl", "wb").write(b"".join(lines))
        else:  # sealed gz: members of 5 lines, offset = member_byte_offset * 2**26 + offset in member
            offs = []
            with open(gdir / "records.jsonl.gz", "wb") as fh:
                for m in range(0, len(lines), 5):
                    m0 = fh.tell(); o = 0
                    for lb in lines[m:m + 5]:
                        offs.append(m0 * (1 << 26) + o); o += len(lb)
                    fh.write(gzip.compress(b"".join(lines[m:m + 5]), mtime=0))
        for s in splits.values():
            for r in s:
                if r["source"] == src and r["game"] == game and "_i" in r:
                    r["off"] = offs[r.pop("_i")]
        lic.append({"source": src, "game": game, "licence_text": "CC0", "basis": "test", "confidence": "x", "evidence": "", "risk_flags": "",
                    "licence_classes": "CC0", "attribution_required": "False", "frames": 16})
    for s, rows in splits.items():
        with open(clean / "splits_v1" / f"{s}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    with open(clean / "licence_manifest.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(lic[0])); w.writeheader(); w.writerows(lic)
    return {"root": str(root), "clean": str(clean), "class_map": str(root / "ALL/class_map.json"), "splits": splits}
