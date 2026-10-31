# Run from Windows after setup.ps1. Does not change the production database.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $GccPython = Join-Path $PWD '.venv\Scripts\python.exe'
    & $GccPython -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'Automated tests failed.' }
    & $GccPython scripts/smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'Offline collection/export/audit smoke test failed.' }
    Write-Host 'Tests passed on this machine; inspect the CI report before claiming another OS was tested.'
} finally { Pop-Location }
