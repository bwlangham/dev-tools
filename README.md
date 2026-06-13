# dev-tools

Personal developer tooling, scripts, and machine setup. Works on macOS and Windows; safe to rerun.

## Fresh machine setup

**macOS** (Apple Silicon or Intel):

```sh
curl -fsSL https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.sh | bash
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.ps1 | iex
```

Installs Homebrew (macOS) or git (Windows) if missing, clones this repo to `~/dev/dev-tools`, then runs the full setup.

## Structure

```
bin/        Executable scripts added to $PATH
config/     Dotfiles and app configuration
scripts/    One-off or maintenance scripts (not on $PATH)
tools/      Installable uv-project tools (e.g. devsesh, forge)
setup/
  bootstrap.sh    macOS: install Homebrew + uv, then run install.py
  bootstrap.ps1   Windows: install uv, then run install.py
  install.py      Cross-platform idempotent setup logic
```

## devsesh

Worktree-based agent session manager. Given a repo under `~/dev`, it creates a
fresh git worktree on a branch off `main` and launches a configurable agent
(`claude`, `opencode`, …) inside it — each in a detached **tmux** session you can
attach to later. Installed to `$PATH` by `install.py` (`uv tool install`).

```sh
devsesh repos                      # list git repos under ~/dev
devsesh new my-repo                # worktree off main + claude in tmux
devsesh new my-repo fix/bug -t opencode -p "fix the failing test"
devsesh ls                         # list sessions (with tmux alive/dead)
devsesh attach my-repo-fix-bug     # attach to the tmux session
devsesh rm my-repo-fix-bug         # tear down (kill tmux + remove worktree)
devsesh clean --merged --dead      # prune merged / dead sessions
```

Config lives at `~/.config/devsesh/config.toml` (`devsesh config init`) — set the
dev root, worktree location, base branch, and per-tool commands.

**Service mode** lets another machine trigger a session over the network:

```sh
export DEVSESH_TOKEN=$(openssl rand -hex 16)
devsesh serve                      # binds 127.0.0.1:8787 by default

# from another machine (over Tailscale or an SSH tunnel):
devsesh trigger http://HOST:8787 my-repo -p "start on the refactor"
ssh HOST -t devsesh attach <name>  # then attach to the spawned session
```

Every endpoint requires a bearer token (from `$DEVSESH_TOKEN`); bind stays on
localhost — expose it across machines via Tailscale or an SSH tunnel, not `0.0.0.0`.

## forge

Adaptive build pipeline. Runs a task autonomously in a fresh worktree (reusing
devsesh's worktree plumbing), defaulting to a **free local model** (qwen3-coder
via Ollama) and **escalating to the Claude subscription only when deterministic
gates fail** — local → Sonnet → Opus, with a daily Opus cap. The gates (lint /
typecheck / test) are what make a cheap model safe as the default: work is judged
on objective signals, not vibes, and only failures cost subscription tokens.

```sh
forge config init                       # ~/.config/forge/config.toml (ladder, gates, budget)
forge run my-repo "add a retry to the http client with tests"
forge ls                                # tasks + status (done / needs_human)
forge show <task-id>                    # per-attempt routing trail (which tier, gate results)
forge logs <task-id>                    # full gate output per attempt
forge resume <task-id>                  # continue an exhausted task's loop
```

Each attempt records the tier/model used and gate results; on success the branch
is committed, on ladder exhaustion the task is flagged `needs_human` with the
worktree left intact. Per-repo gate overrides go in `<repo>/forge.toml` under a
`[gates]` table. Never point a `local` tier at a paid API — that defeats the cost
model (Opus only ever comes through the `claude` CLI on your subscription).

## Bootstrap

**macOS:**

```sh
./setup/bootstrap.sh
```

**Windows (PowerShell):**

```powershell
.\setup\bootstrap.ps1
```

Both scripts install `uv` if missing, then delegate to `install.py` for all further setup. Safe to rerun — each step checks before acting.

## Adding tools

Edit `setup/install.py`:

- macOS packages: add `ensure_brew("pkg-name")`
- Windows packages: add `ensure_winget("Publisher.PackageId")`
- Dotfile symlinks: use `symlink(src, dst)` in the Config section

After bootstrapping, you can rerun setup directly:

```sh
uv run setup/install.py
```

## Requirements

- macOS: Homebrew (installed by bootstrap if missing)
- Windows: winget (built into Windows 10/11)
- Both: [uv](https://docs.astral.sh/uv/) (installed by bootstrap if missing)
