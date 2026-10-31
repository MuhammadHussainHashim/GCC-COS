# Windows PowerShell 5.1+ / PowerShell 7. Python 3.12 must already be installed.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    py -3.12 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
    $GccPython = Join-Path $PWD '.venv\Scripts\python.exe'
    & $GccPython -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $GccPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
    Write-Host 'Setup complete. Next: .\scripts\test.ps1'
} finally { Pop-Location }
