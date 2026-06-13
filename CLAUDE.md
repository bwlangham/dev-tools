# CLAUDE.md

Personal dev-tools repo. Scripts, config, and machine setup for macOS and Windows. **Public repo** — never commit personal data (email, tokens, passwords).

## Layout

- `bin/` — executable utilities meant to be on `$PATH`
- `config/` — dotfiles and app config (symlinked via `install.py`)
- `scripts/` — one-off and maintenance scripts, not on `$PATH`
- `setup/bootstrap.sh` — macOS bootstrap (installs Homebrew + uv, calls install.py)
- `setup/bootstrap.ps1` — Windows bootstrap (installs uv, calls install.py)
- `setup/install.py` — cross-platform idempotent setup logic; the real work happens here

## Conventions

- All real setup logic lives in `install.py`, not in the bootstrap scripts
- Bootstrap scripts are thin: install uv, then call install.py
- `install.py` must be idempotent — check before acting, report status for each step
- Shell scripts in `bin/`: use `#!/usr/bin/env bash` and `set -euo pipefail`
- Python: use `uv run` or `uv`-managed venv; never raw `pip`
- Keep scripts self-contained — no shared libraries unless there's clear repetition

## Adding to install.py

- macOS tool: `ensure_brew("package-name")`
- Windows tool: `ensure_winget("Publisher.PackageId")` — find IDs with `winget search`
- Dotfile symlink: `symlink(REPO_ROOT / "config" / "filename", Path.home() / "filename")`
- Git setting: `git_config("section.key", "value")`

## Working here

- Scripts in `bin/` should be executable (`chmod +x`)
- Don't add error handling, abstractions, or flags beyond what the script actually needs today
- Test idempotency by running `uv run setup/install.py` twice — second run should only print "already installed"
- `main` is protected — always work on a branch and open a PR
