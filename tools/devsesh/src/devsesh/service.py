"""FastAPI service exposing session creation to other machines."""

from __future__ import annotations

from dataclasses import asdict

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException

from . import repos
from . import session as sess
from .config import Config, load


def _auth_dependency(cfg: Config):
    token = cfg.service.resolved_token

    def check(authorization: str = Header(default="")) -> None:
        if not token:
            raise HTTPException(
                status_code=503,
                detail="service token not set (configure $DEVSESH_TOKEN)",
            )
        expected = f"Bearer {token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="invalid or missing token")

    return check


def build_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="devsesh", version="0.1.0")
    auth = _auth_dependency(cfg)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/repos", dependencies=[Depends(auth)])
    def list_repos() -> dict:
        return {"repos": repos.list_repos(cfg)}

    @app.get("/sessions", dependencies=[Depends(auth)])
    def list_sessions() -> dict:
        return {
            "sessions": [
                {**asdict(s), "alive": sess.tmux_alive(s.tmux_session)}
                for s in sess.list_all()
            ]
        }

    @app.post("/sessions", dependencies=[Depends(auth)])
    def create_session(body: dict) -> dict:
        repo = body.get("repo")
        if not repo:
            raise HTTPException(status_code=400, detail="'repo' is required")
        try:
            repo_path = repos.resolve(cfg, repo)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        from . import worktree

        tool = body.get("tool") or cfg.default_tool
        base = body.get("base") or worktree.detect_base(repo_path, cfg.base_branch)
        prompt = body.get("prompt")
        branch = body.get("branch") or sess.auto_branch(cfg, prompt)

        try:
            session = sess.create_session(
                cfg, repo_path, repo, branch, tool, base, prompt
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return {
            "name": session.name,
            "worktree": session.worktree,
            "branch": session.branch,
            "attach_cmd": f"devsesh attach {session.name}",
        }

    @app.delete("/sessions/{name}", dependencies=[Depends(auth)])
    def delete_session(name: str) -> dict:
        from . import cleanup

        session = sess.load(name)
        if session is None:
            raise HTTPException(status_code=404, detail=f"no session {name!r}")
        cleanup.remove(cfg, session)
        return {"removed": name}

    return app


def serve(host: str | None = None, port: int | None = None) -> None:
    cfg = load()
    if not sess.tmux_available():
        raise RuntimeError("tmux is required for the service (install via Homebrew)")
    app = build_app(cfg)
    uvicorn.run(app, host=host or cfg.service.host, port=port or cfg.service.port)
