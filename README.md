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
- **Live-reload dev server** (`mdsite serve`) that rebuilds on save.
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
  "exclude": ["private/**", "*.tmp.md"]
}
```

- `title` — site title; the `-t/--title` flag overrides it.
- `description` — used in the page `<meta name="description">`.
- `theme` — `"light"`, `"dark"`, or `"auto"` (follows the OS preference).
- `footer` — rendered as raw HTML at the bottom of every page.
- `exclude` — glob patterns of source paths to skip. Supports `**` (any depth),
  `*` (within a path segment), and `?` (single character).

## How it works

- **Index pages.** A folder's landing page is its `index.md`. If there is no
  `index.md`, `README.md` is used instead; if both exist, `README.md` is ignored
  with a warning.
- **Clean URLs.** `foo/bar.md` → `dist/foo/bar/index.html`, served at
  `/foo/bar/`. `index.md`/`README.md` map directly to their folder URL.
- **Subfolder hosting.** `--base /docs/` prefixes every URL and asset path.
  The value is normalized, so `docs`, `/docs`, and `/docs/` are equivalent.
- **`serve` specifics.** The dev server always roots the site at `/` (any
  `--base` is ignored) and rebuilds with a clean output dir, so deleted or
  renamed pages never leave stale files behind. Writes into the output dir are
  ignored by the file watcher, so `mdsite serve .` won't loop.

## Output

For each `foo/bar.md`, mdsite emits `dist/foo/bar/index.html`, plus:

- `assets/style.css` (typography, light/dark, bundled Pygments highlight CSS)
- `assets/app.js`, `assets/search.js` (theme toggle, nav, scroll-sync, search)
- `search-index.json` (flat `{title, url, text}` list for client-side search)
- `sitemap.xml`
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
