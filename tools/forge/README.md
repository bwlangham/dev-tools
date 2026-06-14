# forge

Adaptive software-production pipeline. Runs a build task autonomously in a fresh
git worktree, defaulting to a free local model (qwen3-coder via Ollama) and
**escalating to the Claude subscription only when deterministic gates fail** —
local → Sonnet → Opus, with an Opus budget cap. Cheap model + strong gate +
escalation-on-failure keeps subscription/Opus spend proportional to difficulty.

Reuses `devsesh` for repo discovery and worktree management. See the repo
`README.md` for usage.

## Known limitations

- **Local-tier reliability.** qwen3-coder via Ollama intermittently emits its
  tool call as unparsed raw text, so opencode writes nothing and forge escalates
  with an empty diff. The pipeline degrades safely (it escalates), but until the
  local tier drives opencode's tool-calling reliably, more work reaches the
  subscription than the cost model intends. See the `TODO(reliability)` note in
  `src/forge/backends.py`.
