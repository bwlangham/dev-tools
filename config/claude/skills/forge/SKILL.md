---
name: forge
description: Drive the forge CLI — an adaptive, cost-aware build pipeline that runs coding tasks through a local Ollama tier, escalating to Claude Sonnet/Opus only when deterministic gates fail, then optionally reviews and opens a PR. Use when the user wants to run/queue an autonomous build task, check/resume forge tasks, configure forge's ladder/gates/budget, set up a repo's forge.toml, or troubleshoot a forge run (e.g. empty diffs from the local tier).
user-invocable: true
---

# forge

An adaptive software-production pipeline: **BUILD → (optional) REVIEW → PR**. It
runs a coding task autonomously in a fresh git worktree, starting on a free local
model and **escalating to the Claude subscription only when deterministic gates
fail**. Cheap model + strong gate + escalate-on-failure keeps Sonnet/Opus spend
proportional to task difficulty.

Source of truth: `~/dev/dev-tools/tools/forge/src/forge/`. Cross-check against
`forge --help` and each subcommand's `--help` before relying on details here.

## CLI

Entrypoint is `forge.cli:app` (Typer). Repos are resolved by name under the dev
root via `devsesh` (forge reuses devsesh for repo discovery + worktrees).

- `forge run <repo> "<desc>" [--pr]` — create a worktree off the repo's base
  branch and run the build loop. `--pr` runs review + PR after a green build.
- `forge pr <task_id>` — review, push, and open a PR for a task that already
  built (`status == done`). Idempotent: re-running returns the existing PR URL.
- `forge resume <task_id>` — continue an interrupted build from saved attempt
  history.
- `forge ls` — list tasks (status: `done` / `needs_human` / `running`).
- `forge show <task_id>` — detail plus the per-attempt routing table (tier,
  agent ok, changed, gates) and any reviews.
- `forge logs <task_id>` — full gate output for each attempt.
- `forge config init [--force] | path | show`.

## Escalation ladder

Default ladder, cheapest first (`config.py` `DEFAULT_CONFIG`; routing in
`router.py:next_tier`):

1. `local` — `ollama/qwen3-coder-32k`, 2 attempts (free, no tokens)
2. `claude` — `sonnet`, 1 attempt
3. `claude` — `opus`, 1 attempt

A tier is skipped once its per-tier attempt budget is spent. Opus is additionally
capped by `budget.opus_per_day` (default 4; `0` disables Opus entirely). When the
ladder is exhausted with gates still red, the task is `needs_human` and the
worktree is left intact.

`local` tiers run `opencode run -m <model> <prompt>` against Ollama; `claude`
tiers run `claude -p` on the subscription (`acceptEdits` for builds, `plan`/
read-only for reviews). Never point a `local` tier at a paid API — that defeats
the cost model.

## Gates

Run in the worktree after each build attempt; a failing gate escalates. Defaults:

- `lint` = `ruff check .`
- `typecheck` = `mypy .`
- `test` = `pytest -q`

Override per-repo with a `[gates]` table in `<repo>/forge.toml`. `forge.toml` is
_read_ config, not an artifact forge produces — commit it where a repo's gates
differ from the defaults (e.g. hermes-tooling uses `uvx ruff check .`,
`uv run --extra dev pytest -q`, and no mypy gate). With no gates configured,
`forge run` warns that the work is unchecked.

## Review + PR

Runs only after the build's gates are green. A strong `claude` model (`review.model`,
default `sonnet`) critiques the diff in read-only/plan mode and emits
`VERDICT: APPROVE | REQUEST_CHANGES`. If it requests changes, the findings feed
back **through the same build ladder — free local tier first, escalating only on
gate failure** — then it re-reviews, up to `review.max_rounds` (default 2). The
branch is then pushed and a PR opened via `gh`. If a fix run exhausts the ladder
with gates still red, the PR is opened as a **draft** (task still `needs_human`).

## Config / state

- Global config: `~/.config/forge/config.toml` (`[[ladder]]`, `[budget]`,
  `[review]`, `[gates]`). Falls back to built-in defaults if absent.
- Task state: `~/.local/state/forge/tasks/<id>.json`.
- Local tier depends on opencode + Ollama (`~/.config/opencode/opencode.jsonc`,
  qwen3-coder-32k/64k).

## Known issue — empty diffs from the local tier

qwen3-coder via Ollama intermittently emits its tool call as raw text that
opencode can't parse, so nothing is written and the attempt escalates with an
empty diff. This is a **model/template quirk, not a forge bug** — do **not**
re-pull or rebuild the model to "fix" it (memory: `forge-local-tier-toolcalls`).
The pipeline degrades safely by escalating. Inspect with `forge show` / `forge
logs`; use `forge resume <task_id>` to retry. See the `TODO(reliability)` note in
`backends.py`.
