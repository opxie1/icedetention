# One-time bootstrap for the ICE detention pipeline on Windows.
# Run from PowerShell at the project root:
#   .\setup.ps1
#
# Assumes Python 3.11+ is already installed and on PATH. If `python --version`
# tries to open the Microsoft Store, install Python from python.org first
# (tick "Add python.exe to PATH" in the installer).

$ErrorActionPreference = "Stop"

Write-Host "==> Verifying Python installation" -ForegroundColor Cyan
$pyVersion = & python --version 2>&1
if ($LASTEXITCODE -ne 0 -or $pyVersion -notmatch "^Python\s+3\.(\d+)") {
    Write-Error "Python 3 not found on PATH. Install from python.org and re-run."
    exit 1
}
$minor = [int]$Matches[1]
if ($minor -lt 10) {
    Write-Error "Python $pyVersion detected; this pipeline targets 3.10+. Upgrade and re-run."
    exit 1
}
Write-Host "    Found $pyVersion"

if (-not (Test-Path ".\.venv")) {
    Write-Host "==> Creating virtual environment in .\.venv" -ForegroundColor Cyan
    & python -m venv .venv
} else {
    Write-Host "==> Reusing existing .\.venv" -ForegroundColor Cyan
}

Write-Host "==> Installing dependencies" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host "==> Done." -ForegroundColor Green
Write-Host ""
Write-Host "Activate the environment in new terminals with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Then run the pipeline, e.g.:"
Write-Host "  python -m ice_pipeline.cli all --input-dir `"C:\Users\xief\Downloads`""
