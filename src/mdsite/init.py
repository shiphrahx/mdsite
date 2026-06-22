"""init command: scaffold a sample content folder + mdsite.config.json."""

from __future__ import annotations

import json
from pathlib import Path

_CONFIG = {
    "title": "My Site",
    "description": "Notes and docs built with mdsite",
    "theme": "auto",
    "footer": "© 2026 Me",
    "exclude": ["*.tmp.md"],
}

_INDEX = """\
---
title: Home
order: 1
---

# Welcome

This is your new **mdsite** site. Edit the Markdown files in this folder
and rebuild to see changes.

## Quick start

```bash
mdsite build .          # build to ./dist
mdsite serve .          # live-reload dev server
```

See [Getting Started](./getting-started.md) and the [guide](./guide/intro.md).
"""

_GETTING_STARTED = """\
---
title: Getting Started
order: 2
---

# Getting Started

1. Write Markdown files in this folder.
2. Use front matter for `title`, `order`, and `draft`.
3. Run `mdsite build .`

## Tasks

- [x] Install mdsite
- [ ] Write your first page
- [ ] Publish the `dist/` folder anywhere
"""

_GUIDE_INTRO = """\
---
title: Guide
---

# Guide

Folders become navigation sections. This page lives at `guide/intro.md`
and is served at `/guide/intro/`.

| Feature      | Supported |
| ------------ | --------- |
| Tables       | Yes       |
| Task lists   | Yes       |
| ~~Strike~~   | Yes       |
| Code blocks  | Yes       |
"""

_FILES = {
    "index.md": _INDEX,
    "getting-started.md": _GETTING_STARTED,
    "guide/intro.md": _GUIDE_INTRO,
}


def init(target: str = ".") -> None:
    root = Path(target).resolve()
    root.mkdir(parents=True, exist_ok=True)

    config_path = root / "mdsite.config.json"
    if config_path.exists():
        print(f"skip: {config_path.name} already exists")
    else:
        config_path.write_text(
            json.dumps(_CONFIG, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"created {config_path.relative_to(Path.cwd()) if config_path.is_relative_to(Path.cwd()) else config_path}")

    created = 0
    for rel, content in _FILES.items():
        path = root / rel
        if path.exists():
            print(f"skip: {rel} already exists")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created += 1

    print(f"Initialized site in {root} ({created} file(s) created).")
    print(f"Next: mdsite serve {target}")
