from pathlib import Path

from forge import backends, review
from forge.backends import AgentResult
from forge.task import Task


def _task() -> Task:
    return Task(
        id="t-1",
        repo="demo",
        branch="forge/x",
        base="main",
        worktree="/tmp/wt",
        description="do a thing",
        status="done",
    )


def _stub(monkeypatch, output: str, agent_ok: bool = True) -> None:
    monkeypatch.setattr(review, "_diff", lambda repo, base, branch: "diff")
    monkeypatch.setattr(
        backends,
        "run_claude_readonly",
        lambda model, prompt, cwd: AgentResult(agent_ok, output),
    )


def test_approve_verdict(monkeypatch):
    _stub(monkeypatch, "looks good\nVERDICT: APPROVE")
    result = review.run_review("sonnet", _task(), Path("/repo"))
    assert result.approved
    assert result.model == "sonnet"


def test_request_changes_verdict(monkeypatch):
    _stub(monkeypatch, "bug here\nVERDICT: REQUEST_CHANGES fix the bug")
    result = review.run_review("sonnet", _task(), Path("/repo"))
    assert not result.approved


def test_missing_verdict_defaults_to_request(monkeypatch):
    _stub(monkeypatch, "some prose with no verdict line")
    result = review.run_review("sonnet", _task(), Path("/repo"))
    assert not result.approved


def test_last_verdict_wins(monkeypatch):
    _stub(monkeypatch, "VERDICT: REQUEST_CHANGES\nactually\nVERDICT: APPROVE")
    result = review.run_review("sonnet", _task(), Path("/repo"))
    assert result.approved


def test_agent_failure_is_not_approved(monkeypatch):
    _stub(monkeypatch, "VERDICT: APPROVE", agent_ok=False)
    result = review.run_review("sonnet", _task(), Path("/repo"))
    assert not result.approved
