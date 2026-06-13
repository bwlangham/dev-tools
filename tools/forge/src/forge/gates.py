"""Deterministic gates — run configured commands in the worktree.

Gates are the objective signal that makes a weak local model viable as the
default: the agent's work is judged on lint/typecheck/test results, not vibes.
A failing gate escalates the task; its output is fed back into the next attempt.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .task import GateResult

OUTPUT_LIMIT = 4000  # chars of tail kept per gate, to bound prompt/state size


def _tail(text: str) -> str:
    text = text.strip()
    return text if len(text) <= OUTPUT_LIMIT else text[-OUTPUT_LIMIT:]


def run_gates(gates: dict[str, str], cwd: Path) -> list[GateResult]:
    """Run each gate command in ``cwd``; a non-zero exit is a failure."""
    results = []
    for name, command in gates.items():
        proc = subprocess.run(
            command, shell=True, cwd=cwd, capture_output=True, text=True
        )
        results.append(
            GateResult(
                name=name,
                passed=proc.returncode == 0,
                output=_tail(proc.stdout + proc.stderr),
            )
        )
    return results


def failures_summary(results: list[GateResult]) -> str:
    """Human/agent-readable summary of failing gates for retry context."""
    failed = [g for g in results if not g.passed]
    if not failed:
        return ""
    parts = []
    for g in failed:
        parts.append(f"### gate `{g.name}` failed\n```\n{g.output}\n```")
    return "\n\n".join(parts)
