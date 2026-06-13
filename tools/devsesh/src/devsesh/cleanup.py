"""Classify and prune stale sessions."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import session as sess
from . import worktree
from .config import Config
from .session import Session


@dataclass
class Candidate:
    session: Session
    reasons: list[str]


def parse_duration(text: str) -> float:
    """Parse durations like '7d', '12h', '30m' into seconds."""
    match = re.fullmatch(r"(\d+)\s*([smhdw])", text.strip())
    if not match:
        raise ValueError(f"invalid duration {text!r} (use e.g. 30m, 12h, 7d, 2w)")
    value, unit = int(match.group(1)), match.group(2)
    return value * {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]


def classify(
    cfg: Config,
    *,
    older_than: float | None,
    merged: bool,
    dead: bool,
) -> list[Candidate]:
    """Return sessions matching any of the selected criteria."""
    candidates: list[Candidate] = []
    for session in sess.list_all():
        reasons: list[str] = []
        alive = sess.tmux_alive(session.tmux_session)

        if dead and not alive:
            reasons.append("tmux dead")
        if older_than is not None and session.age_seconds > older_than:
            reasons.append("old")
        if merged:
            repo_path = cfg.dev_root / session.repo
            if (repo_path / ".git").exists() and worktree.is_merged(
                repo_path, session.branch, session.base
            ):
                reasons.append("merged")

        if reasons:
            candidates.append(Candidate(session=session, reasons=reasons))
    return candidates


def remove(cfg: Config, session: Session, keep_branch: bool = True) -> None:
    """Tear down a single session: kill tmux, remove worktree, drop state."""
    sess.tmux_kill(session.tmux_session)
    repo_path = cfg.dev_root / session.repo
    if (repo_path / ".git").exists():
        worktree.remove(repo_path, Path(session.worktree), session.branch, keep_branch)
    sess.delete_state(session.name)
