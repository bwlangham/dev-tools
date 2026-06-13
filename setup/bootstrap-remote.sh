#!/usr/bin/env bash
# Fresh-machine bootstrap. Safe to rerun.
# curl -fsSL https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.sh | bash
set -euo pipefail

REPO_URL="https://github.com/bwlangham/dev-tools.git"
REPO_DIR="$HOME/dev/dev-tools"

# --- Homebrew (also installs Xcode CLT, which includes git) ---
if ! command -v brew &>/dev/null; then
  echo "==> Installing Homebrew"
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Brew may not be on PATH yet (Apple Silicon vs Intel path differs)
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# --- Clone repo ---
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "==> Repo already cloned at $REPO_DIR"
else
  echo "==> Cloning dev-tools"
  git clone "$REPO_URL" "$REPO_DIR"
fi

# --- Hand off to the standard bootstrap ---
exec "$REPO_DIR/setup/bootstrap.sh"
