#!/usr/bin/env python3
"""drop-sim: check loot tables against what designers intend, before players find out. Reads a JSON file:
{"tables": {"goblin": {"rolls": 2 | [1, 3],
   "entries": [{"item": "gold", "weight": 50, "min": 1, "max": 5}, {"item": "sword", "weight": 1}, {"nothing": true, "weight": 10}, {"table": "gems", "weight": 5}],
   "guaranteed": [{"item": "bone", "count": 1}], "pity": {"item": "sword", "after": 30}}}}
For each table: exact per-kill probability of getting each item at least once and the expected quantity per kill (ignoring pity,
which only the simulation models: after `after` consecutive kills without the item the next kill guarantees one), a seeded
Monte Carlo run with 95% intervals, and how many kills give a 50% / 90% chance of the item. Nested `table` entries are followed (cycles are rejected).
--expect TABLE:ITEM:MIN:MAX asserts the exact probability lies in [MIN, MAX] (exit 1 otherwise), for CI on balance files.
"""
import os
import argparse, json, math, random, sys


def rolls_of(t):
    r = t.get("rolls", 1); return [r] if isinstance(r, int) else list(range(r[0], r[1] + 1))


def validate(tables):
    def walk(name, path):
        if name in path: raise SystemExit("table cycle: " + " -> ".join(path + [name]))
        if name not in tables: raise SystemExit(f"unknown table {name!r}")
        t = tables[name]
        if not t.get("entries"): raise SystemExit(f"table {name!r} has no entries")
        if sum(float(e.get("weight", 1)) for e in t["entries"]) <= 0: raise SystemExit(f"table {name!r} has zero total weight")
        for e in t["entries"]:
            if float(e.get("weight", 1)) < 0: raise SystemExit(f"table {name!r} has a negative weight")
            if "table" in e: walk(e["table"], path + [name])
    for n in tables: walk(n, [])


def exact(tables, name, memo=None):
    """returns (p_any: item -> P(at least one per kill), qty: item -> expected quantity per kill)."""
    memo = {} if memo is None else memo
    if name in memo: return memo[name]
    t = tables[name]; tot = sum(float(e.get("weight", 1)) for e in t["entries"]); items = set()
    per_p, per_q = {}, {}
    for e in t["entries"]:
        w = float(e.get("weight", 1)) / tot
        if "table" in e:
            sp, sq = exact(tables, e["table"], memo)
            for i in sp: per_p[i] = per_p.get(i, 0) + w * sp[i]; per_q[i] = per_q.get(i, 0) + w * sq[i]
        elif e.get("item") and not e.get("nothing"):
            q = (float(e.get("min", 1)) + float(e.get("max", e.get("min", 1)))) / 2; per_p[e["item"]] = per_p.get(e["item"], 0) + w; per_q[e["item"]] = per_q.get(e["item"], 0) + w * q
    rs = rolls_of(t); p_any, qty = {}, {}
    for i in per_p:
        p_any[i] = sum(1 - (1 - per_p[i]) ** r for r in rs) / len(rs); qty[i] = per_q[i] * sum(rs) / len(rs)
    for g in t.get("guaranteed", []):
        p_any[g["item"]] = 1.0; qty[g["item"]] = qty.get(g["item"], 0) + float(g.get("count", 1))
    memo[name] = (p_any, qty); return memo[name]


def roll_table(tables, name, rng, out):
    t = tables[name]; es = t["entries"]; ws = [float(e.get("weight", 1)) for e in es]; rs = rolls_of(t); n = rs[rng.randrange(len(rs))]
    for _ in range(n):
        e = rng.choices(es, ws)[0]
        if "table" in e: roll_table(tables, e["table"], rng, out)
        elif e.get("item") and not e.get("nothing"):
            lo = int(e.get("min", 1)); hi = int(e.get("max", lo)); out[e["item"]] = out.get(e["item"], 0) + rng.randint(lo, hi)


def simulate(tables, name, trials, seed=0):
    rng = random.Random(seed); t = tables[name]; pity = t.get("pity"); dry = 0
    seen, qty = {}, {}; longest = {}; streak = {}
    for _ in range(trials):
        out = {}; roll_table(tables, name, rng, out)
        for g in t.get("guaranteed", []): out[g["item"]] = out.get(g["item"], 0) + int(g.get("count", 1))
        if pity:
            if pity["item"] not in out:
                dry += 1
                if dry >= pity["after"]: out[pity["item"]] = 1; dry = 0
            else: dry = 0
        for i in set(streak) | set(out):
            if i in out: streak[i] = 0
            else: streak[i] = streak.get(i, 0) + 1
            longest[i] = max(longest.get(i, 0), streak[i])
        for i, q in out.items(): seen[i] = seen.get(i, 0) + 1; qty[i] = qty.get(i, 0) + q
    return seen, qty, longest


def kills_for(p, q):
    return None if p <= 0 else (1 if p >= 1 else math.ceil(math.log(1 - q) / math.log(1 - p)))


def analyse(tables, name, trials=100000, seed=0):
    validate(tables); p, q = exact(tables, name); seen, qty, longest = simulate(tables, name, trials, seed); res = {}
    for i in sorted(set(p) | set(seen)):
        po = seen.get(i, 0) / trials; se = math.sqrt(max(po * (1 - po), 1e-12) / trials)
        res[i] = {"p_exact": round(p.get(i, 0), 6), "qty_exact": round(q.get(i, 0), 4), "p_sim": round(po, 6), "ci95": [round(max(0, po - 1.96 * se), 6), round(min(1, po + 1.96 * se), 6)],
                  "qty_sim": round(qty.get(i, 0) / trials, 4), "kills_for_50": kills_for(p.get(i, 0), 0.5), "kills_for_90": kills_for(p.get(i, 0), 0.9), "longest_dry_streak": longest.get(i, trials)}
    return res


def main(argv=None):
    ap = argparse.ArgumentParser(description="Loot table analysis.")
    ap.add_argument("tables"); ap.add_argument("--table", action="append"); ap.add_argument("--trials", type=int, default=100000); ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--expect", action="append", default=[], help="TABLE:ITEM:MIN:MAX"); ap.add_argument("--json"); a = ap.parse_args(argv)
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
    _src_keys = ('tables',)
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

    tables = json.load(open(a.tables))["tables"]; validate(tables); out = {}; rc = 0
    for name in (a.table or list(tables)):
        out[name] = analyse(tables, name, a.trials, a.seed); print(f"== {name} ({a.trials} kills)")
        for i, r in out[name].items(): print(f"  {i:<14} p={r['p_exact']:.4f} (sim {r['p_sim']:.4f}) qty/kill {r['qty_exact']:.3f}  50%: {r['kills_for_50']} kills  90%: {r['kills_for_90']} kills  longest dry {r['longest_dry_streak']}")
    for e in a.expect:
        t, i, lo, hi = e.split(":"); p = exact(tables, t)[0].get(i, 0.0)
        ok = float(lo) - 1e-9 <= p <= float(hi) + 1e-9; print(("ok   " if ok else "FAIL ") + f"{t}:{i} p={p:.4f} expected {lo}..{hi}"); rc = rc or (0 if ok else 1)
    if a.json: json.dump(out, open(a.json, "w"), indent=1)
    return rc


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
