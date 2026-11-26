"""ICU MessageFormat helpers shared by the localisation linters."""
import re

# `{name, plural|select|selectordinal, ...}` — the argument, not the branch text.
_HEAD = re.compile(
    r"\{([A-Za-z_][A-Za-z0-9_]*)\s*,\s*(plural|select|selectordinal)\s*,"
)
_INNER = re.compile(r"\{([^{}]+)\}")
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _matching_brace(text, open_at):
    depth = 0
    for j in range(open_at, len(text)):
        ch = text[j]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return None


def placeholder_view(text):
    """Rewrite ICU messages so branch wording is not treated as a placeholder.

    `{n, plural, one {# wave} other {# waves}}` becomes `{n}`. `{# wave}` is the
    number plus translated words, which differ by language. A real `{name}` nested
    inside a branch is kept. Text with no ICU message is returned unchanged.
    """
    if not text or "{" not in text:
        return text or ""
    return _rewrite(text)


def _rewrite(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        m = _HEAD.search(text, i)
        if not m:
            out.append(text[i:])
            break
        end = _matching_brace(text, m.start())
        if end is None:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        out.append("{" + m.group(1) + "}")
        interior = _rewrite(text[m.start() + 1:end - 1])
        for im in _INNER.finditer(interior):
            body = im.group(1).strip()
            if body.startswith("#"):
                continue
            name = body.split(":", 1)[0].split(",", 1)[0].strip()
            if _NAME.match(name):
                out.append("{" + body + "}")
        i = end
    return "".join(out)
