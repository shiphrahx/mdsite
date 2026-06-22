"""HTML template assembly: page shell, nav tree, TOC, prev/next."""

from __future__ import annotations

from html import escape
from importlib import resources
from pathlib import Path

from .nav import NavNode
from .render import Heading, pygments_css

_TEMPLATE_FILES = ("page.html", "style.css", "app.js", "search.js")


def _load(name: str) -> str:
    return resources.files("mdsite").joinpath("templates", name).read_text(encoding="utf-8")


_PAGE = _load("page.html")


def render_nav(tree: NavNode, current_url: str, base: str) -> str:
    """Render the sidebar nav tree as nested <ul>. Current page highlighted."""

    def render_node(node: NavNode, path: str) -> str:
        items: list[str] = []
        # Folder landing link (if the folder has an index page).
        # Folders render as collapsible groups; pages as plain links.
        for child in node.children:
            child_path = f"{path}/{child.name}" if path else child.name
            label_url = child.url
            label = escape(child.title or child.name)
            inner = render_node(child, child_path)
            current_cls = " current" if label_url == current_url else ""
            if label_url:
                label_html = (
                    f'<a class="folder-link{current_cls}" href="{label_url}">{label}</a>'
                )
            else:
                label_html = f'<span class="folder-name">{label}</span>'
            items.append(
                f'<li class="nav-folder" data-path="{escape(child_path)}">'
                f'<div class="folder-label"><span class="caret">▾</span>{label_html}</div>'
                f"{inner}</li>"
            )
        for page in node.pages:
            cls = " current" if page.url == current_url else ""
            items.append(
                f'<li><a class="{cls.strip()}" href="{page.url}">{escape(page.title)}</a></li>'
            )
        if not items:
            return ""
        return "<ul>" + "".join(items) + "</ul>"

    return render_node(tree, "")


def render_toc(headings: list[Heading]) -> str:
    """Right-sidebar TOC from H2/H3. Empty if fewer than 2 headings total."""
    relevant = [h for h in headings if h.level in (2, 3)]
    if len(headings) < 2 or not relevant:
        return ""
    items = ['<div class="toc-title">On this page</div>', "<ul>"]
    for h in relevant:
        cls = "toc-h3" if h.level == 3 else "toc-h2"
        items.append(f'<li><a class="{cls}" href="#{h.slug}">{escape(h.text)}</a></li>')
    items.append("</ul>")
    return "".join(items)


def render_prev_next(prev, nxt, base: str) -> str:
    parts: list[str] = []
    if prev:
        parts.append(
            f'<a class="pn-prev" href="{prev.url}">'
            f'<span class="pn-dir">← Previous</span>'
            f'<span class="pn-title">{escape(prev.title)}</span></a>'
        )
    else:
        parts.append("<span></span>")
    if nxt:
        parts.append(
            f'<a class="pn-next" href="{nxt.url}">'
            f'<span class="pn-dir">Next →</span>'
            f'<span class="pn-title">{escape(nxt.title)}</span></a>'
        )
    else:
        parts.append("<span></span>")
    return "".join(parts)


def render_page(*, page_title, site_title, description, content, nav_html,
                toc_html, prev_next_html, footer, theme, base, live_reload="") -> str:
    return _PAGE.format(
        page_title=escape(page_title),
        site_title=escape(site_title),
        description=escape(description or ""),
        content=content,
        nav_html=nav_html,
        toc_html=toc_html,
        prev_next_html=prev_next_html,
        footer=footer or "",
        theme=escape(theme or "auto"),
        base=base,
        live_reload=live_reload,
    )


def write_assets(out_dir: Path, pygments_style: str = "default") -> None:
    """Copy static template assets + generated highlight CSS into out/assets/."""
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    # Append Pygments CSS to style.css so it ships as one file.
    style = _load("style.css") + "\n\n/* Syntax highlighting (Pygments) */\n" + pygments_css(pygments_style)
    (assets / "style.css").write_text(style, encoding="utf-8")
    (assets / "app.js").write_text(_load("app.js"), encoding="utf-8")
    (assets / "search.js").write_text(_load("search.js"), encoding="utf-8")
