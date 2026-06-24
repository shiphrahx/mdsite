"""Tests for HTML template assembly: nav, TOC, prev/next, page shell, assets."""

from __future__ import annotations

from mdsite.layout import (
    render_nav,
    render_page,
    render_prev_next,
    render_toc,
    write_assets,
)
from mdsite.nav import Link, Page, build_nav
from mdsite.render import Heading


def _tree():
    pages = [
        Page("index.md", "/", "Home", 1, True),
        Page("guide/index.md", "/guide/", "Guide", None, True),
        Page("guide/intro.md", "/guide/intro/", "Intro", None, False),
        Page("loose/a.md", "/loose/a/", "Loose A", None, False),
    ]
    tree, _ = build_nav(pages)
    return tree


# ---- render_nav ----

def test_nav_renders_nested_ul():
    html = render_nav(_tree(), "/")
    assert html.startswith("<ul>")
    assert html.count("<ul>") >= 2  # nested folders


def test_nav_folder_with_index_is_link():
    html = render_nav(_tree(), "/")
    assert '<a class="folder-link" href="/guide/">Guide</a>' in html
    assert 'href="/guide/intro/"' in html


def test_nav_folder_without_index_is_span():
    html = render_nav(_tree(), "/")
    # "loose" has no index page -> rendered as a non-link folder name.
    assert '<span class="folder-name">loose</span>' in html


def test_nav_data_path_present():
    html = render_nav(_tree(), "/")
    assert 'data-path="guide"' in html


def test_nav_escapes_title():
    pages = [
        Page("index.md", "/", "Home", 1, True),
        Page("x.md", "/x/", "A <script>", None, False),
    ]
    tree, _ = build_nav(pages)
    html = render_nav(tree, "/")
    assert "&lt;script&gt;" in html
    assert "<script>" not in html


def test_nav_empty_tree():
    pages = [Page("index.md", "/", "Home", 1, True)]
    tree, _ = build_nav(pages)
    # Root index sets url but has no children/pages -> empty inner ul.
    html = render_nav(tree, "/")
    assert html == ""


# ---- render_toc ----

def test_toc_empty_when_under_two_headings():
    assert render_toc([Heading(1, "Only", "only")]) == ""


def test_toc_empty_when_no_h2_h3():
    assert render_toc([Heading(1, "A", "a"), Heading(1, "B", "b")]) == ""


def test_toc_lists_h2_h3():
    headings = [Heading(1, "Title", "title"), Heading(2, "Two", "two"), Heading(3, "Three", "three")]
    html = render_toc(headings)
    assert "On this page" in html
    assert 'href="#two"' in html
    assert 'class="toc-h3"' in html


def test_toc_escapes_text():
    headings = [Heading(1, "T", "t"), Heading(2, "<b>", "b")]
    html = render_toc(headings)
    assert "&lt;b&gt;" in html


# ---- render_prev_next ----

def test_prev_next_both():
    html = render_prev_next(Link("/p/", "Prev"), Link("/n/", "Next"), "/")
    assert 'class="pn-prev" href="/p/"' in html
    assert 'class="pn-next" href="/n/"' in html


def test_prev_next_empty_spans():
    html = render_prev_next(None, None, "/")
    assert html == "<span></span><span></span>"


def test_prev_next_escapes_title():
    html = render_prev_next(Link("/p/", "<x>"), None, "/")
    assert "&lt;x&gt;" in html


# ---- render_page ----

def test_render_page_fills_placeholders():
    html = render_page(
        page_title="Page · Site",
        site_title="Site",
        description="desc",
        content="<p>BODY</p>",
        nav_html="<ul>NAV</ul>",
        toc_html="TOC",
        prev_next_html="PN",
        footer="FOOT",
        theme="dark",
        base="/docs/",
        live_reload="<!--LR-->",
    )
    assert "<p>BODY</p>" in html
    assert "<ul>NAV</ul>" in html
    assert "/docs/assets/style.css" in html
    assert 'data-theme-default="dark"' in html
    assert "<!--LR-->" in html
    assert "FOOT" in html


def test_render_page_escapes_title():
    html = render_page(
        page_title="<evil>",
        site_title="<s>",
        description="",
        content="",
        nav_html="",
        toc_html="",
        prev_next_html="",
        footer="",
        theme="auto",
        base="/",
    )
    assert "<title><evil></title>" not in html
    assert "&lt;evil&gt;" in html


def test_render_page_head_extra_and_logo():
    html = render_page(
        page_title="P",
        site_title="Site",
        description="",
        content="",
        nav_html="",
        toc_html="",
        prev_next_html="",
        footer="",
        theme="auto",
        base="/",
        head_extra='<link rel="icon" href="/assets/f.ico">',
        logo_html='<img class="site-logo" src="/assets/l.svg" alt="">',
    )
    assert '<link rel="icon" href="/assets/f.ico">' in html
    # head_extra lands inside <head>, before </head>.
    assert html.index('rel="icon"') < html.index("</head>")
    # logo sits inside the site-title link, before the title text.
    assert html.index("site-logo") < html.index(">Site</a>")


def test_render_page_slots_default_empty():
    html = render_page(
        page_title="P", site_title="S", description="", content="",
        nav_html="", toc_html="", prev_next_html="", footer="",
        theme="auto", base="/",
    )
    # Unfilled slots leave no literal placeholder braces behind.
    assert "{head_extra}" not in html
    assert "{logo_html}" not in html


# ---- write_assets ----

def test_write_assets_creates_files(tmp_path):
    write_assets(tmp_path)
    assets = tmp_path / "assets"
    assert (assets / "style.css").exists()
    assert (assets / "app.js").exists()
    assert (assets / "search.js").exists()


def test_write_assets_bundles_pygments_css(tmp_path):
    write_assets(tmp_path)
    style = (tmp_path / "assets" / "style.css").read_text(encoding="utf-8")
    assert "Pygments" in style
    assert ".hljs" in style


def test_write_assets_appends_custom_css_last(tmp_path):
    write_assets(tmp_path, extra_css=".brand { color: hotpink; }")
    style = (tmp_path / "assets" / "style.css").read_text(encoding="utf-8")
    assert ".brand { color: hotpink; }" in style
    # Custom CSS must come AFTER the bundled defaults so its rules win.
    assert style.index(".brand") > style.index("Pygments")


def test_write_assets_no_custom_css_marker_when_empty(tmp_path):
    write_assets(tmp_path)
    style = (tmp_path / "assets" / "style.css").read_text(encoding="utf-8")
    assert "Custom CSS" not in style
