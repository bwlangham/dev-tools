"""Git worktree creation, removal, and base-branch detection."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def sanitize(branch: str) -> str:
    """Turn a branch name into a filesystem/tmux-safe token."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-")


def _ref_exists(repo: Path, ref: str) -> bool:
    return (
        git(repo, "rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0
    )


def detect_base(repo: Path, preferred: str) -> str:
    """Pick the base branch: preferred if it exists, else master/main, else HEAD."""
    for candidate in (preferred, "main", "master"):
        if _ref_exists(repo, candidate) or _ref_exists(repo, f"origin/{candidate}"):
            return candidate
    return "HEAD"


def branch_exists(repo: Path, branch: str) -> bool:
    return _ref_exists(repo, f"refs/heads/{branch}")


def worktree_path(worktrees_root: Path, repo_name: str, branch: str) -> Path:
    return worktrees_root / repo_name / sanitize(branch)


def create(
    repo: Path,
    worktrees_root: Path,
    repo_name: str,
    branch: str,
    base: str,
    fetch: bool = True,
) -> Path:
    """Create (or reuse) a worktree for ``branch`` based on ``base``.

    Idempotent: if the worktree path already exists it is returned unchanged.
    """
    path = worktree_path(worktrees_root, repo_name, branch)
    if path.exists():
        return path

    path.parent.mkdir(parents=True, exist_ok=True)
    if fetch:
        git(repo, "fetch", "origin", base, check=False)

    if branch_exists(repo, branch):
        git(repo, "worktree", "add", str(path), branch)
    else:
        git(repo, "worktree", "add", "-b", branch, str(path), base)
    return path


def remove(repo: Path, path: Path, branch: str, keep_branch: bool = True) -> None:
    """Remove a worktree and prune; optionally delete the branch."""
    git(repo, "worktree", "remove", "--force", str(path), check=False)
    git(repo, "worktree", "prune", check=False)
    if not keep_branch and branch_exists(repo, branch):
        git(repo, "branch", "-D", branch, check=False)


def is_merged(repo: Path, branch: str, base: str) -> bool:
    """True if ``branch`` is fully merged into ``base``."""
    result = git(repo, "branch", "--merged", base, check=False)
    if result.returncode != 0:
        return False
    merged = {line.lstrip("+* ").strip() for line in result.stdout.splitlines()}
    return branch in merged
