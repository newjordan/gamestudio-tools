#!/usr/bin/env python3
"""room-graph: extract door/portal connections from Tiled object layers into mermaid and Graphviz DOT, with a reachability check.
Rooms are taken from objects of type/class `room` (the object's name is the room id), or, if none are found, each input
map is one room (the file stem). Edges come from objects of type door, portal, exit, entrance or warp (configurable)
that have a target / to / dest / room / target_room property, or a matching `pair` / `id` property on two doors.
A --start room (default: a spawn object, else the first room) is used for BFS reachability. --fail-on-unreachable
exits 1 when any room cannot be reached. Encoded maps and group layers are handled.
"""
import argparse, os, json, sys
from collections import defaultdict, deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "map-diff"))
import map_diff  # noqa: E402

DOOR_TYPES = {"door", "portal", "exit", "entrance", "warp", "teleport"}
TARGET_KEYS = ("target", "to", "dest", "destination", "room", "target_room", "targetRoom")
PAIR_KEYS = ("pair", "link", "id")


def typ(o):
    return (o.get("type") or o.get("class") or "").lower()


def pname(o):
    return o.get("name") or ""


def objects(m):
    for path, l in map_diff.flat_layers(m.get("layers") or []):
        if l.get("type") == "objectgroup":
            for o in l.get("objects") or []:
                yield path, o


def load_maps(paths):
    out = []
    for p in paths:
        m = map_diff.decode_map(json.load(open(p)))
        out.append((os.path.splitext(os.path.basename(p))[0], p, m))
    return out


def build(maps, door_types):
    rooms = []  # list of room ids
    room_set = set()
    # room objects first
    for stem, path, m in maps:
        for _, o in objects(m):
            if typ(o) == "room" and pname(o):
                if pname(o) not in room_set:
                    rooms.append(pname(o)); room_set.add(pname(o))
    per_map_rooms = bool(room_set)
    if not per_map_rooms:
        for stem, path, m in maps:
            rooms.append(stem); room_set.add(stem)
    def room_of(stem, o, m):
        if not per_map_rooms: return stem
        props = map_diff.props(o)
        for k in ("room", "in", "from"):
            if props.get(k): return str(props[k])
        x, y = o.get("x", 0) + o.get("width", 0) / 2, o.get("y", 0) + o.get("height", 0) / 2
        for _, r in objects(m):
            if typ(r) != "room": continue
            rx, ry, rw, rh = r.get("x", 0), r.get("y", 0), r.get("width", 0), r.get("height", 0)
            if rw and rh and rx <= x <= rx + rw and ry <= y <= ry + rh: return pname(r)
        return stem

    edges = []  # (src, dst, label, kind)
    pair_index = defaultdict(list)  # pair value -> list of (src_room, name)
    for stem, path, m in maps:
        for _, o in objects(m):
            if typ(o) == "room": continue
            if typ(o) not in door_types and typ(o) not in {"spawn"}: 
                # still allow any object with a target property
                props = map_diff.props(o)
                if not any(props.get(k) for k in TARGET_KEYS): continue
            props = map_diff.props(o)
            src = room_of(stem, o, m)
            label = pname(o) or typ(o) or "door"
            dest = next((str(props[k]) for k in TARGET_KEYS if props.get(k)), None)
            if dest:
                if dest not in room_set:
                    rooms.append(dest); room_set.add(dest)
                edges.append((src, dest, label, typ(o) or "door"))
            pair = next((str(props[k]) for k in PAIR_KEYS if k != "id" and props.get(k)), None)
            # also name-based pairing: two doors with the same name in different rooms
            if pair: pair_index[("pair", pair)].append((src, label))
            elif pname(o) and typ(o) in door_types: pair_index[("name", pname(o))].append((src, label))
        # spawn is not an edge
    for key, locs in pair_index.items():
        # connect all rooms that share a pair/name, undirected
        seen = set()
        for i, (a, la) in enumerate(locs):
            for b, lb in locs[i + 1:]:
                if a != b and (a, b) not in seen and (b, a) not in seen:
                    edges.append((a, b, la or lb, "pair")); seen.add((a, b))
    return rooms, edges, per_map_rooms


def mermaid(rooms, edges):
    L = ["flowchart LR"]
    for r in rooms: L.append(f"  {ident(r)}[{r}]")
    for a, b, label, _k in edges:
        L.append(f"  {ident(a)} -->|{label}| {ident(b)}")
    return "\n".join(L) + "\n"


def ident(s):
    t = "".join(c if c.isalnum() or c in "_-" else "_" for c in s)
    return t or "room"


def dot(rooms, edges):
    L = ["digraph rooms {", "  rankdir=LR;"]
    for r in rooms: L.append(f'  "{r}";')
    for a, b, label, _k in edges:
        L.append(f'  "{a}" -> "{b}" [label="{label}"];')
    L.append("}")
    return "\n".join(L) + "\n"


def reach(rooms, edges, start):
    adj = defaultdict(list)
    for a, b, _l, _k in edges:
        adj[a].append(b)
        # pair edges are already added once; treat all as directed as written.
        # pair kind is stored as "pair" — add reverse for pairs
    for a, b, _l, k in edges:
        if k == "pair": adj[b].append(a)
    seen = set(); q = deque([start])
    if start in rooms: seen.add(start)
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen:
                seen.add(v); q.append(v)
    return [r for r in rooms if r not in seen], list(seen)


def start_room(maps, rooms, per_map, requested):
    if requested: return requested
    for stem, path, m in maps:
        for _, o in objects(m):
            if typ(o) == "spawn" or pname(o).lower() == "spawn":
                if per_map:
                    # spawn's containing room
                    props = map_diff.props(o)
                    for k in ("room", "in"):
                        if props.get(k): return str(props[k])
                    x, y = o.get("x", 0), o.get("y", 0)
                    for _, r in objects(m):
                        if typ(r) != "room": continue
                        rx, ry, rw, rh = r.get("x", 0), r.get("y", 0), r.get("width", 0), r.get("height", 0)
                        if rw and rh and rx <= x <= rx + rw and ry <= y <= ry + rh: return pname(r)
                return stem
    return rooms[0] if rooms else ""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Door/portal graph from Tiled object layers.")
    ap.add_argument("maps", nargs="+")
    ap.add_argument("--mermaid"); ap.add_argument("--dot"); ap.add_argument("--json")
    ap.add_argument("--types", default="door,portal,exit,entrance,warp,teleport")
    ap.add_argument("--start"); ap.add_argument("--fail-on-unreachable", action="store_true")
    ap.add_argument("--in-place", action="store_true", help="allow overwriting the input")
    a = ap.parse_args(argv)
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
    _src_keys = ('maps',)
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

    maps = load_maps(a.maps)
    door_types = {t.strip().lower() for t in a.types.split(",") if t.strip()}
    rooms, edges, per_map = build(maps, door_types)
    start = start_room(maps, rooms, per_map, a.start)
    if start and start not in rooms:
        rooms.append(start)
    unreachable, seen = reach(rooms, edges, start) if start else (rooms, [])
    print(f"{len(rooms)} room(s), {len(edges)} edge(s), start {start or '-'}, {len(unreachable)} unreachable")
    for e in edges: print(f"  {e[0]} -> {e[1]} ({e[2]})")
    for r in unreachable: print(f"  UNREACHABLE {r}")
    md, d = mermaid(rooms, edges), dot(rooms, edges)
    if a.mermaid: open(a.mermaid, "w").write(md)
    if a.dot: open(a.dot, "w").write(d)
    if not a.mermaid and not a.dot: print(md)
    if a.json:
        json.dump({"rooms": rooms, "edges": [{"from": a, "to": b, "label": l, "kind": k} for a, b, l, k in edges],
                   "start": start, "unreachable": unreachable}, open(a.json, "w"), indent=1)
    return 1 if a.fail_on_unreachable and unreachable else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
