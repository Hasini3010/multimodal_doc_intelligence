# One-time setup (Windows, from repo root)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

python -m venv .venv
.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r backend\requirements.txt

if (-not (Test-Path ".env")) {
    Copy-Item .env.example .env
    Write-Host "Created .env — add GEMINI_API_KEY before using /ask or demo."
}

.\.venv\Scripts\python scripts\make_test_pack.py
.\.venv\Scripts\python scripts\ingest_all.py

Push-Location frontend
npm install
Pop-Location

Write-Host "Setup complete. Start UI: .\scripts\start.ps1"
