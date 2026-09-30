# Setowa Local Demo Launcher for Windows PowerShell
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$backendDir = Join-Path $scriptDir "backend"

$env:ENVIRONMENT = "development"
$env:LOCAL_DEMO = "true"

# Locate Python virtual environment
$pythonCmd = ""
$candidates = @(
    (Join-Path $backendDir "venv\Scripts\python.exe"),
    (Join-Path $backendDir ".venv\Scripts\python.exe"),
    (Join-Path $scriptDir "venv\Scripts\python.exe"),
    (Join-Path $scriptDir ".venv\Scripts\python.exe")
)

foreach ($c in $candidates) {
    if (Test-Path $c) {
        $pythonCmd = $c
        break
    }
}

if (-not $pythonCmd) {
    Write-Host "[Setowa] Creating virtual environment at backend\venv..." -ForegroundColor Cyan
    $sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $sysPython) {
        $sysPython = (Get-Command py -ErrorAction SilentlyContinue).Source
    }
    if (-not $sysPython) {
        Write-Error "Python was not found in PATH. Please install Python 3.10+."
        exit 1
    }
    & $sysPython -m venv (Join-Path $backendDir "venv")
    $pythonCmd = Join-Path $backendDir "venv\Scripts\python.exe"
    Write-Host "[Setowa] Installing requirements..." -ForegroundColor Cyan
    & $pythonCmd -m pip install -q -r (Join-Path $backendDir "requirements.txt")
}

$startScript = Join-Path $backendDir "scripts\start_demo.py"
& $pythonCmd $startScript $args
