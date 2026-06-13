"""Session state and tmux orchestration."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from . import worktree
from .config import STATE_DIR, Config


@dataclass
class Session:
    name: str
    repo: str
    branch: str
    worktree: str
    tool: str
    base: str
    created_at: float
    tmux_session: str

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


# --- state persistence ------------------------------------------------------


def _state_file(name: str) -> Path:
    return STATE_DIR / f"{name}.json"


def save(session: Session) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(session.name).write_text(json.dumps(asdict(session), indent=2))


def load(name: str) -> Session | None:
    path = _state_file(name)
    if not path.exists():
        return None
    return Session(**json.loads(path.read_text()))


def list_all() -> list[Session]:
    if not STATE_DIR.is_dir():
        return []
    sessions = [
        Session(**json.loads(f.read_text())) for f in sorted(STATE_DIR.glob("*.json"))
    ]
    return sorted(sessions, key=lambda s: s.created_at, reverse=True)


def delete_state(name: str) -> None:
    _state_file(name).unlink(missing_ok=True)


# --- tmux -------------------------------------------------------------------


def tmux_available() -> bool:
    return subprocess.run(["tmux", "-V"], capture_output=True).returncode == 0


def tmux_alive(name: str) -> bool:
    return (
        subprocess.run(
            ["tmux", "has-session", "-t", f"={name}"], capture_output=True
        ).returncode
        == 0
    )


def tmux_new(name: str, cwd: Path, command: str) -> None:
    # Run through a shell so configured commands with args/flags work, and
    # drop to an interactive shell when the agent exits (session stays usable).
    shell = os.environ.get("SHELL", "/bin/sh")
    wrapped = f"{command}; exec {shlex.quote(shell)}"
    subprocess.run(
        ["tmux", "new-session", "-d", "-s", name, "-c", str(cwd), "sh", "-c", wrapped],
        check=True,
    )


def tmux_kill(name: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", f"={name}"], capture_output=True)


def tmux_attach(name: str) -> None:
    """Attach in the foreground (replaces the current process)."""
    os.execvp("tmux", ["tmux", "attach-session", "-t", f"={name}"])


# --- agent command building -------------------------------------------------


def auto_branch(cfg: Config, prompt: str | None) -> str:
    """Generate a branch name from a prompt slug, or a timestamp."""
    if prompt:
        slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40]
        if slug:
            return f"{cfg.branch_prefix}/{slug}"
    return f"{cfg.branch_prefix}/{int(time.time())}"


def build_command(cfg: Config, tool: str, prompt: str | None) -> str:
    base = cfg.tools.get(tool)
    if base is None:
        raise ValueError(f"unknown tool {tool!r}; configured: {', '.join(cfg.tools)}")
    if prompt:
        return f"{base} {shlex.quote(prompt)}"
    return base


# --- high-level create ------------------------------------------------------


def create_session(
    cfg: Config,
    repo_path: Path,
    repo_name: str,
    branch: str,
    tool: str,
    base: str,
    prompt: str | None,
) -> Session:
    """Create the worktree, launch a detached tmux session, persist state."""
    wt = worktree.create(repo_path, cfg.worktrees_root, repo_name, branch, base)
    name = f"{repo_name}-{worktree.sanitize(branch)}"
    command = build_command(cfg, tool, prompt)
    tmux_new(name, wt, command)
    session = Session(
        name=name,
        repo=repo_name,
        branch=branch,
        worktree=str(wt),
        tool=tool,
        base=base,
        created_at=time.time(),
        tmux_session=name,
    )
    save(session)
    return session
