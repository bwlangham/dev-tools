# dev-tools

Personal developer tooling, scripts, and machine setup. Works on macOS and Windows; safe to rerun.

## Fresh machine setup

**macOS** (Apple Silicon or Intel):

```sh
curl -fsSL https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.sh | bash
```

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.ps1 | iex
```

Installs Homebrew (macOS) or git (Windows) if missing, clones this repo to `~/dev/dev-tools`, then runs the full setup.

## Structure

```
bin/        Executable scripts added to $PATH
config/     Dotfiles and app configuration
scripts/    One-off or maintenance scripts (not on $PATH)
setup/
  bootstrap.sh    macOS: install Homebrew + uv, then run install.py
  bootstrap.ps1   Windows: install uv, then run install.py
  install.py      Cross-platform idempotent setup logic
```

## Bootstrap

**macOS:**

```sh
./setup/bootstrap.sh
```

**Windows (PowerShell):**

```powershell
.\setup\bootstrap.ps1
```

Both scripts install `uv` if missing, then delegate to `install.py` for all further setup. Safe to rerun — each step checks before acting.

## Adding tools

Edit `setup/install.py`:

- macOS packages: add `ensure_brew("pkg-name")`
- Windows packages: add `ensure_winget("Publisher.PackageId")`
- Dotfile symlinks: use `symlink(src, dst)` in the Config section

After bootstrapping, you can rerun setup directly:

```sh
uv run setup/install.py
```

## Requirements

- macOS: Homebrew (installed by bootstrap if missing)
- Windows: winget (built into Windows 10/11)
- Both: [uv](https://docs.astral.sh/uv/) (installed by bootstrap if missing)
