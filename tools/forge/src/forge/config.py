"""Load and initialize forge configuration.

Global config lives at ``~/.config/forge/config.toml`` and defines the
escalation ladder, default gates, and budget. A repo may override gates with a
``forge.toml`` at its root.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "forge" / "config.toml"
STATE_DIR = Path.home() / ".local" / "state" / "forge" / "tasks"

DEFAULT_CONFIG = """\
# forge escalation ladder, cheapest tier first. `kind` is the backend:
#   local  -> opencode + a local model (free, no tokens)
#   claude -> the `claude` CLI on your subscription (flat-rate, scarce)
# Never point a `local` tier at a paid API — that defeats the cost model.
[[ladder]]
kind     = "local"
model    = "ollama/qwen3-coder-32k"
attempts = 2

[[ladder]]
kind     = "claude"
model    = "sonnet"
attempts = 1

[[ladder]]
kind     = "claude"
model    = "opus"
attempts = 1

[budget]
# Cap on Opus attempts across all tasks per calendar day. 0 disables Opus.
opus_per_day = 4

# Review runs only after the build's gates are green, using a strong `claude`
# model (never a local tier). A review that requests changes feeds its findings
# back into a fix attempt, up to `max_rounds`, before a PR is opened.
[review]
model      = "sonnet"
max_rounds = 2

# Default gates, run in the worktree after each build attempt. Override per-repo
# with a [gates] table in <repo>/forge.toml. A failing gate escalates the task.
[gates]
lint      = "ruff check ."
typecheck = "mypy ."
test      = "pytest -q"
"""


@dataclass
class Tier:
    kind: str  # "local" | "claude"
    model: str
    attempts: int = 1


@dataclass
class Budget:
    opus_per_day: int = 4


@dataclass
class Review:
    model: str = "sonnet"
    max_rounds: int = 2


@dataclass
class ForgeConfig:
    ladder: list[Tier] = field(
        default_factory=lambda: [
            Tier("local", "ollama/qwen3-coder-32k", 2),
            Tier("claude", "sonnet", 1),
            Tier("claude", "opus", 1),
        ]
    )
    gates: dict[str, str] = field(
        default_factory=lambda: {
            "lint": "ruff check .",
            "typecheck": "mypy .",
            "test": "pytest -q",
        }
    )
    budget: Budget = field(default_factory=Budget)
    review: Review = field(default_factory=Review)


def _parse(data: dict) -> ForgeConfig:
    cfg = ForgeConfig()
    ladder = data.get("ladder")
    if isinstance(ladder, list) and ladder:
        cfg.ladder = [
            Tier(
                kind=str(step["kind"]),
                model=str(step["model"]),
                attempts=int(step.get("attempts", 1)),
            )
            for step in ladder
        ]
    if isinstance(data.get("gates"), dict):
        cfg.gates = {str(k): str(v) for k, v in data["gates"].items()}
    budget = data.get("budget", {})
    if isinstance(budget, dict):
        cfg.budget = Budget(
            opus_per_day=int(budget.get("opus_per_day", cfg.budget.opus_per_day))
        )
    review = data.get("review", {})
    if isinstance(review, dict):
        cfg.review = Review(
            model=str(review.get("model", cfg.review.model)),
            max_rounds=int(review.get("max_rounds", cfg.review.max_rounds)),
        )
    return cfg


def load() -> ForgeConfig:
    """Load global config, falling back to built-in defaults."""
    if not CONFIG_PATH.exists():
        return ForgeConfig()
    return _parse(tomllib.loads(CONFIG_PATH.read_text()))


def repo_gates(repo_path: Path, cfg: ForgeConfig) -> dict[str, str]:
    """Gates for a repo: its forge.toml [gates] override, else the global default."""
    override = repo_path / "forge.toml"
    if override.exists():
        data = tomllib.loads(override.read_text())
        if isinstance(data.get("gates"), dict):
            return {str(k): str(v) for k, v in data["gates"].items()}
    return cfg.gates


def init(force: bool = False) -> Path:
    """Write a default config file if missing."""
    if CONFIG_PATH.exists() and not force:
        return CONFIG_PATH
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(DEFAULT_CONFIG)
    return CONFIG_PATH
