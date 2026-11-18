param(
    [int]$BackendPort = 8000,
    [switch]$NoKernels
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$backendScript = Join-Path $PSScriptRoot "start-backend.ps1"
$frontendScript = Join-Path $PSScriptRoot "start-frontend.ps1"

$backendArguments = @(
    "-NoExit",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$backendScript`"",
    "-Port", "$BackendPort"
)
if ($NoKernels) {
    $backendArguments += "-NoKernels"
}

Start-Process powershell -ArgumentList $backendArguments

Start-Sleep -Seconds 2
& $frontendScript
