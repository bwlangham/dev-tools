"""The REVIEW stage: a strong model critiques the gate-green diff.

Runs only after the build's deterministic gates pass. The model returns a
machine-parseable verdict; a REQUEST_CHANGES verdict feeds its findings back into
a fix attempt (see ``pipeline``). A missing/garbled verdict is treated as
REQUEST_CHANGES so a malformed response never green-lights a PR.
"""

from __future__ import annotations

import re
from pathlib import Path

from devsesh import worktree as dw

from . import backends
from .task import ReviewResult, Task

_VERDICT_RE = re.compile(r"^\s*VERDICT:\s*(APPROVE|REQUEST_CHANGES)\b", re.IGNORECASE)


def _diff(repo_path: Path, base: str, branch: str) -> str:
    result = dw.git(repo_path, "diff", f"{base}...{branch}", check=False)
    return result.stdout


def _parse_verdict(output: str) -> bool:
    """True only if the last verdict line says APPROVE; default False."""
    approved = False
    for line in output.splitlines():
        m = _VERDICT_RE.match(line)
        if m:
            approved = m.group(1).upper() == "APPROVE"
    return approved


def _prompt(task: Task, diff: str) -> str:
    return (
        "You are reviewing a code change for correctness and completeness. Do not "
        "edit any files; only analyze.\n\n"
        f"## Task the change should implement\n{task.description}\n\n"
        "## Diff under review\n"
        f"```diff\n{diff}\n```\n\n"
        "Review for correctness bugs, missed requirements, and obvious quality "
        "problems. List concrete findings. End your response with exactly one line:\n"
        "`VERDICT: APPROVE` if the change is correct and complete, or\n"
        "`VERDICT: REQUEST_CHANGES` followed by what must be fixed."
    )


def fix_prompt(findings: str) -> str:
    return (
        "A review of your change requested fixes. Keep the existing working changes "
        "and address the findings below by editing files directly.\n\n"
        f"## Review findings\n{findings}"
    )


def run_review(model: str, task: Task, repo_path: Path) -> ReviewResult:
    diff = _diff(repo_path, task.base, task.branch)
    result = backends.run_claude_readonly(model, _prompt(task, diff), repo_path)
    approved = result.agent_ok and _parse_verdict(result.output)
    return ReviewResult(model=model, approved=approved, findings=result.output)
