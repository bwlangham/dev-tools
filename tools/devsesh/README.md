# devsesh

Worktree-based agent session manager. Spins up a fresh git worktree on a branch
off `main` for a repo under `~/dev`, then launches a configurable agent
(`claude`, `opencode`, …) inside it — each running in a detached tmux session so
you can spawn it headlessly and attach later. Includes a token-authenticated
HTTP service so another machine can trigger sessions remotely.

See the repo `README.md` for usage.
