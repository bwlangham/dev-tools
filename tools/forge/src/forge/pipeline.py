"""Post-build orchestration: review (with auto-fix) then push + open a PR.

Runs after ``build.run_build`` has produced a gate-green local commit. The review
model is a fixed strong ``claude`` tier, so every PR gets at least one strong-model
look — but only after the cheap build loop has done the basic cleanup.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import backends, build, config, gates, pr, review
from .config import ForgeConfig, Tier
from .task import Attempt, ReviewResult, Task, save


def _apply_fix(
    fcfg: ForgeConfig, task: Task, repo_path: Path, findings: str
) -> Attempt:
    """Let the review model address findings, then re-run gates and commit."""
    wt = Path(task.worktree)
    tier = Tier(kind="claude", model=fcfg.review.model)
    result = backends.run_agent(tier, review.fix_prompt(findings), wt)

    changed = build._has_changes(wt)
    gate_cfg = config.repo_gates(repo_path, fcfg)
    gate_results = gates.run_gates(gate_cfg, wt) if changed else []
    attempt = Attempt(
        tier_kind=tier.kind,
        model=tier.model,
        agent_ok=result.agent_ok,
        changed=changed,
        gates=gate_results,
    )
    task.attempts.append(attempt)
    if changed:
        build._commit(wt, f"forge: address review for {task.description}")
    save(task)
    return attempt


def run_review_and_pr(
    fcfg: ForgeConfig,
    task: Task,
    repo_path: Path,
    do_pr: bool,
    on_review: Callable[[ReviewResult], None] | None = None,
    on_attempt: Callable[[Attempt], None] | None = None,
) -> Task:
    """Review the built change, auto-fix on request, then optionally open a PR."""
    for _ in range(max(1, fcfg.review.max_rounds)):
        result = review.run_review(fcfg.review.model, task, repo_path)
        task.reviews.append(result)
        save(task)
        if on_review:
            on_review(result)
        if result.approved:
            break
        attempt = _apply_fix(fcfg, task, repo_path, result.findings)
        if on_attempt:
            on_attempt(attempt)

    if do_pr:
        pr.push(repo_path, task.branch)
        task.pr_url = pr.open_pr(repo_path, task)
        save(task)
    return task
