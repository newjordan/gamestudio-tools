#!/usr/bin/env python3
"""input-map-lint: sanity-check a game's input map before players find the problems. Input: a JSON map ({"actions": {"jump":
["Key:Space", "Pad:A"]}}, or a plain {action: [bindings]} dict, or {"contexts": {"gameplay": {...}, "menu": {...}}}) or a Godot
project.godot ([input] section, best effort: keys, mouse buttons, joypad buttons and axes, modifiers).
Errors: an action with no bindings, the same binding on two actions in one context (unless allowed), actions whose names differ only
by case, actions used in code but missing from the map (--scan DIR).
Warnings: the same binding listed twice on one action, a plain key shadowed by the same key with a modifier (Shift+W vs W), names
that are not snake_case, actions never referenced in code (--scan), keyboard actions without a gamepad binding (--parity).
Godot's built-in ui_* actions are ignored for conflicts and unused checks unless --include-ui. Exit 1 on errors (or warnings
with --strict).
"""
import argparse, os, json, re, sys

GODOT_KEYS = {4194305: "Escape", 4194306: "Tab", 4194308: "Backspace", 4194309: "Enter", 4194310: "KpEnter", 4194311: "Insert", 4194312: "Delete", 4194317: "Home", 4194318: "End",
              4194319: "Left", 4194320: "Up", 4194321: "Right", 4194322: "Down", 4194323: "PageUp", 4194324: "PageDown", 4194325: "Shift", 4194326: "Ctrl", 4194327: "Meta", 4194328: "Alt"}
for i in range(12): GODOT_KEYS[4194332 + i] = f"F{i + 1}"
MOUSE = {1: "Left", 2: "Right", 3: "Middle", 4: "WheelUp", 5: "WheelDown"}
SNAKE = re.compile(r"^[a-z][a-z0-9_]*$")
DEV = {"key": "key", "keyboard": "key", "kb": "key", "pad": "pad", "gamepad": "pad", "joy": "pad", "joypad": "pad", "controller": "pad", "mouse": "mouse"}


def norm(b):
    """-> (device, code, mods tuple) canonical binding, from a string like 'Key:Shift+W' or an object."""
    if isinstance(b, dict):
        dev, code, mods = b.get("device", "key"), str(b.get("code", b.get("key", ""))), list(b.get("mods", []))
    else:
        s = str(b).strip()
        dev, _, rest = s.partition(":") if ":" in s else ("key", "", s)
        code, mods = rest, []
        if "+" in code and not code.endswith("+"):
            parts = [p.strip() for p in code.split("+")]; code, mods = parts[-1], parts[:-1]
    dev = DEV.get(dev.strip().lower(), dev.strip().lower())
    mods = tuple(sorted({m.strip().lower() for m in mods if m.strip()}))
    return (dev, code.strip().lower(), mods)


def show(b):
    d, c, m = b; return f"{d}:" + "+".join([x.capitalize() for x in m] + [c])


def load_json(path):
    d = json.load(open(path))
    if "contexts" in d: ctx = d["contexts"]
    else: ctx = {"all": d.get("actions", d)}
    return {c: {a: [norm(b) for b in (v if isinstance(v, list) else v.get("bindings", v.get("events", [])) if isinstance(v, dict) else [v])] for a, v in acts.items()} for c, acts in ctx.items()}


def godot_objects(val):
    """Yield (type, argument text) for every Object(Type, ...) in a value, matching parentheses and skipping quoted strings
    (events contain Vector2(0, 0) and similar)."""
    for m in re.finditer(r"Object\((InputEvent\w+),", val):
        i, depth, q = m.end(), 1, False
        while i < len(val) and depth:
            c = val[i]
            if c == '"' and val[i - 1] != "\\": q = not q
            elif not q and c == "(": depth += 1
            elif not q and c == ")": depth -= 1
            i += 1
        yield m.group(1), val[m.end(): i - 1]


def parse_godot(path):
    txt = open(path, encoding="utf-8", errors="replace").read(); m = re.search(r"^\[input\]\s*$(.*?)(?=^\[|\Z)", txt, re.S | re.M)
    if not m: raise SystemExit("no [input] section in project.godot")
    entries, cur = {}, None
    for line in m.group(1).splitlines():
        k = re.match(r"^([A-Za-z0-9_./\-]+)=(.*)$", line)
        if k: cur = k.group(1); entries[cur] = k.group(2)
        elif cur is not None: entries[cur] += "\n" + line
    acts = {}
    for name, val in entries.items():
        evs = []
        for typ, args in godot_objects(val):
            kv = {k: v for k, v in re.findall(r'"(\w+)":(-?\d+(?:\.\d+)?|true|false|"[^"]*")', args)}
            mods = [n for n, f in (("shift", "shift_pressed"), ("ctrl", "ctrl_pressed"), ("alt", "alt_pressed"), ("meta", "meta_pressed")) if kv.get(f) == "true"]
            if typ == "InputEventKey":
                code = next((int(kv[f]) for f in ("physical_keycode", "keycode", "key_label", "scancode") if int(kv.get(f, "0") or 0)), 0)
                label = GODOT_KEYS.get(code) or (chr(code) if 32 < code < 127 else "Space" if code == 32 else f"key#{code}")
                evs.append(("key", label.lower(), tuple(sorted(mods))))
            elif typ == "InputEventMouseButton": evs.append(("mouse", MOUSE.get(int(kv.get("button_index", 0)), "button" + kv.get("button_index", "0")).lower(), tuple(sorted(mods))))
            elif typ == "InputEventJoypadButton": evs.append(("pad", f"button{kv.get('button_index', '0')}", ()))
            elif typ == "InputEventJoypadMotion": evs.append(("pad", f"axis{kv.get('axis', '0')}{'-' if float(kv.get('axis_value', '1')) < 0 else '+'}", ()))
            else: evs.append((typ.replace("InputEvent", "").lower(), "?", ()))
        acts[name] = evs
    return {"all": acts}


def scan_code(root):
    call = re.compile(r"\b(is_action_pressed|is_action_just_pressed|is_action_just_released|is_action|get_action_strength|get_action_raw_strength|get_axis|get_vector|"
                      r"IsActionPressed|IsActionJustPressed|IsActionJustReleased|GetActionStrength|GetAxis|GetVector|GetButton|GetButtonDown|GetButtonUp|GetAxisRaw)\(([^)]*)\)")
    lit = re.compile(r"""[&^]?["']([^"'\\\n]+)["']"""); used, alls = {}, set()
    exts = (".gd", ".cs", ".py", ".lua", ".js", ".ts", ".tscn", ".tres", ".cpp", ".h", ".hpp", ".java", ".kt", ".txt", ".json")
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("node_modules", "__pycache__")]
        for f in fn:
            if not f.endswith(exts): continue
            try: t = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
            except OSError: continue
            for _, args in call.findall(t):
                for s in lit.findall(args): used.setdefault(s, os.path.join(dp, f))
            alls.update(lit.findall(t))
    return used, alls


def lint(ctxs, allow=(), used=None, alls=None, include_ui=False, parity=False):
    F = []
    def add(sev, code, msg): F.append({"severity": sev, "code": code, "message": msg})
    allowed = {frozenset(p) for p in allow}; seen_names = {}
    for ctx, acts in ctxs.items():
        tag = "" if ctx == "all" else f"[{ctx}] "
        for a in acts:
            low = a.lower()
            if low in seen_names.setdefault(ctx, {}) and seen_names[ctx][low] != a: add("error", "name-case", f"{tag}actions {seen_names[ctx][low]!r} and {a!r} differ only by case")
            seen_names[ctx][low] = a
        ui = lambda a: a.startswith("ui_") and not include_ui
        owners = {}
        for a, bs in acts.items():
            if not bs and not ui(a): add("error", "unbound", f"{tag}action {a!r} has no bindings")
            if not SNAKE.match(a) and not ui(a): add("warning", "name-style", f"{tag}action {a!r} is not snake_case")
            seen = set()
            for b in bs:
                if b in seen: add("warning", "duplicate-binding", f"{tag}action {a!r} lists {show(b)} twice")
                seen.add(b)
                if not ui(a): owners.setdefault(b, []).append(a)
            if parity and not ui(a) and bs:
                devs = {b[0] for b in bs}
                if "key" in devs and "pad" not in devs: add("warning", "no-gamepad", f"{tag}action {a!r} has keyboard bindings but no gamepad binding")
        for b, who in owners.items():
            who = list(dict.fromkeys(who))
            if len(who) > 1:
                bad = [(x, y) for i, x in enumerate(who) for y in who[i + 1:] if frozenset((x, y)) not in allowed]
                if bad: add("error", "conflict", f"{tag}{show(b)} is bound to {', '.join(repr(w) for w in who)}")
        for b, who in owners.items():
            if b[0] in ("key", "mouse") and not b[2]:
                for b2, who2 in owners.items():
                    if b2[0] == b[0] and b2[1] == b[1] and b2[2] and set(who) != set(who2) and not (set(who) & set(who2)):
                        add("warning", "shadowed", f"{tag}{show(b)} ({', '.join(who)}) also fires when {show(b2)} ({', '.join(who2)}) is pressed unless the code checks modifiers")
    names = {a for acts in ctxs.values() for a in acts}
    if used is not None:
        for s, f in sorted(used.items()):
            if s not in names and not s.startswith("ui_"): add("error", "undefined", f"code uses action {s!r} ({os.path.relpath(f)}) but the map does not define it")
        for a in sorted(names):
            if a not in alls and not (a.startswith("ui_") and not include_ui): add("warning", "unused", f"action {a!r} is never referenced in the scanned code")
    return F


def main(argv=None):
    ap = argparse.ArgumentParser(description="Lint an input map (JSON or Godot project.godot).")
    ap.add_argument("map"); ap.add_argument("--scan", help="folder of code to cross-check action names against"); ap.add_argument("--allow", action="append", default=[], help="actionA,actionB may share bindings (repeatable)")
    ap.add_argument("--include-ui", action="store_true"); ap.add_argument("--parity", action="store_true", help="warn about keyboard actions without a gamepad binding")
    ap.add_argument("--strict", action="store_true", help="exit 1 on warnings too"); ap.add_argument("--json")
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
    _src_keys = ('map',)
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

    ctxs = parse_godot(a.map) if a.map.endswith(".godot") else load_json(a.map)
    used = alls = None
    if a.scan: used, alls = scan_code(a.scan)
    F = lint(ctxs, [p.split(",") for p in a.allow], used, alls, a.include_ui, a.parity)
    for f in F: print(f"{f['severity'].upper():<7} {f['code']:<18} {f['message']}")
    n = sum(len(v) for v in ctxs.values()); e = sum(f["severity"] == "error" for f in F); w = len(F) - e
    print(f"{n} action(s), {len(ctxs)} context(s): {e} error(s), {w} warning(s)")
    if a.json: json.dump(F, open(a.json, "w"), indent=1)
    return 1 if e or (a.strict and w) else 0


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
    import cli_error
    sys.exit(cli_error.run(main))
