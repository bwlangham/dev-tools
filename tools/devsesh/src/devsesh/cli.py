"""devsesh command-line interface."""

from __future__ import annotations

import os

import typer
from rich.console import Console
from rich.table import Table

from . import cleanup, config, repos
from . import session as sess
from . import worktree

app = typer.Typer(
    help="Worktree-based agent session manager for ~/dev.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


def _cfg() -> config.Config:
    return config.load()


def _fmt_age(seconds: float) -> str:
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def _require_tmux() -> None:
    if not sess.tmux_available():
        console.print("[red]tmux is not installed[/] — `brew install tmux`")
        raise typer.Exit(1)


@app.command(name="repos")
def list_repos_cmd() -> None:
    """List git repos under the dev root."""
    cfg = _cfg()
    found = repos.list_repos(cfg)
    if not found:
        console.print(f"No git repos under {cfg.dev_root}")
        return
    for name in found:
        console.print(name)


@app.command()
def new(
    repo: str = typer.Argument(..., help="Repo name under the dev root."),
    branch: str | None = typer.Argument(
        None, help="Branch name (auto-generated if omitted)."
    ),
    tool: str | None = typer.Option(
        None, "--tool", "-t", help="Agent tool (default from config)."
    ),
    base: str | None = typer.Option(
        None, "--base", "-b", help="Base branch to fork from."
    ),
    prompt: str | None = typer.Option(
        None, "--prompt", "-p", help="Initial prompt for the agent."
    ),
    fg: bool = typer.Option(
        False, "--fg", help="Run in the foreground instead of tmux."
    ),
) -> None:
    """Create a worktree and start an agent session."""
    cfg = _cfg()
    try:
        repo_path = repos.resolve(cfg, repo)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    tool = tool or cfg.default_tool
    base = base or worktree.detect_base(repo_path, cfg.base_branch)
    branch = branch or sess.auto_branch(cfg, prompt)

    if fg:
        try:
            command = sess.build_command(cfg, tool, prompt)
        except ValueError as exc:
            console.print(f"[red]{exc}[/]")
            raise typer.Exit(1)
        wt = worktree.create(repo_path, cfg.worktrees_root, repo, branch, base)
        console.print(f"[green]worktree[/] {wt}")
        os.chdir(wt)
        os.execvp("sh", ["sh", "-c", command])

    _require_tmux()
    try:
        session = sess.create_session(cfg, repo_path, repo, branch, tool, base, prompt)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"[green]started[/] {session.name}  ({session.worktree})")
    console.print(f"attach: [cyan]devsesh attach {session.name}[/]")


@app.command(name="ls")
def list_sessions() -> None:
    """List active sessions."""
    sessions = sess.list_all()
    if not sessions:
        console.print("No sessions.")
        return
    table = Table()
    for col in ("name", "repo", "branch", "tool", "age", "tmux"):
        table.add_column(col)
    for s in sessions:
        alive = sess.tmux_alive(s.tmux_session)
        table.add_row(
            s.name,
            s.repo,
            s.branch,
            s.tool,
            _fmt_age(s.age_seconds),
            "[green]alive[/]" if alive else "[red]dead[/]",
        )
    console.print(table)


@app.command()
def attach(name: str | None = typer.Argument(None)) -> None:
    """Attach to a session's tmux (interactive picker if no name)."""
    _require_tmux()
    if name is None:
        sessions = [s for s in sess.list_all() if sess.tmux_alive(s.tmux_session)]
        if not sessions:
            console.print("No live sessions.")
            raise typer.Exit(1)
        for i, s in enumerate(sessions, 1):
            console.print(f"  {i}. {s.name}  [dim]{s.repo}/{s.branch}[/]")
        choice = typer.prompt("Attach to #", type=int)
        if not 1 <= choice <= len(sessions):
            raise typer.Exit(1)
        name = sessions[choice - 1].name

    if not sess.tmux_alive(name):
        console.print(f"[red]session {name!r} is not alive[/]")
        raise typer.Exit(1)
    sess.tmux_attach(name)


@app.command()
def rm(
    name: str,
    keep_branch: bool = typer.Option(True, "--keep-branch/--delete-branch"),
) -> None:
    """Remove a session: kill tmux, drop the worktree."""
    cfg = _cfg()
    session = sess.load(name)
    if session is None:
        console.print(f"[red]no session {name!r}[/]")
        raise typer.Exit(1)
    cleanup.remove(cfg, session, keep_branch=keep_branch)
    console.print(f"[green]removed[/] {name}")


@app.command()
def clean(
    older_than: str | None = typer.Option(
        None, "--older-than", help="e.g. 30m, 12h, 7d."
    ),
    merged: bool = typer.Option(False, "--merged", help="Branches merged into base."),
    dead: bool = typer.Option(False, "--dead", help="Sessions whose tmux is gone."),
    delete_branch: bool = typer.Option(False, "--delete-branch"),
    dry_run: bool = typer.Option(False, "--dry-run"),
) -> None:
    """Prune stale sessions. Defaults to --dead if no criteria given."""
    cfg = _cfg()
    if not (older_than or merged or dead):
        dead = True
    duration = cleanup.parse_duration(older_than) if older_than else None
    candidates = cleanup.classify(cfg, older_than=duration, merged=merged, dead=dead)
    if not candidates:
        console.print("Nothing to clean.")
        return
    for c in candidates:
        tag = ", ".join(c.reasons)
        if dry_run:
            console.print(f"[yellow]would remove[/] {c.session.name}  ({tag})")
        else:
            cleanup.remove(cfg, c.session, keep_branch=not delete_branch)
            console.print(f"[green]removed[/] {c.session.name}  ({tag})")


@app.command()
def serve(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
) -> None:
    """Run the HTTP service so other machines can trigger sessions."""
    from . import service

    try:
        service.serve(host=host, port=port)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)


@app.command()
def trigger(
    url: str = typer.Argument(..., help="Base URL of a remote devsesh service."),
    repo: str = typer.Argument(...),
    branch: str | None = typer.Argument(None),
    tool: str | None = typer.Option(None, "--tool", "-t"),
    prompt: str | None = typer.Option(None, "--prompt", "-p"),
    base: str | None = typer.Option(None, "--base", "-b"),
    token: str | None = typer.Option(None, "--token", envvar="DEVSESH_TOKEN"),
) -> None:
    """Trigger a session on a remote devsesh service."""
    from . import client

    if not token:
        console.print("[red]a token is required[/] (--token or $DEVSESH_TOKEN)")
        raise typer.Exit(1)
    try:
        result = client.trigger(
            url, repo, token, branch=branch, tool=tool, prompt=prompt, base=base
        )
    except Exception as exc:  # noqa: BLE001 — surface any client/HTTP error
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    console.print(f"[green]created[/] {result['name']}")
    console.print(f"worktree: {result['worktree']}")
    console.print(f"attach:   [cyan]{result['attach_cmd']}[/]")


config_app = typer.Typer(help="Manage devsesh config.")
app.add_typer(config_app, name="config")


@config_app.command("init")
def config_init(force: bool = typer.Option(False, "--force")) -> None:
    """Write a default config file."""
    path = config.init(force=force)
    console.print(f"config at {path}")


@config_app.command("path")
def config_path() -> None:
    console.print(str(config.CONFIG_PATH))


@config_app.command("show")
def config_show() -> None:
    if not config.CONFIG_PATH.exists():
        console.print("[yellow]no config file[/] — run `devsesh config init`")
        return
    console.print(config.CONFIG_PATH.read_text())


if __name__ == "__main__":
    app()
