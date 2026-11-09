param(
    [switch]$Install
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend-ts"
Set-Location -LiteralPath $frontend

$npm = "npm.cmd"
$nodeModules = Join-Path $frontend "node_modules"

if ($Install -or -not (Test-Path -LiteralPath $nodeModules)) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & $npm install --no-audit --no-fund
}

Write-Host "Starting Vite on http://127.0.0.1:5173 ..." -ForegroundColor Green
& $npm run dev
