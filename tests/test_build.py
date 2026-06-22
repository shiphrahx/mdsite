"""Tests for the build pipeline + edge cases."""

from __future__ import annotations

import json
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from mdsite.build import build, output_path_for, url_for
from mdsite.config import make_exclude_matcher
from mdsite.nav import Page, build_nav, prev_next_map
from mdsite.render import render, slugify


# ---- unit: pure helpers ----

def test_output_path_for():
    assert output_path_for("foo/bar.md") == "foo/bar/index.html"
    assert output_path_for("foo/index.md") == "foo/index.html"
    assert output_path_for("index.md") == "index.html"
    assert output_path_for("README.md") == "index.html"


def test_url_for_base():
    assert url_for("foo/bar/index.html", "/") == "/foo/bar/"
    assert url_for("index.html", "/") == "/"
    assert url_for("foo/index.html", "/docs/") == "/docs/foo/"


def test_slugify_unicode_and_spaces():
    assert slugify("Hello World") == "hello-world"
    assert slugify("  Multiple   Spaces  ") == "multiple-spaces"
    assert slugify("Café & Crème") == "café-crème"
    assert slugify("!!!") == "section"


def test_exclude_matcher():
    m = make_exclude_matcher(["drafts/**", "*.tmp.md"])
    assert m("drafts/secret.md")
    assert m("drafts/a/b.md")
    assert m("notes.tmp.md")
    assert not m("public/notes.md")


def test_link_rewrite_relative_md():
    out = render("[x](./other.md)", link_rewrite=lambda h: "/other/" if h == "./other.md" else h)
    assert "/other/" in out.html


def test_external_link_hardened():
    out = render("[x](https://example.com)")
    assert 'rel="noopener"' in out.html


def test_nav_prev_next_order():
    pages = [
        Page("index.md", "/", "Home", 1, True),
        Page("a.md", "/a/", "A", 2, False),
        Page("b.md", "/b/", "B", None, False),
    ]
    _, ordered = build_nav(pages)
    assert [l.url for l in ordered] == ["/", "/a/", "/b/"]
    nm = prev_next_map(ordered)
    assert nm["/"]["next"].url == "/a/"
    assert nm["/b/"]["prev"].url == "/a/"
    assert nm["/b/"]["next"] is None


# ---- integration: build edge cases ----

def _write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_empty_folder_errors(tmp_path):
    (tmp_path / "src").mkdir()
    with pytest.raises(RuntimeError, match="no .md files"):
        build(str(tmp_path / "src"), {"out": str(tmp_path / "out")})


def test_missing_folder_errors(tmp_path):
    with pytest.raises(RuntimeError, match="not found"):
        build(str(tmp_path / "nope"), {"out": str(tmp_path / "out")})


def test_basic_build(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n\n[next](./page.md)\n")
    _write(src / "page.md", "---\ntitle: Page\n---\n# Page\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 2
    assert (out / "index.html").exists()
    assert (out / "page" / "index.html").exists()
    assert (out / "assets" / "style.css").exists()
    assert (out / "search-index.json").exists()
    assert (out / "sitemap.xml").exists()
    # Link rewritten.
    assert "/page/" in (out / "index.html").read_text(encoding="utf-8")


def test_draft_skipped(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "draft.md", "---\ndraft: true\n---\n# Secret\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    assert not (out / "draft" / "index.html").exists()


def test_malformed_frontmatter_continues(tmp_path, capsys):
    src = tmp_path / "src"
    # Unterminated/invalid YAML front matter.
    _write(src / "index.md", "---\ntitle: [unclosed\n---\n# Body\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    assert (out / "index.html").exists()


def test_asset_passthrough(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "img").mkdir()
    (src / "img" / "logo.svg").write_bytes(b"<svg></svg>")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    assert (out / "img" / "logo.svg").read_bytes() == b"<svg></svg>"


def test_binary_md_skipped(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    # Invalid UTF-8 bytes with a .md extension.
    (src / "bad.md").write_bytes(b"\xff\xfe\x00binary")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1


def test_unicode_filename(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "café notes.md", "# Café\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    # Slugified into a safe URL path.
    assert (out / "café-notes" / "index.html").exists()


def test_config_title_and_exclude(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "skip.tmp.md", "# Skip\n")
    (src / "mdsite.config.json").write_text(
        json.dumps({"title": "Cfg", "exclude": ["*.tmp.md"]}), encoding="utf-8"
    )
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    assert "Cfg" in (out / "index.html").read_text(encoding="utf-8")


def test_readme_dropped_when_index_present(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "guide" / "index.md", "# Guide Index\n")
    _write(src / "guide" / "README.md", "# Guide Readme\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 2
    body = (out / "guide" / "index.html").read_text(encoding="utf-8")
    assert "Guide Index" in body
    assert "Guide Readme" not in body
    err = capsys.readouterr().out
    assert "guide/README.md" in err


def test_readme_used_as_index_when_alone(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "guide" / "README.md", "# Guide Readme\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 2
    assert (out / "guide" / "index.html").exists()
    assert "Guide Readme" in (out / "guide" / "index.html").read_text(encoding="utf-8")


def test_link_rewrite_parent_traversal(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "top.md", "# Top\n")
    # ../ climbs out of guide/ back to the source root.
    _write(src / "guide" / "intro.md", "# Intro\n\n[up](../top.md)\n[home](../index.md)\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    body = (out / "guide" / "intro" / "index.html").read_text(encoding="utf-8")
    assert 'href="/top/"' in body
    assert 'href="/"' in body


def test_search_index_shape(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n\nHello **world** with a `code` span.\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    idx = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    assert isinstance(idx, list)
    rec = idx[0]
    assert set(rec) == {"title", "url", "text"}
    # Body is tag-stripped plain text.
    assert "<" not in rec["text"]
    assert "Hello world with a code span" in rec["text"]


# ---- serve mode ----

def test_live_reload_snippet_injected(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True}, live_reload="<!--LR-->")
    assert "<!--LR-->" in (out / "index.html").read_text(encoding="utf-8")


def test_reload_hub_broadcast():
    from mdsite.serve import _ReloadHub
    hub = _ReloadHub()
    q = hub.subscribe()
    hub.broadcast()
    assert q.get(timeout=1) == "reload"
    hub.unsubscribe(q)
    hub.broadcast()  # no subscribers left; must not raise


def test_serve_handler_serves_clean_urls(tmp_path):
    from mdsite.serve import _ReloadHub, _find_free_port, _make_handler

    root = tmp_path / "site"
    (root / "foo").mkdir(parents=True)
    (root / "index.html").write_text("<h1>home</h1>", encoding="utf-8")
    (root / "foo" / "index.html").write_text("<h1>foo page</h1>", encoding="utf-8")

    port = _find_free_port(8999)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), _make_handler(root, _ReloadHub()))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        base = f"http://127.0.0.1:{port}"
        assert "home" in urllib.request.urlopen(base + "/", timeout=2).read().decode()
        # Clean URL /foo/ resolves to foo/index.html.
        assert "foo page" in urllib.request.urlopen(base + "/foo/", timeout=2).read().decode()
    finally:
        httpd.shutdown()


def test_base_applied_to_output(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "page.md", "# Page\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True, "base": "/docs/"})
    home = (out / "index.html").read_text(encoding="utf-8")
    # Asset + nav URLs carry the base prefix.
    assert "/docs/assets/style.css" in home
    assert 'href="/docs/page/"' in home
    idx = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
    assert "/docs/page/" in {r["url"] for r in idx}


def test_base_normalized_without_slashes(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    out = tmp_path / "out"
    # "docs" (no leading/trailing slash) must normalize to "/docs/".
    build(str(src), {"out": str(out), "clean": True, "base": "docs"})
    home = (out / "index.html").read_text(encoding="utf-8")
    assert "/docs/assets/style.css" in home
    assert "/docsassets/" not in home


def test_performance_500_files(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    for i in range(500):
        _write(src / f"sec{i // 50}" / f"page{i}.md",
               f"# Page {i}\n\nSome text with a `code` span and a list:\n\n- a\n- b\n")
    out = tmp_path / "out"
    start = time.perf_counter()
    result = build(str(src), {"out": str(out), "clean": True})
    elapsed = time.perf_counter() - start
    assert result["page_count"] == 501
    # Generous CI-safe bound; spec target is ~3s on a laptop.
    assert elapsed < 15, f"build took {elapsed:.2f}s"
