#!/usr/bin/env bash
set -euo pipefail

# macOS bootstrap: installs Homebrew and uv, then hands off to install.py.
# Safe to rerun.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v brew &>/dev/null; then
  echo "==> Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  # Apple Silicon: add brew to PATH for the rest of this script
  eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
fi

if ! command -v uv &>/dev/null; then
  echo "==> Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Running install.py"
uv run "$REPO_ROOT/setup/install.py"
