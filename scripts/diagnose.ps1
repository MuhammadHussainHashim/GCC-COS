# Windows diagnostics only; does not approve records or infer application-test success.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    $GccPython = Join-Path $PWD '.venv\Scripts\python.exe'
    if (-not (Test-Path $GccPython)) { throw 'Run the documented setup commands to create .venv first.' }
    & $GccPython scripts/diagnose.py --output reports/phase4/windows-diagnostics.json
    if ($LASTEXITCODE -ne 0) { throw 'Local diagnostics failed. Inspect the JSON report before continuing.' }
    Write-Host 'Local diagnostics passed. Next run scripts/test.ps1; diagnostics are not a test-suite result.'
} finally { Pop-Location }
