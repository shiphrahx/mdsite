"""Markdown rendering: markdown-it-py setup, heading slugs/anchors, link
rewriting, Pygments syntax highlighting, TOC extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Callable, Optional

from markdown_it import MarkdownIt
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight as pyg_highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.util import ClassNotFound

_SLUG_STRIP = re.compile(r"[^\w\s-]", re.UNICODE)
_SLUG_SPACE = re.compile(r"\s+")
_SLUG_DASH = re.compile(r"-+")


def slugify(text: str) -> str:
    """URL-safe heading id. Kept identical in spirit to the Node version."""
    s = str(text).strip().lower()
    s = _SLUG_STRIP.sub("", s)
    s = _SLUG_SPACE.sub("-", s)
    s = _SLUG_DASH.sub("-", s)
    s = s.strip("-")
    return s or "section"


def _highlight_code(code: str, lang: str, _attrs) -> str:
    """Pygments highlight callback for fenced code blocks. Returns full
    <pre>...</pre> markup (markdown-it-py uses it verbatim when set)."""
    try:
        lexer = get_lexer_by_name(lang) if lang else guess_lexer(code)
    except ClassNotFound:
        try:
            lexer = guess_lexer(code)
        except ClassNotFound:
            escaped = escape(code)
            return f'<pre class="hljs"><code>{escaped}</code></pre>'
    formatter = HtmlFormatter(nowrap=False, cssclass="hljs")
    return pyg_highlight(code, lexer, formatter)


def pygments_css(style: str = "default") -> str:
    """CSS for highlighted code, generated once and bundled into output."""
    return HtmlFormatter(style=style, cssclass="hljs").get_style_defs(".hljs")


def _make_md() -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": False})
        .enable(["table", "strikethrough", "linkify"])
        .use(tasklists_plugin, enabled=True)
    )
    md.options["highlight"] = _highlight_code
    return md


_MD = _make_md()


@dataclass
class Heading:
    level: int
    text: str
    slug: str


@dataclass
class Rendered:
    html: str
    headings: list[Heading]


_EXTERNAL = re.compile(r"^([a-z]+:)?//", re.IGNORECASE)
_MD_LINK = re.compile(r"\.(md|markdown)$", re.IGNORECASE)


def render(markdown: str, link_rewrite: Optional[Callable[[str], str]] = None) -> Rendered:
    """Render markdown to HTML. Injects heading ids + hover anchors, rewrites
    relative .md links via link_rewrite, hardens external links, lazy-loads
    images. Returns Rendered(html, headings)."""
    env: dict = {}
    tokens = _MD.parse(markdown, env)
    headings: list[Heading] = []
    slug_counts: dict[str, int] = {}

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1:])
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = inline.content if inline and inline.type == "inline" else ""
            slug = slugify(text)
            if slug in slug_counts:
                slug_counts[slug] += 1
                slug = f"{slug}-{slug_counts[slug]}"
            else:
                slug_counts[slug] = 0
            tok.attrSet("id", slug)
            headings.append(Heading(level=level, text=text, slug=slug))
            # Append a hover anchor link inside the heading's inline children.
            if inline is not None:
                anchor = _MD.parseInline(
                    f' <a class="anchor" href="#{slug}" aria-label="Permalink">#</a>',
                    {},
                )
                # parseInline returns a list with one inline token; graft its
                # children onto the heading's inline token.
                if anchor and anchor[0].children:
                    inline.children = (inline.children or []) + anchor[0].children

        if tok.type == "inline" and tok.children:
            for child in tok.children:
                if child.type == "link_open":
                    href = child.attrGet("href")
                    if href and link_rewrite:
                        new_href = link_rewrite(href)
                        if new_href != href:
                            child.attrSet("href", new_href)
                    if href and re.match(r"^https?://", href, re.IGNORECASE):
                        child.attrSet("rel", "noopener")
                        child.attrSet("target", "_blank")
                if child.type == "image":
                    child.attrSet("loading", "lazy")

        i += 1

    html = _MD.renderer.render(tokens, _MD.options, env)
    return Rendered(html=html, headings=headings)


def first_h1(headings: list[Heading]) -> Optional[str]:
    for h in headings:
        if h.level == 1:
            return h.text
    return None
