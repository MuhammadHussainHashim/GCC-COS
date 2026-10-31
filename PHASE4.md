# Phase 4 — human evidence review

The existing 1,241 observations are preserved. **No real reviewer account, approval or independently verified record has been created by this development run.** Automated comparisons never approve records.

A batch of 20 candidates, covering 20 manufacturers and 17 subcategories, is prepared. These are **candidates with original references, not 20 successfully accessed publisher documents**. All original-access checks failed through the configured proxy; a separate Apple robots diagnostic confirmed `Tunnel connection failed: 403 Forbidden`. This was a proxy response, not a publisher response. No original document body was downloaded. Publisher extraction, document licensing and exact expiry remain unestablished.

## Windows installation and diagnostics

Install Python 3.12 (64-bit), Git and VS Code. Open PowerShell in the existing project folder:

```powershell
$env:PYTHONUTF8 = '1'
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/diagnose.py --output reports/phase4/windows-diagnostics.json
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe scripts/smoke.py
```

Or use `scripts\setup.ps1`, `scripts\diagnose.ps1` and `scripts\test.ps1`. If PowerShell blocks scripts, use the inline commands; no execution-policy change is required. In VS Code select `.venv\Scripts\python.exe` as the interpreter. On Linux/macOS replace the Python path with `.venv/bin/python` and create the environment using `python3 -m venv .venv`.

Diagnostics check Python/dependencies, UTF-8, writable temporary project data, SQLite integrity, Excel/CSV round trips and CLI loading. They perform no network requests, do not touch production records and do not infer a test-suite result. Diagnostics and tests passed on Linux here; **native Windows execution remains untested**. The Windows/Linux CI jobs are prepared, not claimed to have run.

If your database is empty, collect the existing real snapshots first:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --manifest examples/phase2/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase3/sources.json ingest --manifest examples/phase3/local-files.json
```

## Prepare and inspect a batch

```powershell
.\.venv\Scripts\python.exe -m gcc_cos review-prepare --batch phase4 --size 20
.\.venv\Scripts\python.exe -m gcc_cos review-workbook exports/human-review-phase4.xlsx --batch phase4
```

`Human review` contains exact **secondary-dataset reference values** alongside separate, initially blank `publisher_*` columns. It includes original product names, manufacturers, footprint values/units, declared quantities, boundaries, dates, references, license metadata and validity years without guessing missing details. `Field comparisons` shows missing evidence, discrepancies or matches. `Full review queue` lists all 1,241 observations. Workbook edits are working notes only; they never import approvals into the database.

The selection prefers manufacturer/category diversity and PDF references where available. It includes nine construction EPD datasets and eleven electronics manufacturers. Samsung's original reference is a presentation; unsupported formats remain flagged for further work. No reference's accessibility is assumed.

To prepare another specific observation:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos review-prepare --record 4
```

Record 4 is an actual candidate in the current database. In a fresh/restored database, use the record ID shown in your own workbook; IDs can differ with ingestion order.

## Resolve access and permission blockers

The 13 exact publisher hosts are listed in `examples/phase4/required-publisher-hosts.json`. Additions were saved to the cloud environment's **draft** while preserving package-manager presets. Review and save those changes in environment settings, then publish the environment. Saving the draft did not grant runtime access or establish publisher reuse permission.

After actual network settings change, retry metadata checks:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos review-probe --batch phase4
```

The probe checks robots and, only where permitted, HTTP HEAD metadata. It never downloads original document bodies. A successful HEAD is not a content check or a license. Robots denials, proxy failures, 401/403/429 and unsupported redirects remain unresolved; the system does not bypass them. Same-host robots failures are cached within a probe batch.

Dataset licenses (Boavizta ODbL/DbCL or the EPD mirror's embedded terms) are preserved separately from original-document permissions. Do not claim manufacturer PDF reuse rights merely because a licensed dataset links to that PDF. Establish permission before importing a publisher document.

## Provision an authorized human reviewer

The trusted local database operator creates a reviewer interactively:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos reviewer-add reviewer1
```

Enter and confirm a password of at least 12 characters at the hidden prompts. Passwords are stored only as salted PBKDF2-SHA256 hashes (600,000 iterations), never as plaintext. No default reviewer or password exists. Do not put passwords in workbook notes or command-line arguments.

To revoke an account:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos reviewer-disable reviewer1
```

Disabled reviewers' approvals no longer qualify for verified-only export. This is a **trusted local-machine** workflow: the database/filesystem owner remains administrator. It is not enterprise SSO, tamper-proof auditing or a public multi-user service.

## Attach actual publisher evidence

The review-workbook command creates empty evidence templates under `reports/phase4/templates`. Fill a template only after obtaining the actual permitted publisher document and inspecting it:

- `url` must match the record's original publisher reference. Cross-URL linking/provenance reconciliation is not yet supported.
- `reuse_permitted`, `license` and `license_url` must reflect established permission for this publisher document; defaults intentionally block import.
- Enter exact publisher fields, the actual document title/date and expiry information. Preserve partial dates and original unit spellings; no day or year-end expiry is guessed.
- PDF locators require one-based page numbers and verbatim quotes containing each field. Quotes must occur on the stated page. Scanned PDFs/OCR, PPTX and HTML evidence import are not implemented.
- JSON locators use explicit `path` lists to scalar fields. A `quote` can select an explicitly printed date from a validity interval. The explicit `unix_ms_date` transform is available only for date fields whose documented source timestamp is in milliseconds; it records a date conversion, not a guessed date. A year alone cannot justify an exact expiry date.
- Licensing text must have document evidence. A licensing URL is a citation and is not itself proof of permission. Separate external license-page evidence attachments are not yet supported.
- If the document has no expiry statement, use `expiry_statement: "no_expiry_stated"` only after inspecting the full document. This is an operator assessment of absence, pending the human reviewer's explicit attestation; it is not an automatic finding. EPD records with a stored validity year still require supported exact expiry evidence.

Example invocation **after** obtaining the real permitted file and filling its template (the file path below is your own file, not a bundled document):

```powershell
.\.venv\Scripts\python.exe -m gcc_cos review-attach 4 "C:\Evidence\publisher.pdf" reports/phase4/templates/record-4-evidence.json
```

The command archives the file, records SHA-256, checks PDF excerpts/JSON paths and compares publisher fields with the stored observation. It always creates an **awaiting-human-approval** packet, even if every comparison matches. The supplied file's publisher identity must still be personally confirmed by the reviewer; an operator-supplied file is not a network-authenticated original.

Discrepancies and missing evidence block approval. Strict name/boundary/date/unit comparisons can require source/mapping corrections; the interface does not silently edit an original observation or guess equivalences.

## Human review interface

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1
```

Open Streamlit's printed local address. In **Human evidence review**:

1. Choose an observation; prepare its packet if needed.
2. Inspect reference data, original URL, publisher excerpts/field paths, hashes, permission details, comparison results and expiry. A permitted archived document is available for inspection.
3. Enter an authorized reviewer account to attach evidence or record a decision.
4. Approve or reject with an explanation. Approval additionally requires explicitly attesting that you personally inspected the complete source, publisher/file identity, all compared fields, licensing and expiry/absence of expiry.

Decisions are append-only events with reviewer, timestamp (UTC), explanation, explicit attestation, packet ID and a digest of the observation. New record content or evidence packets require a new decision. Source-declared review claims and legacy triage acceptance never grant verified-only eligibility.

Approval is blocked for missing/stale/altered evidence, missing required metadata, comparisons with discrepancies, invalid/unsupported values or units, declared expiry, conflicting expiry years and contradictory physical conversion inputs. Rejected records are excluded. HS6 remains empty unless separately justified; human footprint review does not grant tariff classification.

The legacy **Review queue** and `review` CLI remain triage tools for backward compatibility. Their “accepted” label is not a verification approval. No spreadsheet or automated process grants approval.

## Verified-only exports

```powershell
.\.venv\Scripts\python.exe -m gcc_cos export exports/verified-only-phase4.xlsx --verified-only
.\.venv\Scripts\python.exe -m gcc_cos export exports/verified-only-phase4.csv --verified-only
.\.venv\Scripts\python.exe -m gcc_cos export exports/verified-only-phase4.sqlite --verified-only
```

The separate verified-only workbook is currently **empty**, with headers and explanatory license notices. This is expected: no real human decisions exist. The general 1,241-record collection and ordinary exports are preserved.

At export time the application rechecks the latest human decision and attestation, active reviewer authorization, record digest, latest evidence packet, evidence bytes/hash, supported field evidence and expiry. Expired, rejected, unsupported, revoked or stale approvals are excluded dynamically. Approvals carry reviewer/time/evidence hash and scope, not a claim of third-party scientific certification or comparability.

Verified-only Excel audit sheets are restricted to eligible records/sources. SQLite exports omit credential rows, scrub deleted credential content and vacuum the copy; the source database is unchanged. An exported SQLite file is a data/audit snapshot, not a portable login/authorization backup. Keep private operator backups separately.

## Current outcome and incomplete work

See `examples/phase4/REPORT.md`; regenerate current workbooks/reports with the commands above. Historical machine-generated summaries and diagnostics are not versioned. Twenty candidates are prepared; original document access is unestablished, all 180 critical-field comparisons have missing publisher evidence, no publisher documents are attached, and there are zero real accounts/decisions/verified-only rows. Completing 20 original-document comparisons requires permitted publisher access, established reuse terms and actual human review. General OCR/presentation/HTML import, external licensing attachments, broader URL provenance reconciliation and native Windows execution remain incomplete.
