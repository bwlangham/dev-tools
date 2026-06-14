from pathlib import Path

import pytest

from forge import build, gates, pipeline, pr, review
from forge import task as tasks
from forge.backends import AgentResult
from forge.config import ForgeConfig, Review
from forge.task import GateResult, ReviewResult, Task


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(tasks, "STATE_DIR", state)
    monkeypatch.setattr(build, "_commit", lambda wt, msg: None)
    monkeypatch.setattr(build, "_has_changes", lambda wt: True)
    # never touch a real remote
    monkeypatch.setattr(pr, "push", lambda repo, branch: None)
    monkeypatch.setattr(pr, "open_pr", lambda repo, task: "https://example/pr/1")


def _cfg(max_rounds: int = 2) -> ForgeConfig:
    return ForgeConfig(
        gates={"test": "pytest"}, review=Review(model="sonnet", max_rounds=max_rounds)
    )


def _task(tmp_path) -> Task:
    return Task(
        id="t-1",
        repo="demo",
        branch="forge/x",
        base="main",
        worktree=str(tmp_path),
        description="do a thing",
        status="done",
    )


def test_approve_first_round_opens_pr(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", True, "ok")
    )
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert len(task.reviews) == 1
    assert task.pr_url == "https://example/pr/1"
    assert task.attempts == []  # no fix needed


def test_request_then_approve_records_fix(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_review(m, t, r):
        calls["n"] += 1
        return ReviewResult("sonnet", calls["n"] >= 2, "fix it")

    monkeypatch.setattr(review, "run_review", fake_review)
    monkeypatch.setattr(
        pipeline.backends, "run_agent", lambda tier, p, cwd: AgentResult(True, "")
    )
    monkeypatch.setattr(
        gates, "run_gates", lambda g, cwd: [GateResult("test", True, "")]
    )
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert len(task.reviews) == 2
    assert len(task.attempts) == 1  # one fix attempt
    assert task.pr_url == "https://example/pr/1"


def test_max_rounds_exhausted_still_opens_pr(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", False, "nope")
    )
    monkeypatch.setattr(
        pipeline.backends, "run_agent", lambda tier, p, cwd: AgentResult(True, "")
    )
    monkeypatch.setattr(
        gates, "run_gates", lambda g, cwd: [GateResult("test", True, "")]
    )
    task = pipeline.run_review_and_pr(
        _cfg(max_rounds=2), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert len(task.reviews) == 2
    assert task.pr_url == "https://example/pr/1"


def test_no_pr_when_do_pr_false(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", True, "ok")
    )
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=False
    )
    assert task.pr_url is None
