"""Markdown rendering: markdown-it-py setup, heading slugs/anchors, link
rewriting, Pygments syntax highlighting, TOC extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Callable, Optional

from markdown_it import MarkdownIt
from mdit_py_plugins.dollarmath import dollarmath_plugin
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


def _make_highlight(diagrams: bool):
    """Highlight callback. With diagrams on, ```mermaid fences are emitted as
    <pre class="mermaid"> (rendered client-side) instead of syntax-highlighted."""
    def highlight(code: str, lang: str, attrs) -> str:
        if diagrams and lang == "mermaid":
            return f'<pre class="mermaid">{escape(code)}</pre>'
        return _highlight_code(code, lang, attrs)
    return highlight


def _make_md(diagrams: bool = False, math: bool = False) -> MarkdownIt:
    md = (
        MarkdownIt("commonmark", {"html": True, "linkify": True, "typographer": False})
        .enable(["table", "strikethrough", "linkify"])
        .use(tasklists_plugin, enabled=True)
    )
    if math:
        # Protects $…$ / $$…$$ spans from markdown mangling; emits
        # <span class="math inline"> / <div class="math block"> with raw LaTeX,
        # rendered client-side by KaTeX.
        md.use(dollarmath_plugin)
    md.options["highlight"] = _make_highlight(diagrams)
    return md


# Cache one MarkdownIt instance per feature combination (setup is not free).
_MD_CACHE: dict[tuple, MarkdownIt] = {}


def _get_md(diagrams: bool = False, math: bool = False) -> MarkdownIt:
    key = (bool(diagrams), bool(math))
    md = _MD_CACHE.get(key)
    if md is None:
        md = _make_md(diagrams=diagrams, math=math)
        _MD_CACHE[key] = md
    return md


@dataclass
class Heading:
    level: int
    text: str
    slug: str


@dataclass
class Rendered:
    html: str
    headings: list[Heading]


def render(markdown: str, link_rewrite: Optional[Callable[[str], str]] = None,
           diagrams: bool = False, math: bool = False) -> Rendered:
    """Render markdown to HTML. Injects heading ids + hover anchors, rewrites
    relative .md links via link_rewrite, hardens external links, lazy-loads
    images. With diagrams=True, ```mermaid blocks become client-rendered
    diagrams; with math=True, $…$/$$…$$ become KaTeX-rendered math. Returns
    Rendered(html, headings)."""
    md = _get_md(diagrams, math)
    env: dict = {}
    tokens = md.parse(markdown, env)
    headings: list[Heading] = []
    used_slugs: set[str] = set()

    i = 0
    while i < len(tokens):
        tok = tokens[i]

        if tok.type == "heading_open":
            level = int(tok.tag[1:])
            inline = tokens[i + 1] if i + 1 < len(tokens) else None
            text = inline.content if inline and inline.type == "inline" else ""
            base_slug = slugify(text)
            slug = base_slug
            n = 0
            # Guarantee global uniqueness, even against a literal heading whose
            # text already equals an auto-suffixed slug (e.g. "Foo","Foo","Foo 1").
            while slug in used_slugs:
                n += 1
                slug = f"{base_slug}-{n}"
            used_slugs.add(slug)
            tok.attrSet("id", slug)
            headings.append(Heading(level=level, text=text, slug=slug))
            # Append a hover anchor link inside the heading's inline children.
            if inline is not None:
                anchor = md.parseInline(
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

    html = md.renderer.render(tokens, md.options, env)
    return Rendered(html=html, headings=headings)


def first_h1(headings: list[Heading]) -> Optional[str]:
    for h in headings:
        if h.level == 1:
            return h.text
    return None
