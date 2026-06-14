from forge.config import Tier
from forge.router import next_tier
from forge.task import Attempt


def _ladder():
    return [
        Tier("local", "ollama/qwen3-coder-32k", 2),
        Tier("claude", "sonnet", 1),
        Tier("claude", "opus", 1),
    ]


def _attempt(kind: str, model: str) -> Attempt:
    return Attempt(tier_kind=kind, model=model, agent_ok=True, changed=True, gates=[])


def test_starts_at_cheapest_tier():
    tier = next_tier(_ladder(), [], opus_used_today=0, opus_per_day=4)
    assert tier is not None
    assert (tier.kind, tier.model) == ("local", "ollama/qwen3-coder-32k")


def test_exhausts_local_budget_before_escalating():
    attempts = [_attempt("local", "ollama/qwen3-coder-32k")]
    tier = next_tier(_ladder(), attempts, opus_used_today=0, opus_per_day=4)
    assert tier is not None and tier.kind == "local"  # second local attempt allowed

    attempts.append(_attempt("local", "ollama/qwen3-coder-32k"))
    tier = next_tier(_ladder(), attempts, opus_used_today=0, opus_per_day=4)
    assert tier is not None and tier.model == "sonnet"


def test_escalates_through_to_opus():
    attempts = [
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("claude", "sonnet"),
    ]
    tier = next_tier(_ladder(), attempts, opus_used_today=0, opus_per_day=4)
    assert tier is not None and tier.model == "opus"


def test_ladder_exhausted_returns_none():
    attempts = [
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("claude", "sonnet"),
        _attempt("claude", "opus"),
    ]
    assert next_tier(_ladder(), attempts, opus_used_today=1, opus_per_day=4) is None


def test_opus_daily_cap_skips_opus():
    attempts = [
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("claude", "sonnet"),
    ]
    # opus budget already spent today -> opus is skipped -> ladder exhausted
    assert next_tier(_ladder(), attempts, opus_used_today=4, opus_per_day=4) is None


def test_opus_disabled_when_cap_zero():
    attempts = [
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("local", "ollama/qwen3-coder-32k"),
        _attempt("claude", "sonnet"),
    ]
    assert next_tier(_ladder(), attempts, opus_used_today=0, opus_per_day=0) is None
