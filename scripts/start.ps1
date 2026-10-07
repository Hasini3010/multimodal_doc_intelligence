# Start backend + frontend (run from repo root)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $Root

if (-not (Test-Path ".venv\Scripts\uvicorn.exe")) {
    Write-Host "Run setup first: python -m venv .venv; pip install -r backend\requirements.txt"
    exit 1
}

if (-not (Test-Path "frontend\node_modules")) {
    Write-Host "Installing frontend dependencies..."
    Push-Location frontend
    npm install
    Pop-Location
}

$backend = Start-Process -PassThru -WindowStyle Minimized -FilePath "$Root\.venv\Scripts\uvicorn.exe" `
    -ArgumentList "app.main:app","--host","0.0.0.0","--port","8000" `
    -WorkingDirectory "$Root\backend"

Start-Sleep -Seconds 2
Push-Location frontend
$env:NEXT_PUBLIC_API_URL = "http://localhost:8000"
npm run dev
Pop-Location

if ($backend -and -not $backend.HasExited) {
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
}
