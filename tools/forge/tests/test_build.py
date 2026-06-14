from pathlib import Path

import pytest

from forge import backends, build, gates
from forge import task as tasks
from forge.backends import AgentResult
from forge.config import Budget, ForgeConfig, Tier
from forge.task import GateResult, Task


@pytest.fixture(autouse=True)
def isolate_state(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(tasks, "STATE_DIR", state)
    # never touch real git in these tests
    monkeypatch.setattr(build, "_commit", lambda wt, msg: None)
    monkeypatch.setattr(build, "_has_changes", lambda wt: True)


def _cfg():
    return ForgeConfig(
        ladder=[
            Tier("local", "ollama/qwen3-coder-32k", 2),
            Tier("claude", "sonnet", 1),
            Tier("claude", "opus", 1),
        ],
        gates={"test": "pytest"},
        budget=Budget(opus_per_day=4),
    )


def _task(tmp_path) -> Task:
    return Task(
        id="t-1",
        repo="demo",
        branch="forge/x",
        base="main",
        worktree=str(tmp_path),
        description="do a thing",
        status="running",
    )


def test_commits_when_local_passes_first_try(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backends, "run_agent", lambda tier, prompt, cwd: AgentResult(True, "")
    )
    monkeypatch.setattr(
        gates, "run_gates", lambda g, cwd: [GateResult("test", True, "")]
    )
    task = build.run_build(_cfg(), _task(tmp_path), Path(tmp_path))
    assert task.status == "done"
    assert len(task.attempts) == 1
    assert task.attempts[0].tier_kind == "local"


def test_escalates_local_to_sonnet_on_gate_failure(tmp_path, monkeypatch):
    calls = {"n": 0}

    def fake_gates(g, cwd):
        calls["n"] += 1
        passed = calls["n"] >= 3  # fail both local attempts, pass on sonnet
        return [GateResult("test", passed, "" if passed else "boom")]

    monkeypatch.setattr(
        backends, "run_agent", lambda tier, prompt, cwd: AgentResult(True, "")
    )
    monkeypatch.setattr(gates, "run_gates", fake_gates)
    task = build.run_build(_cfg(), _task(tmp_path), Path(tmp_path))
    assert task.status == "done"
    assert [a.model for a in task.attempts] == [
        "ollama/qwen3-coder-32k",
        "ollama/qwen3-coder-32k",
        "sonnet",
    ]


def test_needs_human_when_all_tiers_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(
        backends, "run_agent", lambda tier, prompt, cwd: AgentResult(True, "")
    )
    monkeypatch.setattr(
        gates, "run_gates", lambda g, cwd: [GateResult("test", False, "nope")]
    )
    task = build.run_build(_cfg(), _task(tmp_path), Path(tmp_path))
    assert task.status == "needs_human"
    assert len(task.attempts) == 4  # 2 local + 1 sonnet + 1 opus


def test_empty_diff_escalates(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "_has_changes", lambda wt: False)
    monkeypatch.setattr(
        backends, "run_agent", lambda tier, prompt, cwd: AgentResult(True, "")
    )
    # gates never matter because there are no changes
    task = build.run_build(_cfg(), _task(tmp_path), Path(tmp_path))
    assert task.status == "needs_human"
    assert all(a.changed is False for a in task.attempts)
