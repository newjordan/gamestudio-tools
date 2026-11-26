"""Metrics in numpy (no sklearn/scipy needed)."""
import numpy as np


def accuracy(y, p):
    y, p = np.asarray(y), np.asarray(p)
    return float((y == p).mean()) if len(y) else float("nan")


def macro_f1(y, p, labels=None):
    y, p = np.asarray(y), np.asarray(p)
    labels = np.unique(y) if labels is None else np.asarray(labels)
    f = []
    for c in labels:
        tp = np.sum((p == c) & (y == c)); fp = np.sum((p == c) & (y != c)); fn = np.sum((p != c) & (y == c))
        d = 2 * tp + fp + fn
        f.append(0.0 if d == 0 else 2 * tp / d)
    return float(np.mean(f)) if f else float("nan")


def balanced_accuracy(y, p):
    y, p = np.asarray(y), np.asarray(p)
    return float(np.mean([np.mean(p[y == c] == c) for c in np.unique(y)]))


def _contingency(a, b):
    _, ai = np.unique(a, return_inverse=True)
    _, bi = np.unique(b, return_inverse=True)
    m = np.zeros((ai.max() + 1, bi.max() + 1), dtype=np.int64)
    np.add.at(m, (ai, bi), 1)
    return m


def nmi(a, b):
    m = _contingency(a, b).astype(np.float64)
    n = m.sum()
    pij = m / n
    pi = pij.sum(1); pj = pij.sum(0)
    nz = pij > 0
    mi = np.sum(pij[nz] * np.log(pij[nz] / (pi[:, None] * pj[None, :])[nz]))
    hi = -np.sum(pi[pi > 0] * np.log(pi[pi > 0])); hj = -np.sum(pj[pj > 0] * np.log(pj[pj > 0]))
    d = (hi + hj) / 2
    return float(mi / d) if d > 0 else 1.0


def ari(a, b):
    m = _contingency(a, b).astype(np.float64)
    c2 = lambda x: x * (x - 1) / 2
    s = c2(m).sum(); sa = c2(m.sum(1)).sum(); sb = c2(m.sum(0)).sum(); n = c2(m.sum())
    e = sa * sb / n
    mx = (sa + sb) / 2
    return float((s - e) / (mx - e)) if mx != e else 1.0


def purity(truth, clusters):
    m = _contingency(clusters, truth)
    return float(m.max(1).sum() / m.sum())


def retrieval_metrics(rank_rel, n_pos, ks=(1, 5, 10)):
    """rank_rel: (Q, G) bool, relevance in ranked order (full ranking); n_pos: (Q,) positives per query.
    Returns recall@k (any hit in top k), mAP over full ranking. Queries with no positives are skipped."""
    rank_rel = np.asarray(rank_rel, bool); n_pos = np.asarray(n_pos)
    keep = n_pos > 0
    r = rank_rel[keep]; npos = n_pos[keep]
    out = {f"R@{k}": float(r[:, :k].any(1).mean()) for k in ks}
    cs = np.cumsum(r, 1)
    prec = cs / np.arange(1, r.shape[1] + 1)[None, :]
    out["mAP"] = float(((prec * r).sum(1) / npos).mean())
    out["n_queries"] = int(keep.sum())
    return out
