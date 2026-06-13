"""Load and initialize devsesh configuration."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path.home() / ".config" / "devsesh" / "config.toml"
STATE_DIR = Path.home() / ".local" / "state" / "devsesh" / "sessions"

DEFAULT_CONFIG = """\
dev_root        = "~/dev"
worktrees_root  = "~/dev/.worktrees"
default_tool    = "claude"
base_branch     = "main"
branch_prefix   = "sesh"

[tools]
claude   = "claude"
opencode = "opencode"

[service]
host  = "127.0.0.1"
port  = 8787
# Token required for the HTTP service. Prefer setting $DEVSESH_TOKEN instead of
# storing it here (this repo is public). Leave empty to read from the env var.
token = ""
"""


@dataclass
class ServiceConfig:
    host: str = "127.0.0.1"
    port: int = 8787
    token: str = ""

    @property
    def resolved_token(self) -> str:
        return os.environ.get("DEVSESH_TOKEN", "") or self.token


@dataclass
class Config:
    dev_root: Path = field(default_factory=lambda: Path.home() / "dev")
    worktrees_root: Path = field(
        default_factory=lambda: Path.home() / "dev" / ".worktrees"
    )
    default_tool: str = "claude"
    base_branch: str = "main"
    branch_prefix: str = "sesh"
    tools: dict[str, str] = field(
        default_factory=lambda: {"claude": "claude", "opencode": "opencode"}
    )
    service: ServiceConfig = field(default_factory=ServiceConfig)


def _expand(p: str) -> Path:
    return Path(p).expanduser()


def load() -> Config:
    """Load config from disk, falling back to defaults for any missing keys."""
    cfg = Config()
    if not CONFIG_PATH.exists():
        return cfg

    data = tomllib.loads(CONFIG_PATH.read_text())
    if "dev_root" in data:
        cfg.dev_root = _expand(data["dev_root"])
    if "worktrees_root" in data:
        cfg.worktrees_root = _expand(data["worktrees_root"])
    cfg.default_tool = data.get("default_tool", cfg.default_tool)
    cfg.base_branch = data.get("base_branch", cfg.base_branch)
    cfg.branch_prefix = data.get("branch_prefix", cfg.branch_prefix)
    if isinstance(data.get("tools"), dict):
        cfg.tools = {**cfg.tools, **data["tools"]}

    svc = data.get("service", {})
    if isinstance(svc, dict):
        cfg.service = ServiceConfig(
            host=svc.get("host", cfg.service.host),
            port=int(svc.get("port", cfg.service.port)),
            token=svc.get("token", cfg.service.token),
        )
    return cfg


def init(force: bool = False) -> Path:
    """Write a default config file if missing."""
    if CONFIG_PATH.exists() and not force:
        return CONFIG_PATH
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(DEFAULT_CONFIG)
    return CONFIG_PATH
