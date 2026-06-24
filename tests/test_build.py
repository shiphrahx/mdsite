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


def test_custom_css_appended(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "brand.css", ".markdown-body { font-family: Comic Sans; }")
    (src / "mdsite.config.json").write_text(
        json.dumps({"custom_css": "brand.css"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    style = (out / "assets" / "style.css").read_text(encoding="utf-8")
    assert "Comic Sans" in style
    # The CSS source file itself is not also copied as a standalone asset page.
    assert not (out / "brand" / "index.html").exists()


def test_custom_css_missing_file_warns(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "mdsite.config.json").write_text(
        json.dumps({"custom_css": "nope.css"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    # Missing custom_css must warn but not abort the build.
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    assert "custom_css" in capsys.readouterr().out


def test_404_page_generated(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "page.md", "# Page\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    nf = out / "404.html"
    assert nf.exists()
    body = nf.read_text(encoding="utf-8")
    assert "Page not found" in body
    # Carries the nav + a home link, and is a full styled page.
    assert "assets/style.css" in body
    assert 'href="/page/"' in body  # nav rendered


def test_404_page_respects_base(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True, "base": "/docs/"})
    body = (out / "404.html").read_text(encoding="utf-8")
    assert "/docs/assets/style.css" in body
    assert 'href="/docs/"' in body  # home link


def test_404_page_can_be_disabled(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "mdsite.config.json").write_text(
        json.dumps({"error_page": False}), encoding="utf-8"
    )
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    assert not (out / "404.html").exists()


def test_last_updated_disabled_by_default(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    assert "page-updated" not in (out / "index.html").read_text(encoding="utf-8")


def test_last_updated_mtime_mode(tmp_path):
    import os
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    os.utime(src / "index.md", (1609588800, 1609588800))  # 2021-01-02 UTC
    (src / "mdsite.config.json").write_text(
        json.dumps({"last_updated": "mtime"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'class="page-updated"' in home
    assert "2021-01-02" in home
    assert '<time datetime="2021-01-02">' in home


def test_logo_and_favicon(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "logo.svg").write_bytes(b"<svg/>")
    (src / "fav.ico").write_bytes(b"ICO")
    (src / "mdsite.config.json").write_text(
        json.dumps({"logo": "logo.svg", "favicon": "fav.ico"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    # Files copied into assets/ under their basename.
    assert (out / "assets" / "logo.svg").read_bytes() == b"<svg/>"
    assert (out / "assets" / "fav.ico").read_bytes() == b"ICO"
    home = (out / "index.html").read_text(encoding="utf-8")
    assert '<link rel="icon" href="/assets/fav.ico">' in home
    assert '<img class="site-logo" src="/assets/logo.svg"' in home


def test_logo_favicon_respect_base(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "logo.svg").write_bytes(b"<svg/>")
    (src / "mdsite.config.json").write_text(
        json.dumps({"logo": "logo.svg"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True, "base": "/docs/"})
    home = (out / "index.html").read_text(encoding="utf-8")
    assert 'src="/docs/assets/logo.svg"' in home


def test_missing_logo_warns(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    (src / "mdsite.config.json").write_text(
        json.dumps({"logo": "nope.png", "favicon": "nope.ico"}), encoding="utf-8"
    )
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    err = capsys.readouterr().out
    assert "logo file not found" in err
    assert "favicon file not found" in err


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


def test_link_to_draft_not_rewritten(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n\n[d](./secret.md)\n")
    _write(src / "secret.md", "---\ndraft: true\n---\n# Secret\n")
    out = tmp_path / "out"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 1
    body = (out / "index.html").read_text(encoding="utf-8")
    # Draft is excluded from output, so its link is left as the raw .md href
    # rather than rewritten to a clean URL that would 404.
    assert "/secret/" not in body
    assert "secret.md" in body


def test_link_rewrite_preserves_query_and_fragment(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n\n[x](./page.md?v=2#sec)\n")
    _write(src / "page.md", "# Page\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    body = (out / "index.html").read_text(encoding="utf-8")
    assert 'href="/page/?v=2#sec"' in body


def test_clean_removes_orphan_output(tmp_path):
    src = tmp_path / "src"
    _write(src / "index.md", "# Home\n")
    _write(src / "page.md", "# Page\n")
    out = tmp_path / "out"
    build(str(src), {"out": str(out), "clean": True})
    assert (out / "page" / "index.html").exists()
    # Remove the source page and rebuild clean — stale output must be gone.
    # serve forces clean=True for exactly this reason.
    (src / "page.md").unlink()
    build(str(src), {"out": str(out), "clean": True})
    assert not (out / "page" / "index.html").exists()


class _Evt:
    def __init__(self, path, is_dir=False):
        self.src_path = path
        self.is_directory = is_dir


def test_rebuild_ignores_output_dir(tmp_path):
    """Writes under the out dir must not trigger a rebuild (would loop forever
    when out lives inside src, e.g. `mdsite serve .`)."""
    from mdsite.serve import _RebuildHandler

    out = (tmp_path / "dist").resolve()
    out.mkdir()
    fired = threading.Event()
    h = _RebuildHandler(lambda: fired.set(), ignore_under=out, debounce_s=0.01)

    # Event inside out/ is ignored.
    h.on_any_event(_Evt(str(out / "index.html")))
    assert not fired.wait(0.2), "rebuild fired on output-dir write"

    # Event outside out/ still triggers a rebuild.
    h.on_any_event(_Evt(str(tmp_path / "page.md")))
    assert fired.wait(1.0), "rebuild did not fire on source change"


def test_rebuild_skips_directory_events(tmp_path):
    from mdsite.serve import _RebuildHandler
    fired = threading.Event()
    h = _RebuildHandler(lambda: fired.set(), debounce_s=0.01)
    h.on_any_event(_Evt(str(tmp_path / "sub"), is_dir=True))
    assert not fired.wait(0.2)


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
