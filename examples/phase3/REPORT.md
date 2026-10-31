# GCC-COS Phase 3 coverage and source-verification report

Publication note: this is historical documentation. Machine-generated JSON/CSV reports are not versioned; regenerate current results with the audit, diagnostic and smoke commands in the root instructions. Licensed source inputs and provenance manifests remain versioned.
Date: **30 October 2026**. Execution: Linux/Python 3.12.14. Machine-readable timestamps are UTC. No native Windows or remote CI execution is claimed.

## What was audited and collected

The audit inspected every original **1,236** product observation without deleting or merging records. It checked archived-file hashes against pinned registry hashes, reconstructed source fields, manufacturer attribution, source and original publisher references, declared license evidence, lifecycle boundaries, declared units and existing quality warnings.

Three additional individually reusable construction EPD files were downloaded and ingested successfully, adding **5 observations**. The final default database holds **1,241 product observations** and the original **3 national cement inventory observations**. Product-only exports exclude those inventories.

| Measure | Original Phase 2 cohort | Expanded collection |
| --- | ---: | ---: |
| Product observations | 1,236 | 1,241 |
| Distinct manufacturer/product names | 1,228 | 1,231 |
| Published source datasets | 7 | 10 |
| Observations matched to pinned archived source fields | 1,236 | 1,241 |
| Independently verified against original publisher documents | **0** | **0** |
| Records automatically deleted or merged | 0 | 0 |

Distinct names are not verified unique SKUs: variants, product families, representative products and use assumptions need further review. `model_or_variant` retains the original product designation; no separate variant or HS classification is invented.

See `baseline-summary.json` for the original-cohort audit and `collection-summary.json` for the final measured counts. Record-level findings and the full updated workbook are generated under `reports/phase3` and `exports/products-phase3.xlsx`.

## Duplicates and repeated observations

- **No exact repeated source contents** were found.
- Four repeated-footprint-signature groups contain **8 electronics observations**. Their original manufacturer-report URLs differ; these are not assumed to be accidental duplicates.
- The four model names are Apple Watch SE 44mm Aluminum Case with Sport Band; Apple Watch Series 8 45mm Aluminum Case with Sport Band; Apple Watch Ultra (GPS + Cellular) Titanium Case with Ocean Band; and iPad (9th generation) Wi-Fi + Cellular with 64GB.
- The three watch pairs reference December/September 2022 report versions. The iPad pair references December 2022/September 2021 report versions and has different source comments. These references are preserved as reported; the report documents were not independently checked.
- Two original concrete datasets and one added fibre-cement dataset have separate A1, A2 and A3 observations. They describe three products, not nine independent products. These create three additional repeated-name groups, bringing the final same-name groups to seven.

`duplicate-review.csv` includes record IDs, footprint values, lifecycle scopes and original references. No semantic deduplication or automatic publication-version selection occurred.

## Source verification classes

| Audit class | Final observations | Meaning |
| --- | ---: | --- |
| Independently verified product declarations | **0** | No sufficient primary-document crosscheck was performed |
| `published_third_party_data` | **1,241** | Matched to a pinned secondary dataset with declared reuse evidence and preserved attribution |
| `unverified_record` | **0** in this collection | Used by the audit when archive, row, attribution, schema or permission evidence cannot be established |

The last zero does **not** mean the footprint values were independently verified. All 1,241 remain independently unverified and require human review. The audit's published-data class establishes secondary-source traceability only. It does not prove scientific accuracy, current declaration validity or the original publisher's authenticity.

Fourteen construction observations, from eight EPD datasets, carry explicit source-declared independent/accredited review metadata. One Holcim observation lacks a qualifying review-type field, despite naming a reviewer. Electronics are manufacturer-reported through Boavizta. None was promoted to independently verified status. Changing an imported status string or accepting a record manually cannot establish independent verification; unsupported claims are flagged. A primary-document independent-verification workflow remains unimplemented.

## Reuse license review and attribution

### Boavizta — 1,226 observations

- Pinned commit: `61323eb5c3bb63b0703e7a9c6456482ccbaac3a6`.
- Database license: **ODbL 1.0**. Individual contents: **DbCL 1.0**.
- The copied upstream README's checksum is registered and checked. Manufacturer names, original report URLs, source row evidence and Boavizta attribution remain attached to every record.
- Attribution and applicable database share-alike obligations remain applicable when redistributing derived data. The workbook includes license notices. This review records declared source permissions; it is not a legal opinion or a blanket license for manufacturer reports.
- Manufacturer PDFs were not redistributed or scraped. Original report links are references only. Boavizta explicitly warns against precise assessments and cross-manufacturer comparisons; those warnings remain attached.

### Construction EPD mirror — 15 observations from 9 documents

- Pinned mirror commit: `2baec750dddd29de750337c8f18e2cef7106c78f`.
- Every selected document explicitly states `licenseType: Free of charge for all users and uses` and access restrictions `None`.
- The adapter checks these individual fields and rejects missing or restrictive metadata. Original copyright owners, registration numbers, publisher references, review declarations and source hashes remain preserved.
- The mirror repository's MIT **software** license is not applied to the data. These datasets are not represented as CC0. Current permission metadata was reviewed in the pinned mirrored documents; original publisher terms and documents were not independently revalidated online.

See `source-verification.csv`, the source registry and both Phase 2/Phase 3 provenance manifests for exact URLs, document hashes, permission evidence, manufacturer attribution and per-source obligations.

## Actual category coverage

| Category | Actual product-level observations | Limits |
| --- | ---: | --- |
| Electronics | 1,226 | Includes 50 smartphone observations and limited printers/IoT/home devices; not general appliance coverage |
| Concrete | 8 | Separate construction lifecycle modules; not a full-lifecycle comparison set |
| Aluminum profiles | 1 | Manufacturer representative EPD, not universal aluminum |
| Cement-based foam and fibre-cement boards | 4 | Not plain cement; three board observations are expired |
| Ceramic façades | 2 | One expired declaration |
| Plain cement | 0 | No manufacturer cement product footprint collected |
| Steel | 0 | No permitted product dataset collected |
| Glass | 0 | No permitted product dataset collected |
| Vehicles | 0 | Permission-gated mapping template only |
| General appliances | 0 | Limited electronics/home devices do not establish this category |
| Furniture | 0 | Permission-gated mapping template only |
| Clothing | 0 | Permission-gated mapping template only |

The three new documents cover Argeton ceramic façade (one A1–A3 value), EQUITONE Pictura/Natura Pro fibre-cement board (A1, A2 and A3 separately) and Moeding Alphaton ceramic façade (one A1–A3 value). Four added observations have expired validity years (2024 or 2025). They remain historical evidence, not current declarations.

Reusable CSV mapping templates now support all nine requested target categories. Templates contain no carbon values, licenses, URLs or permissions; they are disabled by default. Tests demonstrate that generic emission factors are not promoted to product footprints. A template or registry placeholder is not a working live source connector or collected coverage.

## Units, boundaries and warnings

The expanded collection preserves declared units: **1,226 item**, **4 kg**, **6 qm (m²)** and **5 m³** observations. Original gas-equivalent unit spellings remain intact. Publication year is reported separately from the source reference year; missing or partial dates are never filled with guessed days.

Boundaries: 1,226 source-schema total-product-lifecycle observations; three A1, three A2, three A3 and six A1–A3 construction observations. Module D credits are not added to manufacturing results. GWP methods and boundary differences remain attached.

All 1,241 carry HS manual-review, independent-crosscheck and source-limitation warnings. Additional findings:

- 113 missing geographies.
- 15 missing publication dates/reference years.
- 8 observations in repeated-footprint-signature review groups.
- 5 observations with inconsistent density/area-mass/thickness metadata. Published values remain unchanged; optional mass-based conversions are suppressed rather than silently correcting source units.
- 4 observations from expired declarations.
- 2 validity years ending in 2026 requiring exact-date review.

No HS6 codes were added. Product descriptions and EPD taxonomies alone do not establish a tariff classification.

## HTTP 403 and unavailable sources

Direct UK Government, US EPA and ÖKOBAUDAT page requests returned HTTP 403 during Phase 2. Phase 3 did not repeatedly retry those unchanged blocked requests or bypass the network/publisher restrictions. No new direct connector success is claimed for them or for LCA Commons. The public licensed mirror is identified transparently as a secondary source, not impersonated as direct publisher access.

The downloader now records structured `error_code`, `http_status` and `next_action` fields for access denials/rate limits. HTTP 401/403/429 stops that source without automatically retrying, changing identities, spoofing headers or switching proxy routes. Tests simulate each status and demonstrate that one failed source does not block an authorized local source. Existing run history is preserved by an additive schema migration. These simulated tests are not claims of successful live access to blocked sources.

Future collection requires documented publisher permission and permitted network access, or an explicitly authorized public API/download. No paywall, authentication gate or robots denial was bypassed.

## Validation and Windows status

- **88 automated tests passed**, including all original 54 tests.
- The baseline and expanded collection/export pipelines were executed; Excel, CSV and SQLite were read back successfully.
- Expanded offline smoke pipeline collected 1,241 observations, checked revalidation/audit, exported all three formats, checked SQLite integrity and foreign keys, and cleaned up temporary databases.
- `linux-smoke.json` records the actual OS as Linux and `native_windows_execution: false`.
- Original database history, source evidence and all three national inventory observations were preserved.
- Dashboard AppTest executed against the actual default database; search, construction filtering, original-source details, warning controls and the quality/source audit rendered without exceptions.
- Dependency consistency and whitespace checks passed.

`WINDOWS.md` contains exact beginner-friendly PowerShell commands. `scripts/setup.ps1` and `scripts/test.ps1` check external command exit codes and do not change execution policy. UTF-8 mode is enabled for international names. `scripts/smoke.py` explicitly closes SQLite handles for Windows temporary-file cleanup. Native `windows-latest` and Linux CI jobs are configured with actual-OS smoke artifacts.

**Native Windows execution and remote CI jobs have not been run in this session.** PowerShell is not installed in this cloud environment. Prepared scripts/static checks are not a Windows pass result.

## Remaining work

Primary publisher-document crosschecks and independent verification remain incomplete. Plain cement, steel, glass, vehicle, general-appliance, furniture and clothing data remain uncollected. Direct UK/EPA/ÖKOBAUDAT/LCA Commons connectors, broader original manufacturer-report extraction, exact product variants/SKUs, uncertainty/GWP harmonization, official versioned HS classification and native Windows execution remain outstanding. Existing historical/secondary data should not be used as a verified universal product-factor database.
