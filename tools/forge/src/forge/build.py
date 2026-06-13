"""The BUILD stage loop: route -> invoke agent -> gate -> escalate or commit.

Stage-agnostic enough that PLAN/REVIEW can reuse the same engine later.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from devsesh import worktree as dw

from . import backends, config, gates, router
from .config import ForgeConfig
from .task import Attempt, Task, opus_attempts_today, save


def _has_changes(wt: Path) -> bool:
    result = dw.git(wt, "status", "--porcelain", check=False)
    return bool(result.stdout.strip())


def _commit(wt: Path, message: str) -> None:
    dw.git(wt, "add", "-A", check=False)
    dw.git(wt, "commit", "-m", message, check=False)


def _prompt(task: Task, prior: Attempt | None) -> str:
    text = (
        "You are implementing a change in this repository. Make the code edits "
        "directly in the working tree.\n\n"
        f"## Task\n{task.description}\n"
    )
    if prior is None:
        return text
    if not prior.changed:
        return text + (
            "\nA previous attempt made no changes. Implement the task concretely "
            "by editing files."
        )
    summary = gates.failures_summary(prior.gates)
    if summary:
        text += (
            "\nA previous attempt failed the following checks. Keep the working "
            f"changes and fix them:\n\n{summary}"
        )
    return text


def run_build(
    fcfg: ForgeConfig,
    task: Task,
    repo_path: Path,
    on_tier: Callable[[object], None] | None = None,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> Task:
    """Run the escalating build loop until gates pass or the ladder is exhausted."""
    wt = Path(task.worktree)
    gate_cfg = config.repo_gates(repo_path, fcfg)

    while True:
        tier = router.next_tier(
            fcfg.ladder,
            task.attempts,
            opus_attempts_today(),
            fcfg.budget.opus_per_day,
        )
        if tier is None:
            task.status = "needs_human"
            save(task)
            return task
        if on_tier:
            on_tier(tier)

        prior = task.attempts[-1] if task.attempts else None
        result = backends.run_agent(tier, _prompt(task, prior), wt)

        changed = _has_changes(wt)
        gate_results = gates.run_gates(gate_cfg, wt) if changed else []
        attempt = Attempt(
            tier_kind=tier.kind,
            model=tier.model,
            agent_ok=result.agent_ok,
            changed=changed,
            gates=gate_results,
        )
        task.attempts.append(attempt)
        save(task)
        if on_attempt:
            on_attempt(attempt)

        if attempt.passed:
            _commit(wt, f"forge: {task.description}")
            task.status = "done"
            save(task)
            return task
