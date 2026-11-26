"""Build a static, dependency-free HTML docs site from the kit's READMEs.

Used by `gst docs -o DIR`. No network, no CDN, no webfonts: system fonts, a
dark theme, and a client-side search index inlined in the homepage so the
site works from file://.
"""
from __future__ import annotations

import html as htmlmod
import json
import os
import re
import shutil
from pathlib import Path

# Dark theme used by every page. Keep these tokens in sync with assets/style.css.
THEME = {
    "bg": "#0e1116",
    "text": "#e8eaed",
    "muted": "#9aa0a6",
    "accent": "#8ab4f8",
    "border": "#2a2f3a",
    "card": "#161b22",
}

SHOWCASES = [
    {
        "id": "godot",
        "title": "Top-down dungeon",
        "lede": "Procedural Godot 4.7 top-down showcase, rendered with software GL. Assets came from the kit, not from hand-authored art.",
        "src": ("examples", "showcase-godot", "preview"),
        "asset_dir": "showcase",
        "files": ("showcase.gif", "shot_08.png", "shot_16.png", "shot_24.png", "sheet.png"),
        "labels": {
            "shot_08.png": "Frame 8",
            "shot_16.png": "Frame 16",
            "shot_24.png": "Frame 24",
            "sheet.png": "Sprite sheet",
            "showcase.gif": "Preview GIF",
        },
        "gif": "showcase.gif",
    },
    {
        "id": "platformer",
        "title": "Side-view platformer",
        "lede": "Side-view Godot 4.7 platformer whose gaps were validated by jump-arc against the game's gravity and jump velocity. Coin SFX, one-way platforms, parallax layers and a generated font HUD — all from kit generators.",
        "src": ("examples", "showcase-platformer", "preview"),
        "asset_dir": "showcase-platformer",
        "files": ("showcase.gif", "shot_12.png", "shot_24.png", "shot_36.png",
                  "sheet.png", "parallax.gif", "parallax_frame.png"),
        "labels": {
            "shot_12.png": "1.2s (first gap)",
            "shot_24.png": "2.4s (second jump, coin collected)",
            "shot_36.png": "3.6s (final platform)",
            "sheet.png": "Sprite sheet",
            "showcase.gif": "Preview GIF",
            "parallax.gif": "Parallax layer preview",
            "parallax_frame.png": "Parallax first frame",
        },
        "gif": "showcase.gif",
    },
    {
        "id": "web",
        "title": "HTML5 canvas room",
        "lede": "A dependency-free vanilla JS canvas game that loads a Tiled JSON map, atlas JSON, WAV SFX and BMFont directly. Every asset came from kit generators. No CDN, no npm, no Godot.",
        "src": ("examples", "showcase-web", "preview"),
        "asset_dir": "showcase-web",
        "files": ("showcase.gif", "shot_00.png", "shot_08.png", "shot_16.png",
                  "sheet.png", "showcase.png"),
        "labels": {
            "shot_00.png": "Start",
            "shot_08.png": "0.8s (walking)",
            "shot_16.png": "1.6s (approaching the coin)",
            "sheet.png": "Sprite sheet",
            "showcase.gif": "Preview GIF",
            "showcase.png": "First frame",
        },
        "gif": "showcase.gif",
    },
    {
        "id": "sample-game",
        "title": "Gem Runner (complete sample game)",
        "lede": "A complete Godot 4.7 action-platformer. Three Tiled levels with flipped tiles, colliders and a navmesh; Aseprite characters with hitboxes; a nine-slice UI, bitmap font, en/de translations and a data-table enemy Resource. Every asset came from a gst command, and an autoplay run reaches the win screen.",
        "src": ("examples", "sample-game-full", "media"),
        "asset_dir": "sample-game",
        "files": ("gameplay.gif", "shot_title.png", "shot_level2.png", "shot_level3.png", "shot_win.png"),
        "labels": {
            "gameplay.gif": "Gameplay GIF (24.9 s)",
            "shot_title.png": "Title (de locale)",
            "shot_level2.png": "Level 2: Ruins",
            "shot_level3.png": "Level 3: Cave",
            "shot_win.png": "Win screen",
        },
        "gif": "gameplay.gif",
    },
    {
        "id": "sample-topdown",
        "title": "Ember Crypt (top-down roguelite sample)",
        "lede": "A complete Godot 4.7 top-down roguelite. Two seeded dungeon-gen floors autotiled with a 47-tile blob set, a stamped boss arena, five enemy kinds with chase, shoot and boss behaviours, loot tables, save/load, en/de/fr text, keyboard and gamepad input, 12 SFX and a mixed music loop. 86 gst tools made every asset; a seeded autoplay run clears both floors and the boss.",
        "src": ("examples", "sample-topdown", "media"),
        "asset_dir": "sample-topdown",
        "files": ("gameplay.gif", "shot_title.png", "shot_floor1.png", "shot_floor2.png", "shot_boss.png", "shot_win.png"),
        "labels": {
            "gameplay.gif": "Gameplay GIF (35 s of a 73.6 s autoplay)",
            "shot_title.png": "Title",
            "shot_floor1.png": "Floor 1 (seed 701)",
            "shot_floor2.png": "Floor 2 (seed 702)",
            "shot_boss.png": "Boss arena",
            "shot_win.png": "Win screen",
        },
        "gif": "gameplay.gif",
    },
]
# Back-compat alias used only if a caller still iterates the first showcase.
SHOWCASE_FILES = SHOWCASES[0]["files"]


def tool_dirs(root):
    """Return {name: path-to-script} the same way gst.tools() does, minus reserved."""
    reserved = {"list", "help", "info", "doctor", "test", "version", "completion",
                "bundle", "search", "categories", "docs", "fuzz"}
    out = {}
    for d in sorted(os.listdir(root)):
        p = os.path.join(root, d, d.replace("-", "_") + ".py")
        if os.path.isfile(p) and d not in reserved:
            out[d] = p
    return out


def first_paragraph(md):
    """First non-heading paragraph of a README (after the title)."""
    lines, buf, started = md.splitlines(), [], False
    for line in lines:
        s = line.strip()
        if not started:
            if s.startswith("#"):
                continue
            if not s:
                continue
            started = True
        if started:
            if not s or s.startswith("#") or s.startswith("```") or s.startswith("|"):
                break
            buf.append(s)
    return " ".join(buf).strip()


def category_map(root):
    gst = os.path.join(root, "gst")
    text = open(gst, encoding="utf-8").read()
    m = re.search(r"CATEGORIES = \{([^}]+)\}", text, re.S)
    if not m:
        return {}
    # keys are quoted tool names
    out = {}
    for km in re.finditer(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", m.group(1)):
        out[km.group(1)] = km.group(2)
    return out


def known_categories(root):
    gst = open(os.path.join(root, "gst"), encoding="utf-8").read()
    m = re.search(r"KNOWN_CATEGORIES = \((.*?)\)", gst, re.S)
    if not m:
        return []
    return re.findall(r'["\']([^"\']+)["\']', m.group(1))


# ---------- markdown ----------

_FENCE = re.compile(r"```([^\n]*)\n(.*?)```", re.S)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITAL = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")
_HEAD = re.compile(r"^(#{1,6})\s+(.*)$")


def _inline(text):
    parts = []
    i = 0
    # already-escaped HTML from links should pass through; we convert in order:
    # extract `code`, then **bold**, then *italic*
    def take(rx, kind, s, start):
        m = rx.search(s, start)
        return m

    # Walk and replace while protecting code spans first
    chunks = []
    pos = 0
    for m in _CODE.finditer(text):
        chunks.append(("t", text[pos:m.start()]))
        chunks.append(("c", m.group(1)))
        pos = m.end()
    chunks.append(("t", text[pos:]))
    out = []
    for kind, val in chunks:
        if kind == "c":
            out.append("<code>" + htmlmod.escape(val) + "</code>")
            continue
        # links already turned into placeholders? we convert links before _inline
        # so here val may contain raw <a ...>
        # split around existing tags
        bits = re.split(r"(<[^>]+>)", val)
        for i, b in enumerate(bits):
            if b.startswith("<"):
                bits[i] = b
                continue
            b = htmlmod.escape(b)
            b = _BOLD.sub(lambda mm: "<strong>" + mm.group(1) + "</strong>", b)
            b = _ITAL.sub(lambda mm: "<em>" + mm.group(1) + "</em>", b)
            bits[i] = b
        out.append("".join(bits))
    return "".join(out)


def _rewrite_md_link(url, kind, name=None):
    """Map a markdown href to a site-relative path from the page being written.

    `kind` is the page kind: 'index', 'tool', 'pipeline', 'other' (categories,
    changelog, showcase — all at the site root).
    """
    if not url:
        return url
    raw, frag = url, ""
    if "#" in url:
        raw, frag = url.split("#", 1)
        frag = "#" + frag
    if not raw:
        return url  # pure fragment
    if raw.startswith(("http://", "https://", "mailto:", "data:")):
        return url

    def prefix(target):
        # target is site-root relative, no leading slash
        if kind == "index" or kind == "other":
            return target + frag
        # tool or pipeline pages live one level down
        return "../" + target + frag

    # tool README: foo/README.md or ../foo/README.md
    m = re.match(r"^(?:\.\./)?([^/]+)/README\.md$", raw)
    if m:
        return prefix("tools/" + m.group(1) + ".html")
    if raw in ("README.md", "../README.md", "./README.md"):
        return prefix("index.html")
    if raw.endswith("CHANGELOG.md") or raw.endswith("/CHANGELOG.md"):
        return prefix("changelog.html")
    m = re.match(r"^(?:\.\./)?docs/pipelines(?:/([^/]+)\.md)?/?$", raw)
    if m:
        if m.group(1):
            return prefix("pipelines/" + m.group(1) + ".html")
        return prefix("pipelines/index.html")
    m = re.match(r"^([^/]+)\.md$", raw)
    if m and kind == "pipeline":
        return m.group(1) + ".html" + frag
    # leave unknown relative links as-is (the test will flag dangling ones)
    return url


def md_to_html(md, kind="other"):
    """Small markdown-to-HTML converter: headings, fences, lists, tables, links."""
    fences = []

    def hold_fence(m):
        fences.append((m.group(1).strip(), m.group(2)))
        return f"\x00FENCE{len(fences) - 1}\x00"

    text = _FENCE.sub(hold_fence, md)

    def sub_link(m):
        label, url = m.group(1), m.group(2)
        href = _rewrite_md_link(url, kind)
        return f'<a href="{htmlmod.escape(href, quote=True)}">{htmlmod.escape(label)}</a>'

    text = _LINK.sub(sub_link, text)

    lines = text.splitlines()
    out, i = [], 0

    def flush_para(buf):
        if buf:
            out.append("<p>" + _inline(" ".join(buf)) + "</p>")
            buf.clear()

    while i < len(lines):
        line = lines[i]
        # fences
        fm = re.match(r"^\x00FENCE(\d+)\x00$", line.strip())
        if fm:
            lang, body = fences[int(fm.group(1))]
            cls = f' class="lang-{htmlmod.escape(lang, quote=True)}"' if lang else ""
            out.append(f"<pre><code{cls}>{htmlmod.escape(body.rstrip())}\n</code></pre>")
            i += 1
            continue
        hm = _HEAD.match(line)
        if hm:
            level = len(hm.group(1))
            title = _inline(hm.group(2).strip())
            slug = re.sub(r"[^a-z0-9]+", "-", re.sub("<[^>]+>", "", hm.group(2)).lower()).strip("-")
            out.append(f'<h{level} id="{htmlmod.escape(slug, quote=True)}">{title}</h{level}>')
            i += 1
            continue
        if line.strip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*[-:]+", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            # drop the separator row
            header, body_rows = rows[0], rows[2:] if len(rows) > 1 else []
            thead = "<tr>" + "".join(f"<th>{_inline(c)}</th>" for c in header) + "</tr>"
            tbody = "".join("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>" for r in body_rows)
            out.append(f"<div class=\"table-wrap\"><table><thead>{thead}</thead><tbody>{tbody}</tbody></table></div>")
            continue
        # lists
        if re.match(r"^\s*[-*+]\s+", line) or re.match(r"^\s*\d+\.\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines) and (re.match(r"^\s*[-*+]\s+", lines[i]) or re.match(r"^\s*\d+\.\s+", lines[i])):
                item = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", lines[i])
                items.append("<li>" + _inline(item) + "</li>")
                i += 1
            out.append(f"<{tag}>" + "".join(items) + f"</{tag}>")
            continue
        if not line.strip():
            i += 1
            continue
        buf = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith("#") \
                and not lines[i].strip().startswith("|") \
                and not re.match(r"^\s*[-*+]\s+", lines[i]) \
                and not re.match(r"^\s*\d+\.\s+", lines[i]) \
                and not re.match(r"^\x00FENCE", lines[i].strip()):
            if _HEAD.match(lines[i]):
                break
            buf.append(lines[i].strip())
            i += 1
        flush_para(buf)
    return "\n".join(out)


# ---------- HTML shell ----------

CSS = """\
:root {
  --bg: #0e1116;
  --text: #e8eaed;
  --muted: #9aa0a6;
  --accent: #8ab4f8;
  --border: #2a2f3a;
  --card: #161b22;
}
* { box-sizing: border-box; }
html { color-scheme: dark; }
body {
  margin: 0;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  font-size: 16px;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.site {
  border-bottom: 1px solid var(--border);
  background: var(--card);
  position: sticky; top: 0; z-index: 10;
}
header.site .inner, main, footer.site .inner {
  max-width: 960px;
  margin: 0 auto;
  padding: 0.85rem 1.25rem;
}
header.site .inner { display: flex; flex-wrap: wrap; align-items: center; gap: 0.75rem 1.25rem; }
header.site .brand { font-weight: 650; letter-spacing: 0.01em; color: var(--text); }
header.site nav { display: flex; flex-wrap: wrap; gap: 0.9rem; }
header.site nav a { color: var(--muted); }
header.site nav a[aria-current="page"], header.site nav a:hover { color: var(--text); }
main { padding-top: 1.5rem; padding-bottom: 3rem; min-height: 70vh; }
footer.site { border-top: 1px solid var(--border); color: var(--muted); font-size: 0.9rem; }
h1 { font-size: 1.8rem; margin: 0 0 0.6rem; letter-spacing: -0.02em; }
h2 { font-size: 1.25rem; margin: 2rem 0 0.6rem; }
h3 { font-size: 1.05rem; margin: 1.4rem 0 0.4rem; }
p { margin: 0.6rem 0; }
.lede { color: var(--muted); margin-bottom: 1.4rem; }
code, pre { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 0.9em; }
code { background: #1c2128; padding: 0.1em 0.35em; border-radius: 3px; }
pre { background: #1c2128; border: 1px solid var(--border); border-radius: 6px; padding: 0.9rem 1rem; overflow: auto; }
pre code { background: none; padding: 0; }
.table-wrap { overflow: auto; margin: 1rem 0; }
table { border-collapse: collapse; width: 100%; font-size: 0.95rem; }
th, td { border-bottom: 1px solid var(--border); padding: 0.45rem 0.6rem; text-align: left; vertical-align: top; }
th { color: var(--muted); font-weight: 600; }
.search-row { display: flex; flex-wrap: wrap; gap: 0.6rem; margin: 1rem 0 1.2rem; }
#q {
  flex: 1 1 16rem;
  background: var(--card);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.55rem 0.75rem;
  font: inherit;
}
#q:focus { outline: 2px solid var(--accent); outline-offset: 1px; }
.chips { display: flex; flex-wrap: wrap; gap: 0.4rem; }
.chips button {
  background: var(--card);
  color: var(--muted);
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 0.2rem 0.7rem;
  font: inherit;
  cursor: pointer;
}
.chips button[aria-pressed="true"], .chips button:hover {
  color: var(--text);
  border-color: var(--accent);
}
#count { color: var(--muted); font-size: 0.9rem; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: 0.75rem; }
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.85rem 1rem;
  display: flex; flex-direction: column; gap: 0.35rem;
}
.card h2 { margin: 0; font-size: 1.05rem; }
.card .cat { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }
.card p { margin: 0; color: var(--muted); font-size: 0.92rem; display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden; }
.cat-group { margin: 1.5rem 0; }
.cat-group h2 { margin-top: 0; }
.cat-group ul { columns: 2; padding-left: 1.1rem; }
@media (max-width: 640px) { .cat-group ul { columns: 1; } }
.shots { display: grid; grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr)); gap: 1rem; }
.shots figure { margin: 0; background: var(--card); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.shots img { display: block; width: 100%; height: auto; background: #000; }
.shots figcaption { padding: 0.5rem 0.75rem; color: var(--muted); font-size: 0.9rem; }
.hero-gif { max-width: 100%; border: 1px solid var(--border); border-radius: 8px; display: block; margin: 1rem 0; }
.empty { color: var(--muted); padding: 1rem 0; }
"""

SEARCH_JS = """\
(function () {
  var q = document.getElementById("q");
  var count = document.getElementById("count");
  var cards = Array.prototype.slice.call(document.querySelectorAll(".card[data-name]"));
  var chips = Array.prototype.slice.call(document.querySelectorAll(".chips button[data-cat]"));
  var active = "all";
  function norm(s) { return (s || "").toLowerCase(); }
  function apply() {
    var query = norm(q && q.value);
    var words = query.split(/\\s+/).filter(Boolean);
    var shown = 0;
    cards.forEach(function (c) {
      var hay = norm(c.getAttribute("data-name") + " " + c.getAttribute("data-cat") + " " + c.getAttribute("data-blurb"));
      var okCat = active === "all" || c.getAttribute("data-cat") === active;
      var okQ = words.every(function (w) { return hay.indexOf(w) !== -1; });
      var on = okCat && okQ;
      c.style.display = on ? "" : "none";
      if (on) shown += 1;
    });
    if (count) {
      count.textContent = shown + " tool" + (shown === 1 ? "" : "s");
    }
  }
  if (q) q.addEventListener("input", apply);
  chips.forEach(function (b) {
    b.addEventListener("click", function () {
      active = b.getAttribute("data-cat");
      chips.forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      apply();
    });
  });
  apply();
})();
"""


def _nav(here, prefix):
    def item(href, label, key):
        cur = ' aria-current="page"' if here == key else ""
        return f'<a href="{prefix}{href}"{cur}>{label}</a>'
    return (
        "<nav>"
        + item("index.html", "Home", "home")
        + item("categories.html", "Categories", "categories")
        + item("pipelines/index.html", "Pipelines", "pipelines")
        + item("changelog.html", "Changelog", "changelog")
        + item("showcase.html", "Showcase", "showcase")
        + "</nav>"
    )


def page(title, body, here, prefix, extra_head="", version="", ntools=0):
    brand = "gamestudio-tools"
    if version:
        brand += f" {htmlmod.escape(version)}"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{htmlmod.escape(title)}</title>
<link rel="stylesheet" href="{prefix}assets/style.css">
{extra_head}
</head>
<body>
<header class="site"><div class="inner">
<a class="brand" href="{prefix}index.html">{brand}</a>
{_nav(here, prefix)}
</div></header>
<main>
{body}
</main>
<footer class="site"><div class="inner">
Static docs built by <code>gst docs</code>. {ntools} tools. Licensed under MIT. No CDN, no network, works from <code>file://</code>.
</div></footer>
</body>
</html>
"""


def blurb_of(root, name):
    readme = os.path.join(root, name, "README.md")
    if os.path.isfile(readme):
        return first_paragraph(open(readme, encoding="utf-8").read())
    return ""


def version_of(root):
    p = os.path.join(root, "VERSION")
    return open(p, encoding="utf-8").read().strip() if os.path.isfile(p) else ""


def build(root, dest):
    """Write the site into `dest` (created / overwritten file-by-file)."""
    root = os.path.abspath(root)
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    tools = tool_dirs(root)
    cats = category_map(root)
    known = known_categories(root) or sorted(set(cats.values()))
    ver = version_of(root)
    n = len(tools)

    assets = os.path.join(dest, "assets")
    os.makedirs(assets, exist_ok=True)
    open(os.path.join(assets, "style.css"), "w", encoding="utf-8").write(CSS)
    open(os.path.join(assets, "search.js"), "w", encoding="utf-8").write(SEARCH_JS)

    # showcase previews (one folder per project under assets/)
    copied = []
    copied_by = {}
    for sc in SHOWCASES:
        preview_src = os.path.join(root, *sc["src"])
        preview_dst = os.path.join(assets, sc["asset_dir"])
        got = []
        if os.path.isdir(preview_src):
            os.makedirs(preview_dst, exist_ok=True)
            for fn in sc["files"]:
                s = os.path.join(preview_src, fn)
                if os.path.isfile(s):
                    shutil.copy2(s, os.path.join(preview_dst, fn))
                    got.append(fn)
                    copied.append(sc["asset_dir"] + "/" + fn)
        copied_by[sc["id"]] = got

    # index
    index_entries = []
    cards = []
    for name in tools:
        cat = cats.get(name, "other")
        blurb = blurb_of(root, name)
        index_entries.append({"name": name, "category": cat, "blurb": blurb})
        cards.append(
            f'<article class="card" data-name="{htmlmod.escape(name, quote=True)}" '
            f'data-cat="{htmlmod.escape(cat, quote=True)}" '
            f'data-blurb="{htmlmod.escape(blurb, quote=True)}">'
            f'<div class="cat">{htmlmod.escape(cat)}</div>'
            f'<h2><a href="tools/{htmlmod.escape(name, quote=True)}.html">{htmlmod.escape(name)}</a></h2>'
            f'<p>{htmlmod.escape(blurb)}</p>'
            f'</article>'
        )
    chips = ['<button type="button" data-cat="all" aria-pressed="true">all</button>']
    for c in known:
        chips.append(f'<button type="button" data-cat="{htmlmod.escape(c, quote=True)}">{htmlmod.escape(c)}</button>')
    # inline search index so file:// works (no fetch)
    index_json = json.dumps(index_entries, ensure_ascii=False, separators=(",", ":"))
    body = f"""
<h1>Game studio workflow tools</h1>
<p class="lede">{n} CPU-only command-line tools. Search the index (client-side, no network) or open a category, a pipeline, the changelog, or the showcase previews.</p>
<div class="search-row">
  <input id="q" type="search" placeholder="Search tools…" autocomplete="off" spellcheck="false">
  <span id="count">{n} tools</span>
</div>
<div class="chips">{"".join(chips)}</div>
<div class="grid" id="tools">{"".join(cards)}</div>
<script type="application/json" id="search-index">{index_json}</script>
<script src="assets/search.js"></script>
"""
    open(os.path.join(dest, "index.html"), "w", encoding="utf-8").write(
        page("gamestudio-tools docs", body, "home", "", version=ver, ntools=n)
    )

    # per-tool pages
    tdir = os.path.join(dest, "tools")
    os.makedirs(tdir, exist_ok=True)
    for name in tools:
        readme = os.path.join(root, name, "README.md")
        md = open(readme, encoding="utf-8").read() if os.path.isfile(readme) else f"# {name}\n\nNo README."
        cat = cats.get(name, "other")
        content = md_to_html(md, kind="tool")
        body = f'<p class="lede"><a href="../categories.html">{htmlmod.escape(cat)}</a> · <code>{htmlmod.escape(name)}</code></p>\n{content}'
        open(os.path.join(tdir, name + ".html"), "w", encoding="utf-8").write(
            page(f"{name} — gamestudio-tools", body, "home", "../", version=ver, ntools=n)
        )

    # pipelines
    psrc = os.path.join(root, "docs", "pipelines")
    pdir = os.path.join(dest, "pipelines")
    os.makedirs(pdir, exist_ok=True)
    pipe_names = []
    if os.path.isdir(psrc):
        for fn in sorted(os.listdir(psrc)):
            if fn.endswith(".md"):
                pipe_names.append(fn[:-3])
    plist = []
    for pn in pipe_names:
        md = open(os.path.join(psrc, pn + ".md"), encoding="utf-8").read()
        blurb = first_paragraph(md)
        content = md_to_html(md, kind="pipeline")
        open(os.path.join(pdir, pn + ".html"), "w", encoding="utf-8").write(
            page(f"{pn} — pipelines", content, "pipelines", "../", version=ver, ntools=n)
        )
        plist.append(
            f'<li><a href="{htmlmod.escape(pn, quote=True)}.html"><strong>{htmlmod.escape(pn)}</strong></a>'
            f' — {htmlmod.escape(blurb)}</li>'
        )
    pindex = "<h1>Pipelines</h1><p class=\"lede\">Documented end-to-end chains. Each page is the kit's pipeline README.</p>"
    pindex += "<ul>" + "".join(plist) + "</ul>" if plist else "<p class=\"empty\">No pipelines.</p>"
    open(os.path.join(pdir, "index.html"), "w", encoding="utf-8").write(
        page("Pipelines — gamestudio-tools", pindex, "pipelines", "../", version=ver, ntools=n)
    )

    # categories
    groups = {c: [] for c in known}
    groups.setdefault("other", [])
    for name in tools:
        groups.setdefault(cats.get(name, "other"), []).append(name)
    parts = ["<h1>Categories</h1>", f'<p class="lede">{n} tools in {len(known)} categories.</p>']
    for c in known + (["other"] if groups.get("other") else []):
        names = groups.get(c) or []
        if not names and c == "other":
            continue
        lis = "".join(
            f'<li><a href="tools/{htmlmod.escape(nm, quote=True)}.html">{htmlmod.escape(nm)}</a></li>'
            for nm in names
        )
        parts.append(f'<section class="cat-group" id="{htmlmod.escape(c, quote=True)}"><h2>{htmlmod.escape(c)} <span class="lede">({len(names)})</span></h2><ul>{lis}</ul></section>')
    open(os.path.join(dest, "categories.html"), "w", encoding="utf-8").write(
        page("Categories — gamestudio-tools", "\n".join(parts), "categories", "", version=ver, ntools=n)
    )

    # changelog
    clog = os.path.join(root, "CHANGELOG.md")
    md = open(clog, encoding="utf-8").read() if os.path.isfile(clog) else "# Changelog\n\nNo changelog."
    open(os.path.join(dest, "changelog.html"), "w", encoding="utf-8").write(
        page("Changelog — gamestudio-tools", md_to_html(md, kind="other"), "changelog", "", version=ver, ntools=n)
    )

    # showcase
    shots = ['<h1>Showcase</h1>',
             '<p class="lede">Three small games whose runtime assets are produced by kit generators: two Godot 4.7 projects previewed with software GL, and a dependency-free HTML5 canvas game.</p>']
    any_preview = False
    for sc in SHOWCASES:
        got = copied_by.get(sc["id"]) or []
        if not got:
            continue
        any_preview = True
        shots.append(f'<h2>{htmlmod.escape(sc["title"])}</h2>')
        shots.append(f'<p class="lede">{htmlmod.escape(sc["lede"])}</p>')
        gif = sc.get("gif")
        if gif and gif in got:
            shots.append(
                f'<img class="hero-gif" src="assets/{htmlmod.escape(sc["asset_dir"], quote=True)}/{htmlmod.escape(gif, quote=True)}" '
                f'alt="{htmlmod.escape(sc["title"])} preview animation">'
            )
        figs = []
        labels = sc.get("labels") or {}
        for fn in got:
            if fn == gif:
                continue
            alt = labels.get(fn, fn)
            shots_src = f'assets/{htmlmod.escape(sc["asset_dir"], quote=True)}/{htmlmod.escape(fn, quote=True)}'
            figs.append(
                f'<figure><img src="{shots_src}" alt="{htmlmod.escape(alt)}">'
                f'<figcaption>{htmlmod.escape(alt)}</figcaption></figure>'
            )
        if figs:
            shots.append('<div class="shots">' + "".join(figs) + "</div>")
    if not any_preview:
        shots.append("<p class=\"empty\">No showcase previews were found next to the kit.</p>")
    open(os.path.join(dest, "showcase.html"), "w", encoding="utf-8").write(
        page("Showcase — gamestudio-tools", "".join(shots), "showcase", "", version=ver, ntools=n)
    )
    return {"dest": dest, "tools": n, "pipelines": len(pipe_names), "previews": copied}
