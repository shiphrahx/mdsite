"""Tests for last-updated date resolution (git + mtime)."""

from __future__ import annotations

import os
import re
import subprocess

import pytest

from mdsite import lastmod
from mdsite.lastmod import last_updated, reset_git_cache

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_git_cache()
    yield
    reset_git_cache()


def test_disabled_returns_none(tmp_path):
    (tmp_path / "a.md").write_text("# A\n", encoding="utf-8")
    assert last_updated(tmp_path, "a.md", None) is None
    assert last_updated(tmp_path, "a.md", False) is None
    assert last_updated(tmp_path, "a.md", "") is None


def test_mtime_mode(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# A\n", encoding="utf-8")
    # Pin mtime to a known date (2021-01-02 12:00 UTC).
    ts = 1609588800
    os.utime(f, (ts, ts))
    assert last_updated(tmp_path, "a.md", "mtime") == "2021-01-02"


def test_mtime_missing_file(tmp_path):
    assert last_updated(tmp_path, "ghost.md", "mtime") is None


def test_git_mode_falls_back_to_mtime_outside_repo(tmp_path):
    f = tmp_path / "a.md"
    f.write_text("# A\n", encoding="utf-8")
    ts = 1609588800
    os.utime(f, (ts, ts))
    # tmp_path is not a git repo -> git mode falls back to mtime.
    assert last_updated(tmp_path, "a.md", "git") == "2021-01-02"


def _git(repo, *args, env=None):
    subprocess.run(["git", "-C", str(repo), *args], check=True,
                   capture_output=True, text=True, env=env)


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not available",
)
def test_git_mode_uses_commit_date(tmp_path):
    repo = tmp_path
    _git(repo, "init")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    f = repo / "a.md"
    f.write_text("# A\n", encoding="utf-8")
    _git(repo, "add", "a.md")
    # Commit with a fixed date.
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2020-05-06T10:00:00"
    env["GIT_COMMITTER_DATE"] = "2020-05-06T10:00:00"
    _git(repo, "commit", "-m", "add", env=env)
    assert last_updated(repo, "a.md", "git") == "2020-05-06"


@pytest.mark.skipif(
    subprocess.run(["git", "--version"], capture_output=True).returncode != 0,
    reason="git not available",
)
def test_git_mode_untracked_falls_back_to_mtime(tmp_path):
    repo = tmp_path
    _git(repo, "init")
    f = repo / "a.md"
    f.write_text("# A\n", encoding="utf-8")
    ts = 1609588800
    os.utime(f, (ts, ts))
    # File exists but is untracked -> git returns nothing -> mtime fallback.
    assert last_updated(repo, "a.md", "git") == "2021-01-02"
