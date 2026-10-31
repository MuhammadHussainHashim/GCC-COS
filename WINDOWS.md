# GCC-COS on Windows — beginner instructions

**Status:** scripts and a native Windows CI job are provided. This cloud session ran Linux/Python 3.12 only. No native Windows execution or CI success is claimed. A workflow file is a test plan until the actual Windows job completes.

## Install Python and open the project

1. Install Python **3.12, 64-bit**, with “Add Python to PATH”. Install Git and VS Code.
2. Open the existing GCC-COS folder in VS Code. If you do not have it yet, clone the repository first.
3. Open **Terminal → New Terminal → PowerShell**. Run from the project root:

```powershell
$env:PYTHONUTF8 = '1'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

In VS Code choose **Python: Select Interpreter**, then `.venv\Scripts\python.exe`. Activation is not required. UTF-8 mode preserves international manufacturer/product names.

Optional equivalent setup script:

```powershell
.\scripts\setup.ps1
```

If your machine restricts script execution, use the inline commands above. These scripts do not change execution policy. Do not disable TLS verification to work around certificate or network problems.

## Collect the real bundled data without Internet downloads

Dependency installation needs package access. Collection below uses attributed source snapshots and makes no source-network requests:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --manifest examples/phase2/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase3/sources.json ingest --manifest examples/phase3/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos revalidate
```

First collection adds **1,241 observations**: 1,226 electronics observations and 15 construction lifecycle-module observations. These are not 1,241 unique SKUs or independently verified declarations. Repeat collection should report duplicates without adding records.

To download the same commit-pinned sources instead of using the bundled originals:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --source all
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase3/sources.json ingest --source all
```

Downloads use robots, license, HTTPS, host and checksum checks. An HTTP 403/401 stops that source; do not change identities, headers, proxy routes or hosts to evade a restriction. Obtain permission or configure an expressly authorized public API/download. HTTP 429 stops collection rather than aggressively retrying.

## Audit and export

```powershell
.\.venv\Scripts\python.exe -m gcc_cos audit --output-dir reports/phase3 --workbook exports/products-phase3.xlsx
.\.venv\Scripts\python.exe -m gcc_cos export exports/products-phase3.csv --products-only
.\.venv\Scripts\python.exe -m gcc_cos export exports/products-phase3.sqlite --products-only
```

Open `exports\products-phase3.xlsx` in Excel. It contains original records, source licensing, product audits, source verification, coverage, duplicate review and validation/review history. All records require review. Expired EPDs are historical evidence, not current product declarations.

`reports\phase3` contains machine-readable CSV audit tables and `summary.json`. No records are deleted or merged by audit. `model_or_variant` preserves the source's product designation; a separate variant is not guessed. Publication year and reference year are reported separately. Original manufacturer-report links are references, not proof that the documents were independently checked or licensed for redistribution.

## Launch the dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open the local browser address printed by Streamlit. Use **Products only**, search text, category/manufacturer/country filters and the warning filter. Inspect selected records for original evidence, HS classification evidence and source limitations. The **Quality and verification** tab shows archive/license traceability, repeated observations and coverage. Normal CSV/Excel buttons export the selected records; use the audit command for the expanded audit workbook.

## Run tests on your Windows machine

```powershell
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest -q
$env:GCC_SMOKE_REPORT = 'reports/windows-smoke.json'
.\.venv\Scripts\python.exe scripts/smoke.py
```

The smoke test uses temporary databases, checks real offline ingestion/audits and all three export formats, and leaves the production database unchanged. It records the **actual** OS, Python version and outcome. A successful `native_windows_execution: true` report must come from Windows; do not edit a Linux report to change that flag.

Optional test wrapper:

```powershell
.\scripts\test.ps1
```

Every external command in the wrappers checks its exit code. A failed stage stops the script. Temporary SQLite handles are explicitly closed so Windows can clean up its temporary files.

## GitHub Actions

`.github/workflows/tests.yml` defines independent `windows-latest` and `ubuntu-latest` jobs using Python 3.12. Each installs dependencies, runs the full suite, executes the real-data offline smoke pipeline and uploads `smoke-report.json`. After pushing your changes, inspect the actual Windows job and artifact before describing Windows as tested. This cloud session did not push changes or run those jobs.

The scripts are intended for Windows PowerShell 5.1+ or PowerShell 7. PowerShell itself was not installed in this cloud environment, so syntax/runtime validation on that shell remains outstanding.
