# mdsite

A zero-config CLI that turns a folder of Markdown files into a clean, browsable
static HTML website — fully offline, no accounts, no API keys, no network calls
at build or runtime.

Point it at a folder of `.md` files and get a complete static site: sidebar nav
mirroring your folder structure, light/dark mode, client-side search, syntax
highlighting, and clean URLs.

## Features

- **Folder structure → navigation.** Nested folders become a collapsible sidebar
  tree; `index.md` / `README.md` become folder landing pages.
- **Clean URLs.** `foo/bar.md` → `/foo/bar/`. Relative `.md` links are rewritten
  automatically.
- **GitHub-flavored Markdown.** Tables, task lists, strikethrough, fenced code.
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
  -h, --help            Show help
```

### Examples

```bash
mdsite init my-site                 # scaffold sample content + config
mdsite serve my-site                # dev server with live-reload
mdsite build ./docs --out ./public --clean
mdsite build ./docs --base /docs/   # host under a subfolder
```

Open the generated `dist/index.html` directly in a browser (`file://`) or serve
the `dist/` folder from any static host.

## Front matter

Optional YAML front matter per file:

```yaml
---
title: Getting Started   # falls back to first H1, then filename
order: 1                 # sort order within its folder (default: alphabetical)
draft: false             # if true, skip in build
---
```

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

- `theme`: `"light"`, `"dark"`, or `"auto"`.
- `exclude`: glob patterns (`**`, `*`, `?`) of source paths to skip.

## Output

For each `foo/bar.md`, mdsite emits `dist/foo/bar/index.html`, plus:

- `assets/style.css` (typography, light/dark, bundled Pygments highlight CSS)
- `assets/app.js`, `assets/search.js` (theme toggle, nav, scroll-sync, search)
- `search-index.json` (flat `{title, url, text}` list for client-side search)
- `sitemap.xml`
- Non-`.md` files (images, PDFs, …) copied through verbatim.

## Development

```bash
pip install -e .
pip install pytest
pytest
```

## License

MIT
