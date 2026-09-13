#!/usr/bin/env python3
"""
Cross-platform idempotent dev setup.
Called by bootstrap.sh / bootstrap.ps1, or directly: uv run setup/install.py
"""

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.jsonc"
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


def ensure_claude_code() -> None:
    """Install Claude Code via the official claude.ai installer."""
    if shutil.which("brew") and (
        subprocess.run(
            ["brew", "list", "--cask", "claude-code"], capture_output=True
        ).returncode
        == 0
    ):
        sys.exit(
            "  claude-code: installed via Homebrew cask. Remove it first with "
            "'brew uninstall --cask claude-code', then re-run."
        )
    if shutil.which("claude"):
        ok("claude-code")
        return
    installing("claude-code")
    if IS_WINDOWS:
        run(
            "powershell",
            "-NoProfile",
            "-Command",
            "irm https://claude.ai/install.ps1 | iex",
        )
    else:
        run("bash", "-c", "curl -fsSL https://claude.ai/install.sh | bash")


def ensure_opencode() -> None:
    """Install opencode via the official installer.

    Homebrew's opencode installs to /opt/homebrew/bin, which ~/.local/bin
    shadows on PATH, so the brew copy is downloaded but never run.
    """
    if shutil.which("brew") and (
        subprocess.run(
            ["brew", "list", "--formula", "opencode"], capture_output=True
        ).returncode
        == 0
    ):
        sys.exit(
            "  opencode: installed via Homebrew, where ~/.local/bin shadows it. "
            "Remove it first with 'brew uninstall opencode', then re-run."
        )
    if shutil.which("opencode"):
        ok("opencode")
        return
    installing("opencode")
    run(
        "bash",
        "-c",
        "curl -fsSL https://opencode.ai/install | bash -s -- --no-modify-path",
    )
    symlink(
        Path.home() / ".opencode" / "bin" / "opencode",
        Path.home() / ".local" / "bin" / "opencode",
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


def uv_tool_installed(name: str) -> bool:
    listed = subprocess.run(
        ["uv", "tool", "list"], capture_output=True, text=True
    ).stdout
    return any(line.split()[:1] == [name] for line in listed.splitlines())


def ensure_uv_tool(name: str, path: Path) -> None:
    if uv_tool_installed(name):
        ok(name)
    else:
        installing(name)
        run("uv", "tool", "install", "--editable", str(path))


def ensure_serena() -> None:
    """Serena MCP server: semantic code tools for opencode and Claude Code."""
    if uv_tool_installed("serena-agent"):
        ok("serena-agent")
    else:
        installing("serena-agent")
        run("uv", "tool", "install", "-p", "3.13", "serena-agent")
    if (Path.home() / ".serena" / "serena_config.yml").exists():
        ok("serena config")
    else:
        run(str(Path.home() / ".local" / "bin" / "serena"), "init")


def ensure_opencode_serena() -> None:
    """Register the Serena MCP server in opencode's global config."""
    entry = {
        "type": "local",
        "command": [
            str(Path.home() / ".local" / "bin" / "serena"),
            "start-mcp-server",
            "--context",
            "ide",
            "--project-from-cwd",
        ],
        "enabled": True,
    }
    if OPENCODE_CONFIG.exists():
        try:
            config = json.loads(OPENCODE_CONFIG.read_text())
        except json.JSONDecodeError:
            print(f"  opencode serena: skipped ({OPENCODE_CONFIG} is not plain JSON)")
            return
    else:
        config = {"$schema": "https://opencode.ai/config.json"}
    if config.get("mcp", {}).get("serena") == entry:
        ok("opencode serena")
        return
    config.setdefault("mcp", {})["serena"] = entry
    OPENCODE_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    OPENCODE_CONFIG.write_text(json.dumps(config, indent=2) + "\n")
    print(f"  opencode serena: registered in {OPENCODE_CONFIG}")


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
        ensure_opencode()
        ensure_brew("rtk")
        ensure_brew("pre-commit")
        ensure_brew("shellcheck")
        ensure_brew("tmux")
        ensure_claude_code()
    elif IS_WINDOWS:
        ensure_winget("GitHub.cli")
        ensure_winget("Git.Git")
        ensure_claude_code()
    else:
        print("  (Linux: install gh and git via your package manager)")
        ensure_claude_code()

    # --- Shell config ---
    print("\n==> Shell config")
    if IS_MACOS:
        zshrc = Path.home() / ".zshrc"
        # Skip shell configuration if .zshrc is a symlink (managed by any system like home-manager, etc.)
        if zshrc.is_symlink():
            print("  .zshrc: symlinked (likely managed by home-manager or similar)")
        else:
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

    # --- Setup tools ---
    run("rtk", "init", "-g", "--opencode")

    # --- Local uv tools ---
    print("\n==> Local tools")
    if not IS_WINDOWS:
        ensure_uv_tool("devsesh", REPO_ROOT / "tools" / "devsesh")
        ensure_uv_tool("forge", REPO_ROOT / "tools" / "forge")
        ensure_serena()
        ensure_opencode_serena()
        symlink(
            REPO_ROOT / "config" / "claude" / "skills" / "forge",
            Path.home() / ".claude" / "skills" / "forge",
        )
    else:
        print("  devsesh: skipped (tmux-backed sessions are macOS/Linux only)")
        print("  forge: skipped (depends on devsesh)")

    print("\n==> Done\n")


if __name__ == "__main__":
    main()
