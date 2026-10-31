# Phase 4 implementation and evidence report

Publication note: this is historical documentation. Machine-generated JSON/CSV reports are not versioned; regenerate current results with the audit, diagnostic and smoke commands in the root instructions. Licensed source inputs and provenance manifests remain versioned.
Date: 30 October 2026. This development run executed on Linux/Python 3.12.14. Machine-generated event timestamps are UTC.

## What was completed

- Preserved the 1,241-observation product collection and three original national cement inventories.
- Prepared a 20-record candidate batch spanning **20 manufacturers and 17 subcategories** (eleven electronics manufacturers and nine construction EPD datasets).
- Exported exact secondary-reference names, manufacturers, footprint values/units, declared units, boundaries, dates, source links, dataset license/attribution and stated validity years. Publisher-derived fields are separate and blank until actual evidence is attached.
- Created an authenticated local reviewer workflow, password hashing, explicit human attestation, version-bound evidence packets and append-only approval/rejection events with explanations and timestamps.
- Added evidence-supported PDF quote/page and JSON path comparisons. Automatic results always await human approval. Mismatches and missing evidence block approval.
- Added `--verified-only` filtering for records and Excel/CSV/SQLite exports, rechecking rejection, exact expiry, evidence support/hash, record version, latest packet/decision and reviewer authorization. Legacy triage acceptance is insufficient.
- Added Windows diagnostic Python/PowerShell scripts and exact beginner commands in `PHASE4.md`. SQLite/UTF-8/CSV/Excel diagnostics passed on Linux.

## What could not be completed

**Twenty accessible original publisher documents were not obtained.** Twenty candidates with original references were selected, not twenty publisher-verified declarations.

All 20 original-access checks encountered `ProxyError` during the robots prerequisite. A separate diagnostic showed that the configured proxy was reachable but denied Apple's tunnel with **HTTP 403 Forbidden**. This is not evidence that Apple, or every other publisher, returned 403 or forbids legitimate access. The other packets retain their actual observed generic proxy errors; the single diagnosis is not fabricated as a publisher response for all twenty.

The current enforced cloud allowlist excludes these original-publisher hosts. Thirteen exact host additions were saved to the environment configuration draft while preserving package-manager presets. Review/save in environment settings and publish before retrying; the draft save itself did not apply runtime access. `required-publisher-hosts.json` records the domains. No proxy route, identity, paywall, robots rule or TLS validation was bypassed.

No original document bodies were downloaded. Original publisher permissions remain unestablished. Boavizta/EPD secondary-dataset licensing is not represented as a license for linked manufacturer PDFs. As a result:

| Measure | Actual result |
| --- | ---: |
| Candidate records prepared | 20 |
| Original publisher documents confirmed accessible | 0 |
| Publisher document bodies downloaded/attached | 0 |
| Critical field comparisons with missing publisher evidence | 180 |
| Completed original-document comparisons | 0 |
| Automatic approvals | 0 |
| Real reviewer accounts created | 0 |
| Real human decisions/approvals | 0 |
| Verified-only export rows | 0 |

No discrepancy-free comparison, exact publisher extraction or successful verification is claimed. Existing source-data validation warnings remain visible, including expired declarations and physical-metadata inconsistencies.

## Review artifacts

- `exports/human-review-phase4.xlsx`: 20 candidates with separate reference/publisher columns, 180 comparison rows, the full 1,241-record queue, decision history and instructions.
- `exports/verified-only-phase4.xlsx`: empty Records sheet with stable headers, approval metadata columns and notices. Related CSV and SQLite exports are also empty.
- `reports/phase4/templates`: permission-blocked empty evidence-specification templates; no invented publisher values or rights.
- `summary.json` and `publisher-access.json`: measured candidate/access outcomes.
- `linux-diagnostics.json` and `linux-smoke.json`: actual OS and validation outcomes.

Edits to a workbook do not approve records. Human review must occur through an operator-provisioned account in the dashboard or the password-prompting CLI. No real reviewer was provisioned by the agent, and no production decision was written.

## Tests and safeguards

The complete test suite passed **111 tests**, preserving all original 88. Added regressions exercise successful authenticated review **only on explicitly synthetic temporary fixtures**, no automatic/legacy approval, unauthorized/disabled accounts, missing attestation, revocation, rejection, record/evidence version changes, checksum corruption, discrepancy/expiry/permission failures, malformed mappings, numeric-quote boundaries, explicit timestamp locators, empty and nonempty verified exports, credential removal from SQLite copies and the actual review UI.

The offline smoke pipeline used temporary databases, collected the real existing 1,241 observations, checked standard CSV/Excel/SQLite round trips and source audit, prepared a 20-record review batch and confirmed zero verified rows. No production account or decision was created by smoke tests.

Diagnostics checked actual Python/dependencies, UTF-8/filesystem access, SQLite integrity, CSV/Excel round trips and CLI loading without network requests. **Native Windows execution and remote Windows CI remain untested**. PowerShell syntax was inspected, not executed in this Linux environment.

## Trust boundaries and remaining work

This is a trusted local-machine workflow. The filesystem/database operator provisions authorized reviewers and can administer the database. It is not tamper-proof auditing, enterprise identity or a public multi-user service. Passwords are salted PBKDF2-SHA256 hashes with 600,000 iterations; exported SQLite data omits credentials. Approval means an authorized human inspected evidence/transcription and declared support, not scientific assurance, third-party certification, comparability or an HS classification.

An operator-supplied file must be personally matched to its original publisher by the reviewer; a matching URL string or file hash does not prove online authenticity. PDF/JSON evidence requires explicit locators. OCR/scans, PPTX/HTML extraction, separate external license-page attachments and cross-reference URL reconciliation remain unsupported. No-expiry statements require full-document human inspection; validity years alone never become invented exact dates.

Next steps require permitted publisher access and actual document permissions, completing publisher extraction/comparisons, and authorized human decisions. Native Windows execution must be performed and its real diagnostic/test artifacts inspected before describing Windows as tested. Verified-only output may correctly remain empty until then.
