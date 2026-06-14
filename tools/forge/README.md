# forge

Adaptive software-production pipeline. Runs a build task autonomously in a fresh
git worktree, defaulting to a free local model (qwen3-coder via Ollama) and
**escalating to the Claude subscription only when deterministic gates fail** —
local → Sonnet → Opus, with an Opus budget cap. Cheap model + strong gate +
escalation-on-failure keeps subscription/Opus spend proportional to difficulty.

Reuses `devsesh` for repo discovery and worktree management. See the repo
`README.md` for usage.

## Review & PR

Once a build's gates are green, `forge run <repo> "<desc>" --pr` runs a **review**
stage: a strong `claude` model (Sonnet by default, set under `[review]` in
`config.toml`) critiques the diff. If it requests changes, the findings feed back
into a **fix run through the same build engine** — fresh from the free local tier,
escalating only when gates fail — then it re-reviews, up to `review.max_rounds`.
Then the branch is pushed and a PR opened via `gh`. `forge pr <task_id>` runs the
same review-and-PR flow against a task that already built successfully; it's
idempotent (re-running returns the existing PR URL).

The review itself always uses a strong subscription model, so every PR gets at
least one strong-model look. The fixes it asks for, though, go back through the
free-first ladder like any other build work — keeping the cost model intact. If a
fix run exhausts the ladder with gates still red, no PR is opened.

## Known limitations

- **Local-tier reliability.** qwen3-coder via Ollama intermittently emits its
  tool call as unparsed raw text, so opencode writes nothing and forge escalates
  with an empty diff. The pipeline degrades safely (it escalates), but until the
  local tier drives opencode's tool-calling reliably, more work reaches the
  subscription than the cost model intends. See the `TODO(reliability)` note in
  `src/forge/backends.py`.
