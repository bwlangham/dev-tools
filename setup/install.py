#!/usr/bin/env python3
"""
Cross-platform idempotent dev setup.
Called by bootstrap.sh / bootstrap.ps1, or directly: uv run setup/install.py
"""

import platform
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
IS_MACOS = platform.system() == "Darwin"
IS_WINDOWS = platform.system() == "Windows"


def ok(label: str) -> None:
    print(f"  {label}: already installed")


def installing(label: str) -> None:
    print(f"  {label}: installing...")


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True)


def ensure_brew(pkg: str) -> None:
    if (
        subprocess.run(
            ["brew", "list", "--formula", pkg], capture_output=True
        ).returncode
        == 0
    ):
        ok(pkg)
    else:
        installing(pkg)
        run("brew", "install", pkg)


def ensure_brew_cask(pkg: str) -> None:
    if (
        subprocess.run(["brew", "list", "--cask", pkg], capture_output=True).returncode
        == 0
    ):
        ok(pkg)
    else:
        installing(pkg)
        run("brew", "install", "--cask", pkg)


def ensure_winget(pkg_id: str) -> None:
    name = pkg_id.split(".")[-1]
    result = subprocess.run(
        ["winget", "list", "--id", pkg_id, "--exact"],
        capture_output=True,
        text=True,
    )
    if pkg_id.lower() in result.stdout.lower():
        ok(name)
    else:
        installing(name)
        run(
            "winget",
            "install",
            "--id",
            pkg_id,
            "--exact",
            "--silent",
            "--accept-package-agreements",
        )


def ensure_shell_line(rc_file: Path, line: str) -> None:
    content = rc_file.read_text() if rc_file.exists() else ""
    if line in content:
        ok(rc_file.name)
        return
    with rc_file.open("a") as f:
        f.write(f"\n{line}\n")
    print(f"  {rc_file.name}: added '{line}'")


def git_config(key: str, value: str) -> None:
    current = subprocess.run(
        ["git", "config", "--global", key], capture_output=True, text=True
    ).stdout.strip()
    if current == value:
        ok(f"git {key}")
    else:
        run("git", "config", "--global", key, value)
        print(f"  git {key}: set to '{value}'")


def ensure_uv_tool(name: str, path: Path) -> None:
    listed = subprocess.run(
        ["uv", "tool", "list"], capture_output=True, text=True
    ).stdout
    if any(line.split()[:1] == [name] for line in listed.splitlines()):
        ok(name)
    else:
        installing(name)
        run("uv", "tool", "install", "--editable", str(path))


def symlink(src: Path, dst: Path) -> None:
    if dst.is_symlink() and dst.resolve() == src.resolve():
        ok(str(dst))
        return
    if dst.exists() or dst.is_symlink():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(src)
    print(f"  linked {dst} -> {src}")


def main() -> None:
    print(f"\n==> Platform: {platform.system()} {platform.machine()}")

    # --- Core CLI tools ---
    print("\n==> Core tools")
    if IS_MACOS:
        ensure_brew("gh")
        ensure_brew("git")
        ensure_brew("opencode")
        ensure_brew("rtk")
        ensure_brew("pre-commit")
        ensure_brew("shellcheck")
        ensure_brew("tmux")
        ensure_brew_cask("claude-code")
    elif IS_WINDOWS:
        ensure_winget("GitHub.cli")
        ensure_winget("Git.Git")
    else:
        print("  (Linux: install gh and git via your package manager)")

    # --- Shell config ---
    print("\n==> Shell config")
    if IS_MACOS:
        zshrc = Path.home() / ".zshrc"
        brew_bin = (
            "/opt/homebrew/bin/brew"
            if Path("/opt/homebrew").exists()
            else "/usr/local/bin/brew"
        )
        ensure_shell_line(zshrc, f'eval "$({brew_bin} shellenv)"')
        ensure_shell_line(zshrc, 'export PATH="$HOME/.local/bin:$PATH"')
    elif not IS_WINDOWS:  # Linux / WSL
        bashrc = Path.home() / ".bashrc"
        ensure_shell_line(bashrc, 'export PATH="$HOME/.local/bin:$PATH"')

    # --- Git config ---
    print("\n==> Git config")
    git_config("init.defaultBranch", "main")
    git_config("push.default", "current")
    git_config("push.autoSetupRemote", "true")
    git_config("pull.rebase", "true")
    git_config("rebase.autoStash", "true")
    git_config("core.excludesfile", "~/.gitignore_global")
    git_config("core.autocrlf", "true" if IS_WINDOWS else "input")
    git_config("alias.st", "status -sb")
    git_config("alias.co", "checkout")
    git_config("alias.sw", "switch")
    git_config("alias.br", "branch")
    git_config("alias.ci", "commit")
    git_config("alias.amend", "commit --amend --no-edit")
    git_config("alias.undo", "reset HEAD~1 --mixed")
    git_config("alias.unstage", "reset HEAD --")
    git_config("alias.aa", "add --all")
    git_config("alias.d", "diff")
    git_config("alias.dc", "diff --cached")
    git_config("alias.last", "log -1 HEAD --stat")
    git_config("alias.lg", "log --oneline --graph --decorate --all")
    git_config("alias.who", "shortlog -sn --no-merges")

    # --- Git identity (not stored in repo; prompt if missing) ---
    print("\n==> Git identity")

    def git_cfg(key: str) -> str:
        r = subprocess.run(
            ["git", "config", "--global", key], capture_output=True, text=True
        )
        return r.stdout.strip()

    def set_git_identity(key: str, prompt: str) -> None:
        if git_cfg(key):
            ok(key)
        elif not sys.stdin.isatty():
            print(
                f"  {key}: skipped (no TTY — set manually with git config --global {key} '...')"
            )
        else:
            value = input(f"  {prompt}: ").strip()
            if value:
                run("git", "config", "--global", key, value)

    set_git_identity("user.name", "Full name")
    set_git_identity("user.email", "Email address")

    # --- Local uv tools ---
    print("\n==> Local tools")
    if not IS_WINDOWS:
        ensure_uv_tool("devsesh", REPO_ROOT / "tools" / "devsesh")
    else:
        print("  devsesh: skipped (tmux-backed sessions are macOS/Linux only)")

    print("\n==> Done\n")


if __name__ == "__main__":
    main()
