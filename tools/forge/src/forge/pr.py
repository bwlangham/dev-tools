"""The PR stage: push the branch and open a pull request via ``gh``.

Only reached under an explicit ``--pr`` flag / ``forge pr`` command — that flag is
the authorization to act outside the local repo. ``open_pr`` is idempotent: if a PR
already exists for the branch it returns that PR's URL instead of failing.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from devsesh import worktree as dw

from .task import Task

_FOOTER = "🤖 Generated with [Claude Code](https://claude.com/claude-code)"


def push(repo_path: Path, branch: str) -> None:
    dw.git(repo_path, "push", "-u", "origin", branch, check=False)


def _body(repo_path: Path, task: Task) -> str:
    diffstat = dw.git(
        repo_path, "diff", "--stat", f"{task.base}...{task.branch}", check=False
    ).stdout.strip()

    tiers = ", ".join(f"{a.tier_kind}:{a.model}" for a in task.attempts) or "(none)"
    lines = [
        task.description,
        "",
        "## forge",
        f"- attempts: {len(task.attempts)} ({tiers})",
    ]
    if task.reviews:
        last = task.reviews[-1]
        verdict = "approved" if last.approved else "requested changes"
        lines += [
            f"- review ({last.model}): {verdict}",
            "",
            "## Review",
            last.findings.strip() or "(no findings)",
        ]
    if diffstat:
        lines += ["", "## Diffstat", "```", diffstat, "```"]
    lines += ["", _FOOTER]
    return "\n".join(lines)


def _existing_url(repo_path: Path, branch: str) -> str | None:
    proc = subprocess.run(
        ["gh", "pr", "view", branch, "--json", "url", "--jq", ".url"],
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    url = proc.stdout.strip()
    return url if proc.returncode == 0 and url else None


def open_pr(repo_path: Path, task: Task, draft: bool = False) -> str:
    """Create a PR for the task's branch, or return the existing PR's URL."""
    existing = _existing_url(repo_path, task.branch)
    if existing:
        return existing
    cmd = [
        "gh",
        "pr",
        "create",
        "--base",
        task.base,
        "--head",
        task.branch,
        "--title",
        task.description,
        "--body",
        _body(repo_path, task),
    ]
    if draft:
        cmd.append("--draft")
    proc = subprocess.run(
        cmd,
        cwd=repo_path,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gh pr create failed: {proc.stderr.strip()}")
    return proc.stdout.strip()
