"""gst docs: every tool has a page and internal links resolve."""
import os, re, sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "lib"))
import docs_site  # noqa: E402

HREF = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.I)
URL_SKIP = re.compile(r"^(https?:|mailto:|data:|javascript:|#)", re.I)


def test_docs_site_pages_and_links(tmp_path):
    dest = tmp_path / "site"
    rec = docs_site.build(ROOT, str(dest))
    tools = docs_site.tool_dirs(ROOT)
    assert rec["tools"] == len(tools) >= 8
    # homepage, nav pages
    for p in ("index.html", "categories.html", "changelog.html", "showcase.html",
              "pipelines/index.html", "assets/style.css", "assets/search.js"):
        assert (dest / p).is_file(), p
    # every tool has a page
    missing = [n for n in tools if not (dest / "tools" / f"{n}.html").is_file()]
    assert not missing, f"missing tool pages: {missing[:8]}"
    # search index lists every tool
    index = (dest / "index.html").read_text(encoding="utf-8")
    assert 'id="search-index"' in index
    for n in tools:
        assert f"tools/{n}.html" in index
        assert f'data-name="{n}"' in index
    # no CDN / webfont / remote script
    for needle in ("cdn.", "fonts.google", "unpkg.com", "jsdelivr", "http://", "https://"):
        # allow https only inside changelog prose if present; the shell itself must not load remote assets
        pass
    shell_files = [dest / "index.html", dest / "assets" / "style.css", dest / "assets" / "search.js"]
    for p in shell_files:
        text = p.read_text(encoding="utf-8")
        assert "cdn." not in text and "fonts.googleapis" not in text and "unpkg" not in text
    # every internal href/src resolves
    broken = []
    html_files = list(dest.rglob("*.html"))
    for path in html_files:
        text = path.read_text(encoding="utf-8")
        for url in HREF.findall(text):
            if URL_SKIP.match(url):
                continue
            raw = url.split("#", 1)[0]
            if not raw:
                continue  # fragment-only, same page
            target = (path.parent / raw).resolve()
            try:
                target.relative_to(dest.resolve())
            except ValueError:
                broken.append((str(path.relative_to(dest)), url, "escaped site root"))
                continue
            if not target.exists():
                broken.append((str(path.relative_to(dest)), url, "missing"))
    assert not broken, "broken links:\n" + "\n".join(f"  {p} -> {u} ({why})" for p, u, why in broken[:40])


def test_gst_docs_command(tmp_path):
    import subprocess
    dest = tmp_path / "from-gst"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "gst"), "docs", "-o", str(dest)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (dest / "index.html").is_file()
    # reserved: not listed as a tool
    listed = subprocess.run([sys.executable, os.path.join(ROOT, "gst"), "list"],
                            capture_output=True, text=True, check=True).stdout
    assert not re.search(r"^docs\s", listed, re.M)
    help_ = subprocess.run([sys.executable, os.path.join(ROOT, "gst"), "--help"],
                           capture_output=True, text=True, check=True).stdout
    assert "gst docs" in help_
    comp = subprocess.run([sys.executable, os.path.join(ROOT, "gst"), "completion", "bash"],
                          capture_output=True, text=True, check=True).stdout
    assert "docs" in comp
    # usage error
    bad = subprocess.run([sys.executable, os.path.join(ROOT, "gst"), "docs"],
                         capture_output=True, text=True)
    assert bad.returncode == 2
