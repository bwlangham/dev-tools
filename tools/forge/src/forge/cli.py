"""forge command-line interface."""

from __future__ import annotations

import re
import time

import typer
from devsesh import config as dconfig
from devsesh import repos as drepos
from devsesh import worktree as dw
from rich.console import Console
from rich.table import Table

from . import build, config, pipeline
from . import task as tasks
from .config import Tier
from .task import Attempt, ReviewResult, Task

app = typer.Typer(
    help="Adaptive software-production pipeline for ~/dev.",
    no_args_is_help=True,
    add_completion=True,
)
console = Console()


def _fmt_age(seconds: float) -> str:
    s = int(seconds)
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def _branch(description: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", description.lower()).strip("-")[:40]
    return f"forge/{slug}" if slug else f"forge/{int(time.time())}"


def _tier_label(tier: Tier) -> str:
    return f"{tier.kind}:{tier.model}"


def _run_loop(task: Task, repo_path, fcfg) -> Task:
    def on_tier(tier: object) -> None:
        assert isinstance(tier, Tier)
        console.print(f"[cyan]→ attempting[/] [bold]{_tier_label(tier)}[/]")

    def on_attempt(attempt: Attempt) -> None:
        if attempt.passed:
            console.print("  [green]all gates passed[/]")
            return
        if not attempt.changed:
            console.print("  [yellow]no changes produced[/] — escalating")
            return
        failed = [g.name for g in attempt.gates if not g.passed]
        console.print(f"  [red]gate failed:[/] {', '.join(failed)} — escalating")

    return build.run_build(
        fcfg, task, repo_path, on_tier=on_tier, on_attempt=on_attempt
    )


def _review_and_pr(task: Task, repo_path, fcfg, do_pr: bool) -> Task:
    def on_review(result: ReviewResult) -> None:
        if result.approved:
            console.print(f"  [green]review approved[/] ([bold]{result.model}[/])")
        else:
            console.print(
                f"  [yellow]review requested changes[/] ([bold]{result.model}[/])"
                " — fixing"
            )

    def on_tier(tier: object) -> None:
        assert isinstance(tier, Tier)
        console.print(f"  [cyan]→ fixing with[/] [bold]{_tier_label(tier)}[/]")

    def on_attempt(attempt: Attempt) -> None:
        if attempt.passed:
            console.print("    [green]fix passed gates[/]")
        elif not attempt.changed:
            console.print("    [yellow]fix made no changes[/] — escalating")
        else:
            failed = ", ".join(g.name for g in attempt.gates if not g.passed)
            console.print(f"    [red]fix still failing:[/] {failed} — escalating")

    if do_pr:
        console.print("\n[cyan]→ reviewing[/]")
    return pipeline.run_review_and_pr(
        fcfg,
        task,
        repo_path,
        do_pr=do_pr,
        on_review=on_review,
        on_tier=on_tier,
        on_attempt=on_attempt,
    )


@app.command()
def run(
    repo: str = typer.Argument(..., help="Repo name under the dev root."),
    description: str = typer.Argument(..., help="What to build."),
    pr: bool = typer.Option(
        False, "--pr", help="On success, review the change, push, and open a PR."
    ),
) -> None:
    """Run an autonomous build task: escalate across tiers until gates pass."""
    fcfg = config.load()
    dcfg = dconfig.load()
    try:
        repo_path = drepos.resolve(dcfg, repo)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    base = dw.detect_base(repo_path, dcfg.base_branch)
    branch = _branch(description)
    wt = dw.create(repo_path, dcfg.worktrees_root, repo, branch, base)

    if not config.repo_gates(repo_path, fcfg):
        console.print("[yellow]warning:[/] no gates configured — work is unchecked")

    task = Task(
        id=tasks.make_id(repo, description),
        repo=repo,
        branch=branch,
        base=base,
        worktree=str(wt),
        description=description,
        status="running",
    )
    tasks.save(task)
    console.print(f"[green]task[/] {task.id}")
    console.print(f"[green]worktree[/] {wt}\n")

    task = _run_loop(task, repo_path, fcfg)
    if pr and task.status == "done":
        task = _review_and_pr(task, repo_path, fcfg, do_pr=True)
    _report(task, repo_path)


@app.command(name="pr")
def open_pr(task_id: str = typer.Argument(...)) -> None:
    """Review, push, and open a PR for a task that already built successfully."""
    fcfg = config.load()
    dcfg = dconfig.load()
    task = tasks.load(task_id)
    if task is None:
        console.print(f"[red]no task {task_id!r}[/]")
        raise typer.Exit(1)
    if task.status != "done":
        console.print(
            f"[red]task is {task.status!r}[/] — only `done` tasks can be PR'd"
        )
        raise typer.Exit(1)
    try:
        repo_path = drepos.resolve(dcfg, task.repo)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    task = _review_and_pr(task, repo_path, fcfg, do_pr=True)
    _report(task, repo_path)


@app.command()
def resume(task_id: str = typer.Argument(...)) -> None:
    """Continue a task's build loop from its saved attempt history."""
    fcfg = config.load()
    dcfg = dconfig.load()
    task = tasks.load(task_id)
    if task is None:
        console.print(f"[red]no task {task_id!r}[/]")
        raise typer.Exit(1)
    try:
        repo_path = drepos.resolve(dcfg, task.repo)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    task.status = "running"
    task = _run_loop(task, repo_path, fcfg)
    _report(task, repo_path)


def _report(task: Task, repo_path) -> None:
    console.print()
    if task.status == "done":
        diffstat = dw.git(
            repo_path, "diff", "--stat", f"{task.base}...{task.branch}", check=False
        )
        console.print(f"[green]done[/] in {len(task.attempts)} attempt(s)")
        console.print(diffstat.stdout.strip() or "(no diff)", markup=False)
        if task.reviews:
            last = task.reviews[-1]
            verdict = (
                "[green]approved[/]"
                if last.approved
                else "[yellow]changes requested[/]"
            )
            console.print(f"review: {verdict} ({last.model})")
        if task.pr_url:
            console.print(f"PR: [cyan]{task.pr_url}[/]")
    else:
        console.print(
            f"[red]needs human[/] — ladder exhausted after "
            f"{len(task.attempts)} attempt(s)"
        )
        console.print(f"worktree left intact: [cyan]{task.worktree}[/]")


@app.command(name="ls")
def list_tasks() -> None:
    """List tasks and their status."""
    all_tasks = tasks.list_all()
    if not all_tasks:
        console.print("No tasks.")
        return
    table = Table()
    for col in ("id", "repo", "status", "attempts", "age"):
        table.add_column(col)
    status_color = {"done": "green", "needs_human": "red", "running": "yellow"}
    for t in all_tasks:
        color = status_color.get(t.status, "white")
        table.add_row(
            t.id,
            t.repo,
            f"[{color}]{t.status}[/]",
            str(len(t.attempts)),
            _fmt_age(t.age_seconds),
        )
    console.print(table)


@app.command()
def show(task_id: str = typer.Argument(...)) -> None:
    """Show a task's details and per-attempt routing trail."""
    task = tasks.load(task_id)
    if task is None:
        console.print(f"[red]no task {task_id!r}[/]")
        raise typer.Exit(1)
    console.print(f"[bold]{task.id}[/]  ({task.status})")
    console.print(f"repo:     {task.repo}")
    console.print(f"branch:   {task.branch}  (base {task.base})")
    console.print(f"worktree: {task.worktree}")
    if task.pr_url:
        console.print(f"pr:       {task.pr_url}")
    console.print(f"task:     {task.description}\n")
    table = Table(title="attempts")
    for col in ("#", "tier", "agent", "changed", "gates"):
        table.add_column(col)
    for i, a in enumerate(task.attempts, 1):
        if not a.changed:
            gates_cell = "[yellow]no changes[/]"
        elif a.passed:
            gates_cell = "[green]all passed[/]"
        else:
            failed = ", ".join(g.name for g in a.gates if not g.passed)
            gates_cell = f"[red]{failed}[/]"
        table.add_row(
            str(i),
            f"{a.tier_kind}:{a.model}",
            "ok" if a.agent_ok else "[red]err[/]",
            "yes" if a.changed else "no",
            gates_cell,
        )
    console.print(table)
    if task.reviews:
        rtable = Table(title="reviews")
        for col in ("#", "model", "verdict"):
            rtable.add_column(col)
        for i, r in enumerate(task.reviews, 1):
            verdict = "[green]approved[/]" if r.approved else "[yellow]changes[/]"
            rtable.add_row(str(i), r.model, verdict)
        console.print(rtable)


@app.command()
def logs(task_id: str = typer.Argument(...)) -> None:
    """Print full gate output for each attempt of a task."""
    task = tasks.load(task_id)
    if task is None:
        console.print(f"[red]no task {task_id!r}[/]")
        raise typer.Exit(1)
    for i, a in enumerate(task.attempts, 1):
        console.print(f"\n[bold]── attempt {i}: {a.tier_kind}:{a.model} ──[/]")
        if not a.gates:
            console.print("[dim](no gates run)[/]")
        for g in a.gates:
            mark = "[green]PASS[/]" if g.passed else "[red]FAIL[/]"
            console.print(f"{mark} {g.name}")
            if not g.passed and g.output:
                console.print(g.output, markup=False, style="dim")


config_app = typer.Typer(help="Manage forge config.")
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
        console.print("[yellow]no config file[/] — run `forge config init`")
        return
    console.print(config.CONFIG_PATH.read_text(), markup=False)


if __name__ == "__main__":
    app()
