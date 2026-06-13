"""Escalation routing — pure decision logic, no side effects.

Walks the ladder cheapest-first, returning the next tier to try given the
attempts already made. Opus is additionally guarded by a daily budget cap.
"""

from __future__ import annotations

from .config import Tier
from .task import Attempt


def _used(attempts: list[Attempt], tier: Tier) -> int:
    return sum(
        1 for a in attempts if a.tier_kind == tier.kind and a.model == tier.model
    )


def next_tier(
    ladder: list[Tier],
    attempts: list[Attempt],
    opus_used_today: int,
    opus_per_day: int,
) -> Tier | None:
    """Return the next tier to attempt, or None if the ladder is exhausted.

    A tier is skipped once its per-tier attempt budget is spent. An Opus tier is
    also skipped when the daily Opus budget is already used up.
    """
    for tier in ladder:
        if _used(attempts, tier) >= tier.attempts:
            continue
        if tier.model == "opus" and opus_used_today >= opus_per_day:
            continue
        return tier
    return None
