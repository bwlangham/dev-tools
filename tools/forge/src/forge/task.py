"""Task state, attempt history, and JSON persistence under STATE_DIR."""

from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

from .config import STATE_DIR

# Task lifecycle:
#   running     -> build loop in progress
#   done        -> all gates green, changes committed
#   needs_human -> escalation ladder exhausted, worktree left intact
STATUSES = ("running", "done", "needs_human")


@dataclass
class GateResult:
    name: str
    passed: bool
    output: str


@dataclass
class Attempt:
    tier_kind: str  # "local" | "claude"
    model: str
    agent_ok: bool  # the agent process itself exited cleanly
    changed: bool  # the attempt produced a non-empty diff
    gates: list[GateResult]
    created_at: float = field(default_factory=time.time)

    @property
    def passed(self) -> bool:
        return self.changed and all(g.passed for g in self.gates)


@dataclass
class ReviewResult:
    model: str
    approved: bool
    findings: str
    created_at: float = field(default_factory=time.time)


@dataclass
class Task:
    id: str
    repo: str
    branch: str
    base: str
    worktree: str
    description: str
    status: str
    attempts: list[Attempt] = field(default_factory=list)
    reviews: list[ReviewResult] = field(default_factory=list)
    pr_url: str | None = None
    created_at: float = field(default_factory=time.time)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at


def make_id(repo: str, description: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:32]
    return f"{repo}-{slug or 'task'}-{int(time.time())}"


def _state_file(task_id: str) -> Path:
    return STATE_DIR / f"{task_id}.json"


def save(task: Task) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    _state_file(task.id).write_text(json.dumps(asdict(task), indent=2))


def _from_dict(data: dict) -> Task:
    attempts = [
        Attempt(
            tier_kind=a["tier_kind"],
            model=a["model"],
            agent_ok=a["agent_ok"],
            changed=a["changed"],
            gates=[GateResult(**g) for g in a["gates"]],
            created_at=a["created_at"],
        )
        for a in data.get("attempts", [])
    ]
    reviews = [
        ReviewResult(
            model=r["model"],
            approved=r["approved"],
            findings=r["findings"],
            created_at=r["created_at"],
        )
        for r in data.get("reviews", [])
    ]
    return Task(
        id=data["id"],
        repo=data["repo"],
        branch=data["branch"],
        base=data["base"],
        worktree=data["worktree"],
        description=data["description"],
        status=data["status"],
        attempts=attempts,
        reviews=reviews,
        pr_url=data.get("pr_url"),
        created_at=data["created_at"],
    )


def load(task_id: str) -> Task | None:
    path = _state_file(task_id)
    if not path.exists():
        return None
    return _from_dict(json.loads(path.read_text()))


def list_all() -> list[Task]:
    if not STATE_DIR.is_dir():
        return []
    tasks = [_from_dict(json.loads(f.read_text())) for f in STATE_DIR.glob("*.json")]
    return sorted(tasks, key=lambda t: t.created_at, reverse=True)


def opus_attempts_today() -> int:
    """Count Opus attempts across all tasks created today (for the daily cap)."""
    today = date.today()
    count = 0
    for task in list_all():
        for attempt in task.attempts:
            if attempt.model == "opus" and (
                date.fromtimestamp(attempt.created_at) == today
            ):
                count += 1
    return count
