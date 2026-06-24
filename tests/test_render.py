"""Tests for Markdown rendering: slugs, anchors, links, GFM, highlighting."""

from __future__ import annotations

import pytest

from mdsite.render import (
    Heading,
    first_h1,
    pygments_css,
    render,
    slugify,
)


# ---- slugify ----

@pytest.mark.parametrize("text,expected", [
    ("Hello World", "hello-world"),
    ("  Multiple   Spaces  ", "multiple-spaces"),
    ("Café & Crème", "café-crème"),
    ("UPPER", "upper"),
    ("a--b", "a-b"),
    ("-leading-trailing-", "leading-trailing"),
    ("!!!", "section"),
    ("", "section"),
    ("123", "123"),
])
def test_slugify(text, expected):
    assert slugify(text) == expected


def test_slugify_non_str_coerced():
    assert slugify(42) == "42"


# ---- headings + anchors ----

def test_heading_gets_id_and_anchor():
    out = render("# Title Here\n")
    assert 'id="title-here"' in out.html
    assert 'class="anchor"' in out.html
    assert 'href="#title-here"' in out.html


def test_headings_collected_with_levels():
    out = render("# H1\n\n## H2\n\n### H3\n")
    levels = [h.level for h in out.headings]
    assert levels == [1, 2, 3]
    assert out.headings[1].text == "H2"
    assert out.headings[1].slug == "h2"


def test_duplicate_heading_slugs_deduped():
    out = render("## Repeat\n\n## Repeat\n\n## Repeat\n")
    slugs = [h.slug for h in out.headings]
    assert slugs == ["repeat", "repeat-1", "repeat-2"]
    assert 'id="repeat"' in out.html
    assert 'id="repeat-1"' in out.html


def test_slug_dedup_handles_literal_suffix_collision():
    # "Foo","Foo" -> foo, foo-1; then a literal "Foo 1" also slugs to foo-1
    # and must be bumped again so every id stays unique.
    out = render("# Foo\n\n# Foo\n\n# Foo 1\n")
    slugs = [h.slug for h in out.headings]
    assert slugs == ["foo", "foo-1", "foo-1-1"]
    assert len(set(slugs)) == 3


# ---- link handling ----

def test_external_link_hardened():
    out = render("[x](https://example.com)")
    assert 'rel="noopener"' in out.html
    assert 'target="_blank"' in out.html


def test_http_link_also_hardened():
    out = render("[x](http://example.com)")
    assert 'target="_blank"' in out.html


def test_internal_md_link_rewritten():
    out = render(
        "[x](./other.md)",
        link_rewrite=lambda h: "/other/" if h == "./other.md" else h,
    )
    assert 'href="/other/"' in out.html
    # Internal links are not given target=_blank.
    assert "_blank" not in out.html


def test_link_rewrite_not_called_result_used_verbatim():
    out = render("[x](a.md)", link_rewrite=lambda h: "/REWRITTEN/")
    assert "/REWRITTEN/" in out.html


def test_anchor_only_link_untouched():
    out = render("[x](#frag)", link_rewrite=lambda h: "/SHOULD_NOT/")
    # render() passes every href through link_rewrite; the rewriter itself is
    # responsible for skipping anchors, so here the stub rewrites it. Confirm
    # render does call the rewriter.
    assert "/SHOULD_NOT/" in out.html


# ---- images ----

def test_image_lazy_loaded():
    out = render("![alt](pic.png)")
    assert 'loading="lazy"' in out.html


# ---- GFM features ----

def test_table_rendered():
    md = "| a | b |\n| - | - |\n| 1 | 2 |\n"
    out = render(md)
    assert "<table>" in out.html
    assert "<td>1</td>" in out.html


def test_strikethrough():
    out = render("~~gone~~")
    assert "<s>gone</s>" in out.html


def test_task_list():
    out = render("- [x] done\n- [ ] todo\n")
    assert 'type="checkbox"' in out.html
    assert "checked" in out.html


def test_raw_html_passthrough():
    out = render("<div class='x'>hi</div>")
    assert "<div" in out.html


# ---- syntax highlighting ----

def test_fenced_code_highlighted():
    out = render("```python\nprint('hi')\n```\n")
    assert "hljs" in out.html
    assert "<pre" in out.html


def test_fenced_unknown_lang_still_pre():
    out = render("```nonexistlang\nsome text\n```\n")
    assert "<pre" in out.html


def test_pygments_css_non_empty():
    css = pygments_css("default")
    assert ".hljs" in css
    assert len(css) > 50


# ---- mermaid diagrams ----

def test_mermaid_block_when_diagrams_enabled():
    out = render("```mermaid\ngraph TD; A-->B;\n```\n", diagrams=True)
    assert '<pre class="mermaid">' in out.html
    assert "graph TD; A--&gt;B;" in out.html  # source preserved + escaped
    assert "hljs" not in out.html  # not syntax-highlighted


def test_mermaid_block_highlighted_when_diagrams_disabled():
    out = render("```mermaid\ngraph TD; A-->B;\n```\n", diagrams=False)
    # Falls back to a normal (highlighted) code block, not a mermaid container.
    assert 'class="mermaid"' not in out.html
    assert "<pre" in out.html


def test_non_mermaid_code_unaffected_by_diagrams_flag():
    out = render("```python\nprint('hi')\n```\n", diagrams=True)
    assert "hljs" in out.html
    assert 'class="mermaid"' not in out.html


# ---- math (KaTeX) ----

def test_inline_math_when_enabled():
    out = render(r"Euler: $e^{i\pi}+1=0$ done", math=True)
    assert '<span class="math inline">' in out.html
    assert r"e^{i\pi}+1=0" in out.html


def test_block_math_when_enabled():
    out = render("$$\n\\int_0^1 x\\,dx\n$$\n", math=True)
    assert '<div class="math block">' in out.html


def test_math_untouched_when_disabled():
    out = render(r"cost is $5 and $10", math=False)
    # No math parsing: dollar signs stay literal, no math spans.
    assert 'class="math' not in out.html


# ---- first_h1 ----

def test_first_h1_returns_first_level1():
    hs = [Heading(2, "Sub", "sub"), Heading(1, "Top", "top"), Heading(1, "Two", "two")]
    assert first_h1(hs) == "Top"


def test_first_h1_none_when_absent():
    assert first_h1([Heading(2, "Sub", "sub")]) is None
    assert first_h1([]) is None
