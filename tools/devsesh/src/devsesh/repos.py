"""Discover git repositories under the dev root."""

from __future__ import annotations

from pathlib import Path

from .config import Config


def list_repos(cfg: Config) -> list[str]:
    """Return names of git repos directly under dev_root (sorted)."""
    root = cfg.dev_root
    if not root.is_dir():
        return []
    names = []
    for child in root.iterdir():
        if child.name.startswith("."):
            continue
        if not child.is_dir():
            continue
        if (child / ".git").exists():
            names.append(child.name)
    return sorted(names)


def resolve(cfg: Config, repo: str) -> Path:
    """Resolve a repo name to its path, raising if it isn't a git repo."""
    path = cfg.dev_root / repo
    if not (path / ".git").exists():
        raise ValueError(f"{repo!r} is not a git repo under {cfg.dev_root}")
    return path
