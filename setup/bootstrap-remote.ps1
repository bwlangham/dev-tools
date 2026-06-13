# Fresh-machine bootstrap for Windows. Safe to rerun.
# irm https://raw.githubusercontent.com/bwlangham/dev-tools/main/setup/bootstrap-remote.ps1 | iex
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/bwlangham/dev-tools.git"
$RepoDir = "$env:USERPROFILE\dev\dev-tools"

# Allow local scripts to run (needed to exec bootstrap.ps1 from disk)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# --- Git (needed to clone; winget is built into Windows 10 1809+ / Windows 11) ---
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "==> Installing git"
    winget install --id Git.Git --exact --silent --accept-package-agreements --accept-source-agreements
    # Reload PATH from registry so git is available in this session
    $env:PATH = [Environment]::GetEnvironmentVariable("PATH", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("PATH", "User")
}

# --- Clone repo ---
if (Test-Path "$RepoDir\.git") {
    Write-Host "==> Repo already cloned at $RepoDir"
} else {
    Write-Host "==> Cloning dev-tools"
    New-Item -ItemType Directory -Force -Path (Split-Path $RepoDir) | Out-Null
    git clone $RepoUrl $RepoDir
}

# --- Hand off to the standard bootstrap ---
& "$RepoDir\setup\bootstrap.ps1"
