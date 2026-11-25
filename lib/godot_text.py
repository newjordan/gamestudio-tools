"""Helpers for Godot 4 text resources (.tscn / .tres)."""


def escape(s) -> str:
    out = []
    for ch in str(s):
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\t":
            out.append("\\t")
        elif ch == "\r":
            out.append("\\r")
        elif o < 32:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    return "".join(out)


def string(s) -> str:
    return '"%s"' % escape(s)


def string_name(s) -> str:
    return "&%s" % string(s)


def res_path(prefix, *parts):
    """Join a res:// folder (or file) prefix with the basenames in parts."""
    base = (prefix or "res://")
    if not base.startswith("res://"):
        base = "res://" + base.lstrip("/")
    base = base[len("res://"):].rstrip("/")
    tail = "/".join(p.replace("\\", "/").split("/")[-1] for p in parts if p)
    if tail and base.split("/")[-1] == tail:      # the prefix already names the file
        return "res://" + base
    joined = "/".join(x for x in (base, tail) if x)
    return "res://" + joined


def literal(value) -> str:
    """Format a Python value as a Godot 4 text-resource literal."""
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return repr(float(value))
    if isinstance(value, dict):
        inner = ", ".join("%s: %s" % (string(k), literal(v)) for k, v in value.items())
        return "{ %s }" % inner
    if isinstance(value, (list, tuple)):
        return "[%s]" % ", ".join(literal(v) for v in value)
    return string(value)


def num(x) -> str:
    """Format a number for a Godot text resource (ints stay ints)."""
    f = float(x)
    if f.is_integer() and abs(f) < 2 ** 53:
        return str(int(f))
    return repr(f)
