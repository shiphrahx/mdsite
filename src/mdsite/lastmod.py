"""Resolve a page's 'last updated' date from git history or file mtime."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Cache git availability per source root so we run `git` at most once to probe.
_git_repo_cache: dict[str, bool] = {}


def _is_git_repo(src: Path) -> bool:
    key = str(src)
    if key not in _git_repo_cache:
        try:
            r = subprocess.run(
                ["git", "-C", str(src), "rev-parse", "--is-inside-work-tree"],
                capture_output=True, text=True, timeout=5,
            )
            _git_repo_cache[key] = r.returncode == 0 and r.stdout.strip() == "true"
        except (OSError, subprocess.SubprocessError):
            _git_repo_cache[key] = False
    return _git_repo_cache[key]


def _git_date(src: Path, rel: str) -> str | None:
    """Last committer date (YYYY-MM-DD) for a file, or None if untracked."""
    try:
        r = subprocess.run(
            ["git", "-C", str(src), "log", "-1", "--format=%cs", "--", rel],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = r.stdout.strip()
    return out or None


def _mtime_date(src: Path, rel: str) -> str | None:
    try:
        ts = (src / rel).stat().st_mtime
    except OSError:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def last_updated(src: Path, rel: str, mode) -> str | None:
    """Return a YYYY-MM-DD date string for `rel`, or None when disabled/unknown.

    mode: falsy -> disabled; "mtime" -> file modification time;
    "git" -> last git commit date, falling back to mtime when untracked or
    when the source is not a git repo. Any other truthy value is treated as
    "git" for convenience (e.g. `true` in config)."""
    if not mode:
        return None
    if mode == "mtime":
        return _mtime_date(src, rel)
    # "git" (or any other truthy value): prefer git, fall back to mtime.
    if _is_git_repo(src):
        date = _git_date(src, rel)
        if date:
            return date
    return _mtime_date(src, rel)


def reset_git_cache() -> None:
    """Clear the git-repo probe cache (used by tests)."""
    _git_repo_cache.clear()
