from pathlib import Path

import pytest

from forge import pipeline, pr, review
from forge import task as tasks
from forge.config import ForgeConfig, Review
from forge.task import Attempt, GateResult, ReviewResult, Task


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(tasks, "STATE_DIR", state)
    # never touch a real remote
    monkeypatch.setattr(pr, "push", lambda repo, branch: None)
    monkeypatch.setattr(
        pr, "open_pr", lambda repo, task, draft=False: "https://example/pr/1"
    )


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


def _fake_build(status: str = "done"):
    """Simulate a fix run: record an attempt and set the resulting status.

    Asserts the fix is routed free-first (reset_routing) with findings as context.
    """

    def run(fcfg, task, repo_path, **kwargs):
        assert kwargs.get("reset_routing") is True
        assert kwargs.get("extra_context")
        task.attempts.append(
            Attempt("local", "qwen", True, True, [GateResult("test", True, "")])
        )
        task.status = status
        return task

    return run


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


def test_request_then_approve_runs_fix_ladder(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_review(m, t, r):
        calls["n"] += 1
        return ReviewResult("sonnet", calls["n"] >= 2, "fix it")

    monkeypatch.setattr(review, "run_review", fake_review)
    monkeypatch.setattr(pipeline.build, "run_build", _fake_build("done"))
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert len(task.reviews) == 2
    assert len(task.attempts) == 1  # one fix run recorded an attempt
    assert task.pr_url == "https://example/pr/1"


def test_max_rounds_exhausted_still_opens_pr(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", False, "nope")
    )
    monkeypatch.setattr(pipeline.build, "run_build", _fake_build("done"))
    task = pipeline.run_review_and_pr(
        _cfg(max_rounds=2), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert len(task.reviews) == 2
    assert len(task.attempts) == 2  # one fix per round
    assert task.pr_url == "https://example/pr/1"


def test_fix_ladder_exhausted_blocks_pr(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", False, "nope")
    )
    monkeypatch.setattr(pipeline.build, "run_build", _fake_build("needs_human"))
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=True
    )
    assert task.status == "needs_human"
    assert task.pr_url is None


def test_no_pr_when_do_pr_false(tmp_path, monkeypatch):
    monkeypatch.setattr(
        review, "run_review", lambda m, t, r: ReviewResult("sonnet", True, "ok")
    )
    task = pipeline.run_review_and_pr(
        _cfg(), _task(tmp_path), Path(tmp_path), do_pr=False
    )
    assert task.pr_url is None
