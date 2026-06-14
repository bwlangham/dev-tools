"""Headless agent invocation.

Two backends map onto the cost model:
  local  -> `opencode run` against a local model (free, no tokens)
  claude -> `claude -p` on the subscription (Sonnet/Opus; flat-rate, scarce)

Both edit files in-place in the worktree, which acts as the sandbox.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .config import Tier

# claude -p auto-applies file edits in this mode without prompting. Bash and
# other tools stay gated — fine, since forge runs the gates itself.
CLAUDE_PERMISSION_MODE = "acceptEdits"


@dataclass
class AgentResult:
    agent_ok: bool
    output: str


def run_agent(tier: Tier, prompt: str, cwd: Path) -> AgentResult:
    if tier.kind == "local":
        return _run_local(tier.model, prompt, cwd)
    if tier.kind == "claude":
        return _run_claude(tier.model, prompt, cwd)
    raise ValueError(f"unknown tier kind {tier.kind!r}")


def _run_local(model: str, prompt: str, cwd: Path) -> AgentResult:
    # TODO(reliability): qwen3-coder via Ollama intermittently emits its tool
    # call as raw text opencode can't parse (e.g. `<function=write>...`), so no
    # file is written and the attempt escalates with an empty diff — defeating
    # the cost model. Seen ~1/3 of runs in testing; nondeterministic, not a forge
    # bug. Investigate: alternate variants (qwen3-coder-64k / non-coder qwen3),
    # the Ollama chat template's tool rendering, and opencode's Ollama provider
    # settings (native vs OpenAI-compat endpoint). Until the local tier parses
    # tool calls reliably, expect more escalation to the subscription than ideal.
    proc = subprocess.run(
        ["opencode", "run", "-m", model, prompt],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    return AgentResult(agent_ok=proc.returncode == 0, output=proc.stdout + proc.stderr)


def _claude(model: str, prompt: str, cwd: Path, permission_mode: str) -> AgentResult:
    proc = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
            "--model",
            model,
            "--output-format",
            "json",
            "--permission-mode",
            permission_mode,
        ],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    agent_ok = proc.returncode == 0
    output = proc.stdout
    # claude --output-format json reports its own error state in the payload.
    try:
        payload = json.loads(proc.stdout)
        agent_ok = agent_ok and not payload.get("is_error", False)
        output = payload.get("result", proc.stdout)
    except (json.JSONDecodeError, AttributeError):
        output = proc.stdout + proc.stderr
    return AgentResult(agent_ok=agent_ok, output=output)


def _run_claude(model: str, prompt: str, cwd: Path) -> AgentResult:
    return _claude(model, prompt, cwd, CLAUDE_PERMISSION_MODE)


def run_claude_readonly(model: str, prompt: str, cwd: Path) -> AgentResult:
    """Invoke claude for analysis only — `plan` mode forbids any file edits."""
    return _claude(model, prompt, cwd, "plan")
