param(
    [switch]$Reinstall,
    [switch]$NoKernels,
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

# PySpark launches its Python workers with the literal command `python3`, which
# does not exist on Windows. Point the driver and workers at the virtualenv so
# RDD/UDF jobs do not fail with "Cannot run program \"python3\"".
$env:PYSPARK_PYTHON = $venvPython
$env:PYSPARK_DRIVER_PYTHON = $venvPython

# Spark 4.1 only supports Java 17 and 21. Prefer a compatible JDK installed
# under Program Files when JAVA_HOME is unset or points at a newer JDK, so
# PySpark does not silently pick up e.g. Java 25 from PATH.
function Get-JavaMajorVersion([string]$JavaExe) {
    if (-not (Test-Path -LiteralPath $JavaExe)) { return $null }
    # `java -version` writes to stderr, which PowerShell treats as an error when
    # $ErrorActionPreference is Stop.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $firstLine = & $JavaExe -version 2>&1 | Select-Object -First 1
    } finally {
        $ErrorActionPreference = $previous
    }
    if ("$firstLine" -match '"(\d+)') { return [int]$Matches[1] }
    return $null
}

$currentMajor = $null
if ($env:JAVA_HOME) {
    $currentMajor = Get-JavaMajorVersion (Join-Path $env:JAVA_HOME "bin\java.exe")
}
if (-not $currentMajor -or $currentMajor -lt 17 -or $currentMajor -gt 21) {
    $javaRoot = "C:\Program Files\Java"
    $candidates = @()
    if (Test-Path -LiteralPath $javaRoot) {
        $candidates = Get-ChildItem -LiteralPath $javaRoot -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^jdk-(17|21)(\D|$)' } |
            Sort-Object Name -Descending
    }
    foreach ($candidate in $candidates) {
        $major = Get-JavaMajorVersion (Join-Path $candidate.FullName "bin\java.exe")
        if ($major -ge 17 -and $major -le 21) {
            $env:JAVA_HOME = $candidate.FullName
            $env:PATH = (Join-Path $candidate.FullName "bin") + ";" + $env:PATH
            $currentMajor = $major
            break
        }
    }
}

if (-not $env:JAVA_HOME) {
    Write-Warning "JAVA_HOME is not set. Spark 4.1 requires Java 17 or newer."
} else {
    Write-Host "JAVA_HOME=$($env:JAVA_HOME) (Java $currentMajor)" -ForegroundColor Cyan
}
if ($env:OS -eq "Windows_NT" -and -not $env:HADOOP_HOME) {
    Write-Warning "HADOOP_HOME is not set. Spark on Windows needs winutils.exe for table writes."
}

if ($NoKernels) {
    Write-Host "Skipping notebook kernel installation (-NoKernels)." -ForegroundColor DarkGray
}
else {
    $kernelInstaller = Join-Path $backend "install_kernels.py"
    Write-Host "Installing missing notebook kernels (Java, Scala)..." -ForegroundColor Cyan
    Write-Host "The first Scala install downloads almond and can take several minutes." -ForegroundColor DarkGray
    & $venvPython $kernelInstaller
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Notebook kernel installation failed. Start the backend anyway; install kernels later from the notebook toolbar."
    }
}

Write-Host "Starting FastAPI on http://127.0.0.1:$Port ..." -ForegroundColor Green
& $venvPython -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
