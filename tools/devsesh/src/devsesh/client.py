"""Client for triggering a session on a remote devsesh service."""

from __future__ import annotations

import httpx


def trigger(
    url: str,
    repo: str,
    token: str,
    *,
    branch: str | None = None,
    tool: str | None = None,
    prompt: str | None = None,
    base: str | None = None,
) -> dict:
    """POST a session-creation request to a remote service; return its JSON."""
    body: dict[str, str] = {"repo": repo}
    if branch:
        body["branch"] = branch
    if tool:
        body["tool"] = tool
    if prompt:
        body["prompt"] = prompt
    if base:
        body["base"] = base

    resp = httpx.post(
        f"{url.rstrip('/')}/sessions",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()
