"""Post-build orchestration: review (with auto-fix) then push + open a PR.

Runs after ``build.run_build`` has produced a gate-green local commit. The review
itself uses a fixed strong ``claude`` model, so every PR gets at least one
strong-model look. Fixes it requests, however, go back through the *same* build
engine — fresh from the free local tier and escalating only on failure — so the
cost model is preserved for the fix work too.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from . import build, pr, review
from .config import ForgeConfig
from .task import Attempt, ReviewResult, Task, save


def run_review_and_pr(
    fcfg: ForgeConfig,
    task: Task,
    repo_path: Path,
    do_pr: bool,
    on_review: Callable[[ReviewResult], None] | None = None,
    on_tier: Callable[[object], None] | None = None,
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

        # Address findings through the build ladder, free tier first.
        task = build.run_build(
            fcfg,
            task,
            repo_path,
            on_tier=on_tier,
            on_attempt=on_attempt,
            extra_context=review.fix_context(result.findings),
            reset_routing=True,
            commit_message=f"forge: address review for {task.description}",
        )
        if task.status != "done":
            # The fix ladder was exhausted with gates still failing — don't open a
            # PR on broken code; leave the worktree for a human.
            return task

    if do_pr:
        pr.push(repo_path, task.branch)
        # If we exhausted review rounds without approval, open as a draft PR
        task.pr_url = pr.open_pr(repo_path, task, draft=task.status == "needs_human")
        save(task)
    return task
