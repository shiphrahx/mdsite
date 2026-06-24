# mdsite

A zero-config CLI that turns a folder of Markdown files into a clean, browsable
static HTML website — fully offline, no accounts, no API keys, no network calls
at build or runtime.

Point it at a folder of `.md` files and get a complete static site: sidebar nav
mirroring your folder structure, light/dark mode, client-side search, syntax
highlighting, and clean URLs.

## Quick start

```bash
pip install mdsite
mdsite init my-site      # scaffold sample content + config
mdsite serve my-site     # live-reload dev server at http://127.0.0.1:3000
mdsite build my-site     # write the static site to ./dist
```

Then publish `dist/` to any static host (GitHub Pages, Netlify, S3, nginx …).

## Features

- **Folder structure → navigation.** Nested folders become a collapsible sidebar
  tree; `index.md` / `README.md` become folder landing pages.
- **Clean URLs.** `foo/bar.md` → `/foo/bar/`. Relative `.md` links (including
  `../` traversal, `?query`, and `#fragment`) are rewritten automatically.
- **GitHub-flavored Markdown.** Tables, task lists, strikethrough, fenced code,
  autolinked URLs.
- **Syntax highlighting** via Pygments, generated at build time (no client JS,
  no CDN).
- **Light / dark mode** with a toggle, persisted in `localStorage`, respecting
  `prefers-color-scheme` on first load.
- **Client-side search** over a generated `search-index.json` — instant,
  keyboard-navigable, no backend.
- **On-page table of contents** from H2/H3 headings, scroll-synced.
- **Prev / next** links based on `order` front matter.
- **Live-reload dev server** (`mdsite serve`) that rebuilds on save and honors
  `--base`.
- **Copy buttons** on every code block (Clipboard API with a fallback).
- **Tags / categories** with auto-generated `/tags/` listing pages and chips.
- **Atom feed** (`feed.xml`) built from pages that carry a `date` (blog mode).
- **Open Graph & Twitter Card** meta tags for rich social sharing.
- **Broken-link checking** — relative `.md` links that resolve to nothing are
  reported at build time.
- **404 page** generated for static hosts; **`sitemap.xml`** for SEO.
- **Last-updated dates** from git history or file mtime (opt-in).
- **Logo & favicon**, **custom CSS override**, and configurable **markdown
  extensions** (footnotes, definition lists, typography).
- **Mermaid diagrams** and **KaTeX math** — opt-in, with the libraries vendored
  locally so the offline guarantee still holds.
- **Versioned docs** — build multiple version subtrees with a header switcher.
- **Incremental builds** — opt-in render cache re-renders only changed pages.
- **Fully offline.** No network requests during build or when viewing output.

## Install

```bash
pipx install mdsite        # recommended — isolated install
# or
pip install mdsite
```

Requires Python 3.9+.

### From source

```bash
git clone <repo-url> mdsite
cd mdsite
pip install -e .
```

## Usage

```
mdsite <command> [options]

Commands:
  build <srcDir>        Build a site from a folder of .md files
  serve <srcDir>        Build, then serve locally + live-reload on file change
  init [dir]            Create a sample content folder + mdsite.config.json

Options:
  -o, --out <dir>       Output directory (default: ./dist)
  -t, --title <string>  Site title (default: from config or folder name)
  --clean               Wipe the output dir before building
  --base <path>         Base URL path for hosting in a subfolder (default: /)
  --port <n>            Preferred port for `serve` (default: 3000)
  -h, --help            Show help
```

### Examples

```bash
mdsite init my-site                 # scaffold sample content + config
mdsite serve my-site --port 8080    # dev server with live-reload
mdsite build ./docs --out ./public --clean
mdsite build ./docs --base /docs/   # host under a subfolder
```

### Viewing the output

Serve the `dist/` folder from any static host, or run `mdsite serve <srcDir>`
for local preview. Output uses clean, root-relative URLs (`/foo/bar/`), so links
resolve over HTTP but **not** when opening `dist/index.html` via `file://`. For a
quick local check without `serve`:

```bash
cd dist && python -m http.server
```

## Front matter

Optional YAML front matter per file:

```yaml
---
title: Getting Started   # falls back to first H1, then filename
order: 1                 # sort order within its folder (default: alphabetical)
draft: false             # if true, skip in build
description: Short blurb  # used for <meta>, og:description, feed summary
tags: [guide, intro]     # tag chips + /tags/ listing pages
date: 2026-06-24         # include this page in the Atom feed
image: /img/cover.png    # og:image for this page
---
```

Pages without an `order` sort alphabetically by title, after any ordered pages.
Links pointing at a `draft` page are left untouched (not rewritten), since the
draft is not emitted.

## Configuration

Optional `mdsite.config.json` at the source root:

```json
{
  "title": "My Site",
  "description": "Notes and docs",
  "theme": "auto",
  "footer": "© 2026 Me",
  "exclude": ["private/**", "*.tmp.md"],

  "logo": "logo.svg",
  "favicon": "favicon.ico",
  "custom_css": "brand.css",

  "site_url": "https://example.com",
  "og_image": "/img/share.png",
  "social_meta": true,

  "last_updated": "git",
  "error_page": true,
  "check_links": true,
  "tag_pages": true,
  "feed": true,

  "markdown": { "footnote": true, "deflist": true, "typographer": true },
  "diagrams": false,
  "math": false,
  "incremental": false,

  "versions": [
    { "label": "v2 (latest)", "dir": "v2", "default": true },
    { "label": "v1", "dir": "v1" }
  ]
}
```

Core:

- `title` — site title; the `-t/--title` flag overrides it.
- `description` — default `<meta name="description">` (front matter overrides per page).
- `theme` — `"light"`, `"dark"`, or `"auto"` (follows the OS preference).
- `footer` — rendered as raw HTML at the bottom of every page.
- `exclude` — glob patterns of source paths to skip. Supports `**` (any depth),
  `*` (within a path segment), and `?` (single character).

Branding:

- `logo` / `favicon` — paths (relative to the source) copied into `assets/` and
  wired into the header/`<head>`.
- `custom_css` — path to a CSS file appended after the bundled stylesheet, so
  your rules win without forking templates.

Social / SEO:

- `site_url` — absolute origin used to make `og:url` / `og:image` and feed links
  absolute.
- `og_image` — default social-share image (path or absolute URL).
- `social_meta` — emit Open Graph + Twitter Card tags (default `true`).

Build behavior:

- `last_updated` — `"git"` (last commit date, falling back to mtime), `"mtime"`,
  or `false` (default) to show a per-page “Last updated” date.
- `error_page` — emit `404.html` (default `true`).
- `check_links` — warn about relative `.md` links that resolve to nothing
  (default `true`).
- `tag_pages` — generate `/tags/` and `/tags/<slug>/` pages (default `true`).
- `feed` — generate an Atom `feed.xml` from pages with a `date` (default `true`).
- `incremental` — cache rendered pages and re-render only what changed
  (default `false`). The cache lives beside the output dir.

Markdown / rich content:

- `markdown` — opt into extra markdown-it features: `footnote`, `deflist`,
  `typographer` (as a dict of booleans or a list of names).
- `diagrams` — render ```` ```mermaid ```` blocks via locally-vendored Mermaid
  (default `false`).
- `math` — render `$…$` / `$$…$$` via locally-vendored KaTeX (default `false`).

Versioned docs:

- `versions` — a list of `{label, dir, default}` (or bare directory strings).
  Each `dir` is a subfolder of the source built into `/<slug>/`, with a header
  version switcher; the site root redirects to the default version.

## How it works

- **Index pages.** A folder's landing page is its `index.md`. If there is no
  `index.md`, `README.md` is used instead; if both exist, `README.md` is ignored
  with a warning.
- **Clean URLs.** `foo/bar.md` → `dist/foo/bar/index.html`, served at
  `/foo/bar/`. `index.md`/`README.md` map directly to their folder URL.
- **Subfolder hosting.** `--base /docs/` prefixes every URL and asset path.
  The value is normalized, so `docs`, `/docs`, and `/docs/` are equivalent.
- **`serve` specifics.** The dev server honors `--base` (it builds with the
  prefix and strips it from requests, bouncing `/` to the base path) and
  rebuilds with a clean output dir, so deleted or renamed pages never leave
  stale files behind. Writes into the output dir are ignored by the file
  watcher, so `mdsite serve .` won't loop.

## Output

For each `foo/bar.md`, mdsite emits `dist/foo/bar/index.html`, plus:

- `assets/style.css` (typography, light/dark, bundled Pygments highlight CSS)
- `assets/app.js`, `assets/search.js` (theme toggle, nav, scroll-sync, search,
  copy buttons, version switcher)
- `search-index.json` (`{title, url, text, headings}` list for client-side
  search, with heading-weighted ranking + match highlighting)
- `sitemap.xml`, and `404.html`
- `/tags/` listing pages and `feed.xml` when tags / dated pages are present
- `assets/vendor/…` when Mermaid or KaTeX is enabled (vendored locally)
- Non-`.md` files (images, PDFs, …) copied through verbatim.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite covers rendering, navigation, config, search, layout, the CLI,
the init scaffold, and the build/serve pipeline end to end.

## License

MIT
