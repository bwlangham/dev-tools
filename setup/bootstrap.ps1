# Windows bootstrap: installs uv, then hands off to install.py.
# Safe to rerun. Run from PowerShell as: .\setup\bootstrap.ps1

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing uv"
    irm https://astral.sh/uv/install.ps1 | iex
    $env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
}

Write-Host "==> Running install.py"
uv run "$RepoRoot\setup\install.py"
