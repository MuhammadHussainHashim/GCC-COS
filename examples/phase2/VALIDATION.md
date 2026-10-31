# Phase 2 validation — 30 October 2026

Publication note: this is historical documentation. Machine-generated JSON/CSV reports are not versioned; regenerate current results with the audit, diagnostic and smoke commands in the root instructions. Licensed source inputs and provenance manifests remain versioned.
Executed in `/workspace/GCC-COS` on Linux, Python 3.12.14. This report distinguishes collection from independent verification. No native Windows run was performed.

## Executed checks

- Original baseline: **28 passed** before Phase 2 changes.
- Final complete suite: **54 passed** in 2.04 seconds, including all original 28 tests. No skipped or expected-failure tests.
- `pip check`: no broken requirements; no additional dependencies were needed for Phase 2.
- Phase 1 end-to-end: three authentic cement inventory rows ingested into an isolated baseline database and exported as CSV, Excel and SQLite. A repeated ingestion reports zero inserted and three duplicates.
- Live product pipeline: all seven pinned product-source files downloaded using the production robots/permission/checksum gates and ingested successfully. Final repeat: zero inserted and 1,236 duplicate observations across the seven sources.
- Independent offline database: the manifest imported all 1,236 observations from the bundled exact originals with the same permission and checksum checks and no network requests.
- `revalidate`: 1,239 stored observations checked (1,236 product observations plus three original national inventory rows); one paving-stone result changed after the new consistency check. The optional kg-based factor was suppressed and the prior/current results recorded in Validation audit. Original published values were not changed.
- Product-only Excel and CSV: read back with pandas, both contain 1,236 rows, all labeled `published_product_footprint`, with original values, licenses and provenance intact. The paving-stone export contains only its supported per-area normalization and its conflict issue.
- Product-only SQLite export: 1,236 records and seven document references; `PRAGMA integrity_check` returned `ok`, `PRAGMA foreign_key_check` returned no violations. The active source database remains intact, with the three inventory rows preserved.
- Dashboard AppTest: old empty/inventory cases still pass; product filters and search tested. A separate functional run against the real default database showed 1,239 total observations, 1,236 product observations, 10 after the construction filter and one after aluminum search, without exceptions.
- Local dashboard server: startup succeeded, `/_stcore/health` returned `ok`, and HTML was served.
- `git diff --check`: passed. Generated databases/exports remain Git-ignored; source snapshots, attribution and code are repository files.

## Actual collection counts

| Collection | Footprint observations | Distinct manufacturer/product names |
| --- | ---: | ---: |
| Boavizta licensed PCF dataset | 1,226 | 1,222 |
| Six construction EPD datasets | 10 | 6 |
| Total products | **1,236** | **1,228** |
| Original national cement inventories (excluded from product exports) | 3 | Not products |

Four electronics names have more than one source observation; these may differ by report or assumptions and are not silently merged. Two construction EPDs provide separate A1, A2 and A3 values. Multiple observations are not claimed to be additional unique products or full-lifecycle totals. All collected footprint values are finite and positive; none was invented to fill a missing value.

Exact measured counts, issues and source IDs are in `collection-summary.json`. Every input URL and checksum is in `provenance.json` and `sources.json`.

### Construction observations

| Manufacturer / dataset | Retained modules | Observations |
| --- | --- | ---: |
| Heidelberg Materials Precast Denmark — Betonelement Væg C35 Passiv | A1, A2, A3 separately | 3 |
| Holcim Germany — ECOPact concrete DI3234-BHFS, Lüdenscheid-Freisenberg | A1–A3 | 1 |
| Rinn — Beton-Pflastersteine | A1–A3 | 1 |
| Höfer Metall Technik — Aluminiumprofil pressblank | A1–A3 | 1 |
| Master Builders Solutions — MasterProtect NFF 2070 IN cement-based foam | A1–A3 | 1 |
| Skagen Cement Støberi — Aggressiv 35MPa max 16mm vib-fri Færdig beton | A1, A2, A3 separately | 3 |

Cement-based insulation foam is not plain cement. No steel, glass or plain-cement product footprints were collected. Some datasets represent manufacturer production/product averages or families rather than a unique SKU; original representativeness is retained.

### Electronics observations

Collected 1,226 source-reported PCF observations, including 50 smartphones, 452 laptops, 296 monitors, 259 desktops and 55 servers, plus smaller tablet, printer, drive and IoT/home categories. These are from a licensed secondary dataset linking to manufacturer reports; no claim is made that GCC-COS fetched or independently re-extracted the manufacturer PDFs.

## Verification and missing information

- **Independently crosschecked against original publisher reports by GCC-COS: 0.**
- 1,226 electronics observations are labeled manufacturer-reported/not independently crosschecked.
- Nine construction observations, covering five EPD datasets, explicitly declare independent/accredited third-party review and name a reviewer/institution in their source metadata. One EPD names a reviewer but does not supply a qualifying review-type field; its one observation remains `review_metadata_incomplete`.
- All 1,236 product observations remain `needs_review`; no automatic promotion to `verified_product_footprint` occurred.
- Geography is missing for 113 electronics observations; publication date and reference year are missing for 15. These are left empty and flagged.
- All product HS6 assignments are empty pending evidence-based classification. A material name or EPD taxonomy is not treated as an HS classification.
- Two EPDs have validity ending in the current year without a separately established exact expiry date; exact-date review is required. No validity date is invented from a year.

## Licenses and source provenance

Boavizta explicitly licenses the dataset under ODbL 1.0 and individual contents under DbCL 1.0; see the copied `Boavizta-README.md`. Its caution against precise assessments and cross-manufacturer comparison is retained per record. Boavizta-derived database distributions require appropriate attribution and applicable share-alike compliance. Manufacturer report URLs are references, not assertions of permission to redistribute the PDFs.

The EPD JSON documents were collected from commit-pinned `ocni-dtu/epdx` public mirror files. Permission was established individually from `administrativeInformation/publicationAndOwnership`: the exact `licenseType` is “Free of charge for all users and uses” and `accessRestrictions` explicitly says “None”. The parser refuses documents without these fields or with restrictions. The copyright owner, registration and license evidence are preserved. The software repository's MIT license is not applied to the EPD data. Original source URLs point to ÖKOBAUDAT or ECO Platform; those primary documents have not been independently crosschecked.

The workbook contains per-source license and attribution sheets plus an explicit license-notice sheet. Independent EPD sources retain their own terms; they are not claimed to be ODbL or CC0. Complete raw originals needed to reconstruct the collection are bundled here under their respective terms.

## Normalization and resolved failures

- Boavizta's documented total-product kgCO2eq field and one-product schema allow normalization per item. An additional mass-based factor requires explicit positive product weight in kilograms.
- EPD impacts use only supported GWP-total/GWP method UUIDs and stated CO₂-equivalent units. GWP-fossil, biogenic, other indicators and missing module values are not substituted. Module D is not added to manufacturing results.
- EPD declared quantities and units are taken from the single reference product flow. Formula inputs and method/module identifiers are included in exports. Density and area-mass conversions require explicit physical units; inverse “conversion factor to 1 kg” fields are not used.
- One Holcim EPD initially failed because the parser did not recognize the authentic spelling `kg CO_(2) eqv.`. Inspection established its explicit CO₂-equivalent unit; support was added and its live ingestion now succeeds. The failed run is preserved in ingestion history.
- The Rinn paving-stone source states density 2.4 kg/m³, thickness 0.08 m and area mass 179 kg/m². These do not agree dimensionally. GCC-COS does not assume a unit typo or correct the source: it flags the conflict, retains the published 21.8 CO₂-equivalent result per square metre for A1–A3, and suppresses the optional per-kg factor. Previous derived results are retained only in the validation audit.

## Sources that did not work or remain incomplete

| Source/category | Observed outcome |
| --- | --- |
| Direct ÖKOBAUDAT terms/publication site | HTTP 403; no direct connector success claimed |
| UK Government 2025 conversion-factor publication page | HTTP 403; no workbook downloaded or mapped |
| US EPA factor hub page | HTTP 403; no official factor table ingested |
| US LCA Commons | No live API connector implemented/tested |
| General manufacturer PDFs | No direct document connector tested; licensed Boavizta PCF contents used instead |
| Plain cement, steel, glass | No product records collected |
| Vehicles, clothing, furniture and general appliances | Registry placeholders only; no coverage claimed |

The current cloud network allowlist does not include the official UK/EPA/ÖKOBAUDAT domains. HTTP 403 alone does not prove the publishers prohibit access. Any future direct collection still requires both permitted network access and documented source-specific reuse terms. No paywall, authentication gate or robots denial was bypassed.

## Reproducibility and remaining work

The README provides exact Windows installation, live/offline collection, validation, export and dashboard commands. These were checked against the executable parser and package configuration, but native Windows execution remains untested in this Linux cloud environment.

The reusable cloud `start_skill` draft was updated for Phase 2. Installation dependencies were unchanged. Draft saving does not publish or prove restoration in a fresh task; review/save in environment settings and publish when desired.

Next work remains: primary-report crosschecks; clearer product/configuration and uncertainty models; reusable plain-cement/steel/glass EPD sources; direct licensed UK/EPA/LCA Commons connectors; broader consumer categories; general PDF table/OCR support; native Windows tests; and a versioned official HS taxonomy. The working source collection and exports do not establish those capabilities.
