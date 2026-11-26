#!/usr/bin/env python3
"""Deterministic combat for Reed Causeway.

The same step order is implemented in project/scripts/level.gd. Both sides
step 1/60 s, spawn from the integer frame numbers written here, and place
every tower the player can afford without letting a costly one block a
cheaper one later in the queue. Exit 0 only when every creep dies, nothing
leaks, and every planned tower is built.
"""
import argparse, csv, json, os

STEP = 1.0 / 60.0


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def index(rows, key="id"):
    return {row[key]: row for row in rows}


def events_of(rules, waves):
    rows = sorted(waves, key=lambda r: (int(r["wave"]), int(r["seq"])))
    t = float(rules["lead"])
    prev = None
    events = []
    for row in rows:
        wave = int(row["wave"])
        if prev is not None and wave != prev:
            t += float(rules["gap"])
        prev = wave
        gap = float(row["gap"])
        for _ in range(int(row["count"])):
            events.append({"t": t, "kind": row["kind"], "wave": wave})
            t += gap
    sim_t = 0.0
    frame = 0
    ei = 0
    while ei < len(events):
        if events[ei]["t"] <= sim_t:
            events[ei]["step"] = frame
            ei += 1
            continue
        sim_t += STEP
        frame += 1
    for event in events:
        del event["t"]
    return events


def point_at(samples, dist):
    if dist <= samples[0]["s"]:
        p = samples[0]["p"]
        return p[0], p[1]
    for i in range(1, len(samples)):
        s1 = samples[i]["s"]
        if dist <= s1:
            s0 = samples[i - 1]["s"]
            p0 = samples[i - 1]["p"]
            p1 = samples[i]["p"]
            u = 0.0 if s1 == s0 else (dist - s0) / (s1 - s0)
            return (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u)
    p = samples[-1]["p"]
    return p[0], p[1]


def dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def fight(combat, samples):
    tile = int(combat["tile"])
    length = float(combat["length"])
    towers_def = combat["towers"]
    creeps_def = combat["creeps"]
    build = combat["build"]
    events = combat["events"]
    gold = int(combat["gold"])
    core = int(combat["core"])
    leaks = kills = spawned = 0
    frame = event_i = next_id = 0
    next_id = 1
    placed = [False] * len(build)
    towers, creeps = [], []
    while True:
        for i, row in enumerate(build):
            if placed[i]:
                continue
            spec = towers_def[row["kind"]]
            if gold < spec["cost"]:
                continue
            gold -= spec["cost"]
            placed[i] = True
            towers.append({
                "kind": row["kind"],
                "pos": ((row["x"] + 0.5) * tile, (row["y"] + 0.5) * tile),
                "range": spec["range"], "dmg": spec["dmg"], "cd": spec["cd"], "cool": 0.0,
                "slow": spec["slow"], "slow_time": spec["slow_time"], "splash": spec["splash"],
            })
        while event_i < len(events) and events[event_i]["step"] <= frame:
            event = events[event_i]
            event_i += 1
            spec = creeps_def[event["kind"]]
            creeps.append({
                "id": next_id, "kind": event["kind"], "hp": spec["hp"], "speed": spec["speed"],
                "gold": spec["gold"], "leak": spec["leak"], "dist": 0.0, "slow": 1.0,
                "slow_left": 0.0, "pos": point_at(samples, 0.0),
            })
            next_id += 1
            spawned += 1
        for tw in towers:
            tw["cool"] -= STEP
            if tw["cool"] > 0.0:
                continue
            best = None
            reach2 = tw["range"] * tw["range"]
            for creep in creeps:
                if creep["hp"] <= 0:
                    continue
                if dist2(creep["pos"], tw["pos"]) > reach2:
                    continue
                if best is None or creep["dist"] > best["dist"] or (
                        creep["dist"] == best["dist"] and creep["id"] < best["id"]):
                    best = creep
            if best is None:
                continue
            if tw["splash"] > 0.0:
                splash2 = tw["splash"] * tw["splash"]
                victims = [c for c in creeps if c["hp"] > 0 and dist2(c["pos"], best["pos"]) <= splash2]
            else:
                victims = [best]
            for victim in victims:
                victim["hp"] -= tw["dmg"]
                if tw["slow"] < 1.0:
                    victim["slow"] = tw["slow"]
                    victim["slow_left"] = tw["slow_time"]
            tw["cool"] = tw["cd"]
        alive = []
        for creep in creeps:
            if creep["hp"] <= 0:
                gold += creep["gold"]
                kills += 1
                continue
            if creep["slow_left"] > 0.0:
                creep["slow_left"] -= STEP
                if creep["slow_left"] <= 0.0:
                    creep["slow"] = 1.0
                    creep["slow_left"] = 0.0
            creep["dist"] += creep["speed"] * creep["slow"] * STEP
            if creep["dist"] >= length:
                leaks += 1
                core -= creep["leak"]
                continue
            creep["pos"] = point_at(samples, creep["dist"])
            alive.append(creep)
        creeps = alive
        frame += 1
        done = event_i >= len(events) and not creeps
        if done or core <= 0 or frame > 60 * 90:
            break
    towers_built = sum(placed)
    win = core > 0 and leaks == 0 and kills == len(events) and towers_built == len(build) and not creeps
    result = {"win": win, "core": core, "leaks": leaks, "kills": kills, "gold": gold,
              "towers": towers_built, "spawned": spawned, "frames": frame, "time": round(frame * STEP, 2)}
    print("SIM " + " ".join("%s=%s" % (k, int(v) if isinstance(v, bool) else v) for k, v in result.items()))
    return result


def as_int(text):
    return int(text)


def as_float(text):
    return float(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--route", required=True)
    ap.add_argument("--rules", required=True)
    ap.add_argument("--towers", required=True)
    ap.add_argument("--creeps", required=True)
    ap.add_argument("--waves", required=True)
    ap.add_argument("--build", required=True)
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args()
    rules = json.load(open(a.rules, encoding="utf-8"))
    route = json.load(open(a.route, encoding="utf-8"))
    towers = index(read_csv(a.towers))
    creeps = index(read_csv(a.creeps))
    waves = read_csv(a.waves)
    build = sorted(read_csv(a.build), key=lambda r: int(r["seq"]))
    tower_stats = {}
    for name, row in towers.items():
        tower_stats[name] = {
            "cost": as_int(row["cost"]), "range": as_float(row["range"]), "dmg": as_int(row["dmg"]),
            "cd": as_float(row["cd"]), "slow": as_float(row["slow"]), "slow_time": as_float(row["slow_time"]),
            "splash": as_float(row["splash"]),
        }
    creep_stats = {}
    for name, row in creeps.items():
        creep_stats[name] = {
            "hp": as_int(row["hp"]), "speed": as_float(row["speed"]),
            "gold": as_int(row["gold"]), "leak": as_int(row["leak"]),
        }
    events = events_of(rules, waves)
    combat = {
        "seed": int(rules["seed"]), "tile": int(rules["tile"]), "length": route["length"],
        "gold": int(rules["gold"]), "core": int(rules["core"]),
        "towers": tower_stats, "creeps": creep_stats,
        "build": [{"seq": int(r["seq"]), "kind": r["kind"], "x": int(r["x"]), "y": int(r["y"])} for r in build],
        "events": events,
    }
    # Reload through JSON so the numbers below are the ones Godot will parse.
    blob = json.dumps(combat, sort_keys=True)
    combat = json.loads(blob)
    result = fight(combat, route["samples"])
    os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(combat, fh, indent=1, sort_keys=True)
        fh.write("\n")
    if not result["win"]:
        raise SystemExit("autoplay loses: %s" % result)
    return 0


if __name__ == "__main__":
    main()
