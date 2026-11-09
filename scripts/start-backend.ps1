param(
    [switch]$Reinstall,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location -LiteralPath $backend

$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    $python = Get-Command python -ErrorAction SilentlyContinue
    if (-not $python) {
        throw "Python was not found on PATH. Install Python 3.11+ first."
    }
    & $python.Source -m venv .venv
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}
elseif ($Reinstall) {
    Write-Host "Reinstalling backend dependencies..." -ForegroundColor Cyan
    & $venvPython -m pip install --upgrade pip
    & $venvPython -m pip install -r requirements.txt
}

if (-not $env:JAVA_HOME) {
    Write-Warning "JAVA_HOME is not set. Spark 4.1 requires Java 17+."
}
if ($env:OS -eq "Windows_NT" -and -not $env:HADOOP_HOME) {
    Write-Warning "HADOOP_HOME is not set. Spark on Windows needs winutils.exe for table writes."
}

Write-Host "Starting FastAPI on http://127.0.0.1:$Port ..." -ForegroundColor Green
& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
