"""CPU baselines: random, majority, kNN (colour histogram / hash), numpy softmax logistic regression, k-means."""
import numpy as np
from . import metrics


def hellinger_embed(h):
    """sqrt of an L1-normalised histogram: dot product = Bhattacharyya coefficient."""
    return np.sqrt(np.clip(h, 0, None)).astype(np.float32)


def hash_u64(packed):
    return np.ascontiguousarray(packed, dtype=np.uint8).view(">u8").reshape(-1).astype(np.uint64)


def hamming(q, g):
    """q: (Q,) uint64, g: (G,) uint64 -> (Q,G) int distances"""
    return np.bitwise_count(q[:, None] ^ g[None, :]).astype(np.int16)


def knn_predict(sim_fn, train_y, n_test, k, chunk=512, n_classes=None):
    """sim_fn(i0,i1) -> (chunk, N_train) similarity (higher = closer). Majority vote over top-k, ties -> nearest."""
    preds = np.empty(n_test, dtype=np.int64)
    for i0 in range(0, n_test, chunk):
        s = sim_fn(i0, min(n_test, i0 + chunk))
        if k == 1:
            preds[i0:i0 + len(s)] = train_y[np.argmax(s, 1)]
            continue
        top = np.argpartition(-s, k - 1, axis=1)[:, :k]
        ts = np.take_along_axis(s, top, 1)
        order = np.argsort(-ts, 1, kind="stable")
        top = np.take_along_axis(top, order, 1)
        ly = train_y[top]
        for j in range(len(ly)):
            c = np.bincount(ly[j], minlength=n_classes)
            best = np.flatnonzero(c == c.max())
            # tie-break by nearest neighbour among tied classes
            preds[i0 + j] = next(y for y in ly[j] if y in best)
    return preds


def random_predict(n, n_classes, seed):
    return np.random.default_rng(seed).integers(0, n_classes, n)


def majority_predict(train_y, n):
    return np.full(n, np.bincount(train_y).argmax())


class Standardiser:
    def fit(self, x):
        self.mu = x.mean(0); self.sd = x.std(0) + 1e-6; return self

    def __call__(self, x):
        return ((x - self.mu) / self.sd).astype(np.float32)


def softmax_logreg(x, y, n_classes, l2, epochs=300, lr=0.05, seed=0, class_weight=True):
    """Full-batch Adam on multinomial logistic regression with L2. Returns (W, b).
    class_weight: inverse-frequency weights so rare classes count (macro-F1 is the headline metric)."""
    rng = np.random.default_rng(seed)
    n, d = x.shape
    W = (rng.standard_normal((d, n_classes)) * 0.01).astype(np.float32)
    b = np.zeros(n_classes, np.float32)
    Y = np.zeros((n, n_classes), np.float32); Y[np.arange(n), y] = 1
    cnt = np.bincount(y, minlength=n_classes).astype(np.float32)
    w = (n / (n_classes * np.maximum(cnt, 1)))[y] if class_weight else np.ones(n, np.float32)
    w = (w / w.sum()).astype(np.float32)[:, None]
    mW = np.zeros_like(W); vW = np.zeros_like(W); mb = np.zeros_like(b); vb = np.zeros_like(b)
    b1, b2, eps = 0.9, 0.999, 1e-8
    for t in range(1, epochs + 1):
        z = x @ W + b
        z -= z.max(1, keepdims=True)
        p = np.exp(z); p /= p.sum(1, keepdims=True)
        g = (p - Y) * w
        gW = x.T @ g + l2 * W
        gb = g.sum(0)
        mW = b1 * mW + (1 - b1) * gW; vW = b2 * vW + (1 - b2) * gW * gW
        mb = b1 * mb + (1 - b1) * gb; vb = b2 * vb + (1 - b2) * gb * gb
        W -= lr * (mW / (1 - b1 ** t)) / (np.sqrt(vW / (1 - b2 ** t)) + eps)
        b -= lr * (mb / (1 - b1 ** t)) / (np.sqrt(vb / (1 - b2 ** t)) + eps)
    return W, b


def logreg_predict(model, x):
    W, b = model
    return np.argmax(x @ W + b, 1)


def kmeans(x, k, seed, iters=50, n_init=3):
    """k-means++ init, Lloyd iterations; best of n_init by inertia."""
    rng = np.random.default_rng(seed)
    x = x.astype(np.float32)
    xx = (x * x).sum(1)
    best = None
    for _ in range(n_init):
        c = [x[rng.integers(len(x))]]
        d2 = xx - 2 * x @ c[0] + c[0] @ c[0]
        for _ in range(1, k):
            pr = np.clip(d2, 0, None); pr = pr / pr.sum() if pr.sum() > 0 else np.full(len(x), 1 / len(x))
            c.append(x[rng.choice(len(x), p=pr)])
            d2 = np.minimum(d2, xx - 2 * x @ c[-1] + c[-1] @ c[-1])
        C = np.stack(c)
        for _ in range(iters):
            dist = xx[:, None] - 2 * x @ C.T + (C * C).sum(1)[None, :]
            a = dist.argmin(1)
            newC = C.copy()
            for j in range(k):
                m = a == j
                if m.any():
                    newC[j] = x[m].mean(0)
            if np.allclose(newC, C):
                break
            C = newC
        dist = xx[:, None] - 2 * x @ C.T + (C * C).sum(1)[None, :]
        a = dist.argmin(1)
        inertia = float(dist[np.arange(len(x)), a].sum())
        if best is None or inertia < best[0]:
            best = (inertia, a)
    return best[1]


def rank_eval(score_fn, n_q, rel_fn, valid_fn=None, ks=(1, 5, 10), chunk=256, higher_better=True):
    """Generic ranked retrieval. score_fn(i0,i1)->(c,G); rel_fn(i0,i1)->(c,G) bool; valid_fn(i0,i1)->(c,G) bool
    (False = excluded from the gallery for that query, e.g. the query itself or its own run)."""
    hits = {k: [] for k in ks}; aps = []
    for i0 in range(0, n_q, chunk):
        i1 = min(n_q, i0 + chunk)
        s = score_fn(i0, i1).astype(np.float64)
        if not higher_better:
            s = -s
        rel = rel_fn(i0, i1)
        if valid_fn is not None:
            v = valid_fn(i0, i1)
            s = np.where(v, s, -np.inf); rel = rel & v
        # stable tie handling: ties broken by gallery index (deterministic)
        order = np.argsort(-s, axis=1, kind="stable")
        r = np.take_along_axis(rel, order, 1)
        npos = r.sum(1)
        keep = npos > 0
        r = r[keep]; npos = npos[keep]
        for k in ks:
            hits[k].append(r[:, :k].any(1))
        cs = np.cumsum(r, 1, dtype=np.float32)
        prec = cs / np.arange(1, r.shape[1] + 1, dtype=np.float32)[None, :]
        aps.append((prec * r).sum(1) / npos)
    out = {f"R@{k}": float(np.concatenate(hits[k]).mean()) for k in ks}
    ap = np.concatenate(aps)
    out["mAP"] = float(ap.mean()); out["n_queries"] = int(len(ap))
    return out
