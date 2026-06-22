"""Tests for the init scaffold command."""

from __future__ import annotations

import json

from mdsite.build import build
from mdsite.init import init


def test_init_creates_config_and_files(tmp_path):
    init(str(tmp_path))
    assert (tmp_path / "mdsite.config.json").exists()
    assert (tmp_path / "index.md").exists()
    assert (tmp_path / "getting-started.md").exists()
    assert (tmp_path / "guide" / "intro.md").exists()


def test_init_config_is_valid_json(tmp_path):
    init(str(tmp_path))
    cfg = json.loads((tmp_path / "mdsite.config.json").read_text(encoding="utf-8"))
    assert cfg["title"] == "My Site"
    assert "*.tmp.md" in cfg["exclude"]


def test_init_skips_existing(tmp_path, capsys):
    (tmp_path / "index.md").write_text("# Mine\n", encoding="utf-8")
    init(str(tmp_path))
    out = capsys.readouterr().out
    assert "skip: index.md already exists" in out
    # Existing file left untouched.
    assert (tmp_path / "index.md").read_text(encoding="utf-8") == "# Mine\n"


def test_init_output_builds(tmp_path):
    """The scaffolded site must build cleanly end-to-end."""
    src = tmp_path / "site"
    init(str(src))
    out = tmp_path / "dist"
    result = build(str(src), {"out": str(out), "clean": True})
    assert result["page_count"] == 3
    assert (out / "index.html").exists()
    assert (out / "getting-started" / "index.html").exists()
    assert (out / "guide" / "intro" / "index.html").exists()
