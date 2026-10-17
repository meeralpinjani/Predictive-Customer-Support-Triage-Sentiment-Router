# One-command local demo (Windows, no Docker):  powershell -ExecutionPolicy Bypass -File .\start-demo.ps1
# First run creates the Python venv, installs everything and downloads the AI models (~1-2 GB).
# Add -Reset to wipe and reseed the demo database.
param([switch]$Reset)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"
$py = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Creating Python environment..." -ForegroundColor Cyan
    python -m venv (Join-Path $backend ".venv")
    & $py -m pip install -r (Join-Path $backend "requirements-dev.txt")
    & $py -m pip install -r (Join-Path $backend "requirements-ml.txt") --extra-index-url https://download.pytorch.org/whl/cpu
}
if (-not (Test-Path (Join-Path $backend ".env"))) {
    Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
}
if ($Reset -or -not (Test-Path (Join-Path $backend "triage.db"))) {
    Write-Host "Seeding demo data (loads the AI models once)..." -ForegroundColor Cyan
    Push-Location $backend; & $py -m scripts.reset_demo; Pop-Location
}
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    Write-Host "Installing frontend packages..." -ForegroundColor Cyan
    Push-Location $frontend; npm ci; Pop-Location
}

Start-Process powershell -WorkingDirectory $backend -ArgumentList "-NoExit", "-Command", "& '$py' -m uvicorn app.main:app --port 8000"
Start-Process powershell -WorkingDirectory $frontend -ArgumentList "-NoExit", "-Command", "npm run dev"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
Write-Host "Dashboard: http://localhost:5173   API docs: http://localhost:8000/docs" -ForegroundColor Green
