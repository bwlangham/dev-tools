import subprocess
from pathlib import Path

from forge import pr
from forge.task import Attempt, ReviewResult, Task


def _task() -> Task:
    return Task(
        id="t-1",
        repo="demo",
        branch="forge/x",
        base="main",
        worktree="/tmp/wt",
        description="add a feature",
        status="done",
        attempts=[Attempt("local", "qwen", True, True, [])],
        reviews=[ReviewResult("sonnet", True, "all good")],
    )


def _fake_git(monkeypatch, stdout: str) -> None:
    monkeypatch.setattr(
        pr.dw,
        "git",
        lambda repo, *a, **k: subprocess.CompletedProcess(a, 0, stdout, ""),
    )


def test_body_includes_summary_review_and_footer(monkeypatch):
    _fake_git(monkeypatch, " file.py | 2 +-")
    body = pr._body(Path("/repo"), _task())
    assert "add a feature" in body
    assert "local:qwen" in body
    assert "review (sonnet): approved" in body
    assert "all good" in body
    assert "file.py | 2 +-" in body
    assert body.rstrip().endswith("Claude Code](https://claude.com/claude-code)")


def test_open_pr_returns_new_url(monkeypatch):
    _fake_git(monkeypatch, "")
    monkeypatch.setattr(pr, "_existing_url", lambda repo, branch: None)

    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "pr", "create"]
        return subprocess.CompletedProcess(cmd, 0, "https://example/pr/9\n", "")

    monkeypatch.setattr(pr.subprocess, "run", fake_run)
    assert pr.open_pr(Path("/repo"), _task()) == "https://example/pr/9"


def test_open_pr_idempotent_returns_existing(monkeypatch):
    monkeypatch.setattr(
        pr, "_existing_url", lambda repo, branch: "https://example/pr/1"
    )

    def fail(*a, **k):  # gh pr create must not run
        raise AssertionError("create should not be called")

    monkeypatch.setattr(pr.subprocess, "run", fail)
    assert pr.open_pr(Path("/repo"), _task()) == "https://example/pr/1"


def test_open_pr_raises_on_failure(monkeypatch):
    _fake_git(monkeypatch, "")
    monkeypatch.setattr(pr, "_existing_url", lambda repo, branch: None)
    monkeypatch.setattr(
        pr.subprocess,
        "run",
        lambda cmd, **k: subprocess.CompletedProcess(cmd, 1, "", "boom"),
    )
    try:
        pr.open_pr(Path("/repo"), _task())
    except RuntimeError as exc:
        assert "boom" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
