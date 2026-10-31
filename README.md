# Green Carbon Corridor — Carbon Operating System (GCC-COS)

GCC-COS is a local, free Python application for collecting carbon-footprint evidence. It downloads authorized documents, keeps their original values and references, checks data quality, stores records in SQLite, and exports CSV, Excel and SQLite. Streamlit provides a searchable dashboard. No paid APIs, AI subscriptions or account are required for the working sources.

**Phase 2 result: 1,236 product-level footprint observations, covering 1,228 distinct manufacturer/product names.** These comprise 1,226 manufacturer-reported electronics observations collected through Boavizta and 10 lifecycle-module observations from six real construction EPD datasets collected through a public ILCD mirror. The three Phase 1 national cement inventory records are preserved separately.

**These are source-reported observations, not independent verification by GCC-COS.** Nine EPD observations carry explicit third-party-review metadata; one has incomplete review-type metadata. Original publisher reports have not been independently crosschecked. All product records remain in the manual review queue. There are no invented production carbon values or guessed HS codes.

## Repository contents and data licensing

This branch contains the existing Phase 1–4 application, dashboard, configuration, tests, Windows scripts and CI workflow. Local databases, reviewer credentials, virtual environments, generated exports and machine reports are excluded from Git. Licensed offline input snapshots are intentionally included because tests and the offline demo use them; see [data licenses and provenance](DATA_LICENSES.md). Historical phase reports describe prior cloud runs, not results from a fresh checkout. Regenerate current reports using the commands below.

## Phase 4: human evidence review

An authenticated human-review workflow now separates legacy triage and automatic comparisons from explicit human approval. All **1,241 observations are preserved**. Twenty representative candidates are prepared, but **original publisher access is unestablished because the cloud proxy blocked the checks**. Publisher extraction and licensing fields remain blank rather than copied from secondary data as if verified.

```powershell
.\.venv\Scripts\python.exe scripts/diagnose.py --output reports/phase4/windows-diagnostics.json
.\.venv\Scripts\python.exe -m gcc_cos review-prepare --batch phase4 --size 20
.\.venv\Scripts\python.exe -m gcc_cos review-workbook exports/human-review-phase4.xlsx --batch phase4
.\.venv\Scripts\python.exe -m gcc_cos export exports/verified-only-phase4.xlsx --verified-only
```

The verified-only workbook is currently empty: no real reviewers or approvals were created automatically. Approvals require an operator-provisioned account, personally inspected original evidence, supported comparisons, explicit attestation and an explanation. Rejected, expired, unsupported, revoked and stale records are excluded at export time. Automatic matches, imported review claims, workbook edits and legacy “accepted” labels never grant eligibility.

Use the **Human evidence review** dashboard tab after starting on loopback:

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1
```

See [complete Phase 4 beginner instructions](PHASE4.md) for account provisioning, permitted evidence import, diagnostics and exact Windows commands, and the [actual Phase 4 results](examples/phase4/REPORT.md) for access blockers and limitations. Native Windows execution remains untested. Publisher-host additions were saved as a network draft; review/save and publish in environment settings before retrying access. That does not establish publisher licensing permission.

## Phase 3 update

The original **1,236 observations were audited without deletion or merging**. Three additional individually reusable construction EPD files add five historical/module observations: the collection now contains **1,241 observations**, **1,231 distinct manufacturer/product names**, and **10 source datasets**. Unique SKUs have not been established. No observation has been independently verified against its original publisher document.

The audit identifies four repeated-footprint pairs with different original report URLs and separate groups of lifecycle modules. These are review candidates, not automatic duplicates to remove. It checks pinned archive hashes, reconstructed source fields, attribution and declared reuse terms. Four newly collected observations come from expired EPDs and remain flagged. No new steel/glass/vehicle/clothing/furniture/general-appliance records are claimed.

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase3/sources.json ingest --manifest examples/phase3/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos audit --output-dir reports/phase3 --workbook exports/products-phase3.xlsx
```

Run the Phase 2 collection below first if your database is empty. The audit workbook includes Product audit, Source verification, Coverage and Duplicate review sheets alongside original records and licenses. Audit classes distinguish published third-party data and unverified records; import status labels or manual acceptance cannot establish independent verification. No independent primary-document verification workflow has been implemented.

See [Windows setup and testing](WINDOWS.md) and the [Phase 3 evidence/coverage report](examples/phase3/REPORT.md). PowerShell wrappers and native Windows/Linux GitHub Actions jobs are provided; **Windows execution and those CI jobs have not been run in this cloud session**.

For another category, generate a disabled, permission-gated mapping template:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos source-template vehicles reports/vehicle-source.json
```

Templates also support cement, steel, aluminum, glass, electronics, appliances, furniture and clothing. They contain no carbon values, source URL, license or reuse permission. Configure a real authorized document and its exact schema before enabling one. Input `data_kind` must distinguish genuine product footprints from generic factors; a template is not evidence of collected coverage.

The dashboard adds original-source links, selected-record details, warning filters and a Quality and verification tab. CLI record/export filters now include `--warnings-only`, `--warning ISSUE_CODE` and `--hs6 CODE`. HS filtering does not create or justify a classification.

## 1. Install on Windows with VS Code

Install **Python 3.12 (64-bit)** and select “Add Python to PATH”. Install Git and VS Code. Open PowerShell or CMD:

```powershell
git clone https://github.com/MuhammadHussainHashim/GCC-COS.git
cd GCC-COS
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
```

If you already have this repository, open its existing folder; skip cloning it. In VS Code choose **Python: Select Interpreter**, then `.venv\Scripts\python.exe`. Run every command below from the repository root. Using the Python executable directly avoids PowerShell activation-policy problems.

These commands were checked against the CLI and Python packaging configuration. **Execution was tested on Linux/Python 3.12, not native Windows.** On Linux/macOS create the environment with `python3 -m venv .venv` and replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.

## 2. Collect real product records

### Download from the tested public sources

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --source all
.\.venv\Scripts\python.exe -m gcc_cos revalidate
.\.venv\Scripts\python.exe -m gcc_cos sources
```

This downloads seven pinned, checksum-verified public files: one Boavizta CSV and six EPD JSON datasets. A first run inserts 1,236 observations; repeating it adds zero records and reports duplicates. Lifecycle modules remain separate, so an observation is not always a distinct product. The dataset is pinned for reproducibility; it does not claim the latest product coverage.

If your network blocks the downloads, use the exact attributed originals bundled in this repository:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --manifest examples/phase2/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos revalidate
```

The manifest mode performs **no network requests** and still checks source permissions and SHA-256. Live and offline paths share the same source IDs and bytes, so switching between them does not create duplicate records.

### Export the actual product records

```powershell
.\.venv\Scripts\python.exe -m gcc_cos export exports/products.xlsx --products-only
.\.venv\Scripts\python.exe -m gcc_cos export exports/products.csv --products-only
.\.venv\Scripts\python.exe -m gcc_cos export exports/products.sqlite --products-only
```

Open `exports/products.xlsx` in Excel. It contains Records, Sources and licenses, License notices, Ingestion runs, Review audit and Validation audit sheets. The product-only selection excludes national inventories and generic emission factors. It **does include records awaiting review**; read their issues before analysis.

SQLite export creates a consistent database copy and preserves selected records and their provenance/audit relationships. Raw document files are not embedded in that copy: retain or share the licensed `data/raw` archives separately when necessary. Export never overwrites the active database.

Examples of narrower exports:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos export exports/construction.xlsx --products-only --category construction
.\.venv\Scripts\python.exe -m gcc_cos export exports/smartphones.xlsx --products-only --search Smartphone
.\.venv\Scripts\python.exe -m gcc_cos records --products-only --review-only --manufacturer Apple
```

Filters also support `--geography`, `--status` and `--verification-status`. Search matches product names, manufacturers, category/subcategory, material, EPD ID and HS6. Exact manufacturer/category filters preserve original source spellings.

## 3. Launch the dashboard

```powershell
.\.venv\Scripts\python.exe -m streamlit run dashboard.py
```

Open the local address printed by Streamlit. Select **Products only**, enter search text, and filter by category, manufacturer, geography, review status and verification status. CSV and Excel download buttons export exactly the current selection. Other tabs show source status, ingestion history, the manual review queue and archived-document metadata.

The dashboard uses `data/carbon.sqlite`. It is a trusted local application with no login system; do not expose it publicly. Quality checks and review acceptance do not certify carbon values.

## 4. Which sources actually worked?

| Source | Actual collected coverage | Status |
| --- | --- | --- |
| Boavizta Environmental Footprint Data | 1,226 electronics PCF observations, including 50 smartphones | Live CSV connector tested; manufacturer-reported values obtained through a licensed secondary database |
| Public ILCD construction EPD mirror (`ocni-dtu/epdx`) | 10 module observations from 6 EPD datasets | Live JSON connector tested; concrete, concrete paving, aluminum profiles and cement-based insulation foam |
| OWID / Global Carbon Budget | 3 national cement-process totals | Phase 1 connector retained; these are not product factors |
| Direct ÖKOBAUDAT publication/terms page | None directly | HTTP 403 in this cloud environment; mirror collection is labeled separately |
| UK Government GHG conversion factors | None | Official publication page returned HTTP 403; no workbook connector claimed |
| US EPA hub | None | Official hub page returned HTTP 403; no factor connector claimed |
| US LCA Commons | None | Dataset-specific API connector remains unimplemented |
| Plain cement, steel and glass product EPDs | None | No reusable product datasets collected yet |
| Vehicles, clothing, furniture and general appliances | None | Explicitly pending registry categories, not working data connectors |
| Ecochain and carbon calculators | None | Methodology references only; extraction disabled |

Electronics coverage includes laptops, desktops, monitors, smartphones, tablets, servers, printers, drives and limited home/IoT devices. This is not general vehicle, appliance or clothing coverage. Manufacturers include Dell, Lenovo, HP, Apple, Google, Microsoft, Seagate, Lexmark, Samsung, Asus and Fairphone.

Construction datasets include Heidelberg Materials Precast Denmark, Holcim Germany, Rinn, Höfer Metall Technik, Master Builders Solutions and Skagen Cement Støberi. Some declarations represent manufacturer product averages or families rather than a unique SKU. Their lifecycle scopes and representativeness are retained; do not compare them indiscriminately.

See [Phase 2 validation and limitations](examples/phase2/VALIDATION.md) for exact counts, hashes, source failures and checks. [Phase 1 validation](examples/VALIDATION.md) is historical.

## 5. Evidence, licensing and scientific limits

Each product observation retains product/manufacturer, original value and unit, declared quantity/unit, publication date **as supplied**, geography and its meaning, lifecycle module/boundary, source URL and original report URL, license, attribution, document hash, reference-year/validity metadata, review claims, raw row or JSON evidence, normalized factors and quality issues. Missing dates/geographies remain missing. A partial date such as “November 2020” is never expanded into an invented day.

- **Boavizta:** database licensed under **ODbL 1.0**, individual contents under **DbCL 1.0**. Attribution and applicable share-alike obligations apply to the derived database and redistributed exports. Read [the upstream README](examples/phase2/Boavizta-README.md). Boavizta expressly warns against accurate impact evaluations or comparing manufacturers; these limitations are attached to every relevant record. This license does not grant permission to redistribute manufacturers’ PDF documents; none are bundled or scraped.
- **Construction EPD datasets:** permission is checked inside each individual JSON: `licenseType` must be **“Free of charge for all users and uses”**, and access restrictions must explicitly be **“None”**. The copyright owner, registration and complete license metadata are preserved. The mirror repository’s software MIT license is **not** treated as a data license. Source-specific terms remain attached to each record; these are not claimed to be CC0 datasets.
- [Exact source commits, file hashes and paths](examples/phase2/provenance.json) are retained. Bundled originals are real source data, not synthetic examples.

Data kinds distinguish `published_product_footprint`, `verified_product_footprint`, `published_generic_factor`, `calculated_value`, `unverified_estimate` and `published_inventory`. Current product imports use `published_product_footprint`. Review declarations are recorded separately; none is automatically promoted to independently verified status.

### Normalization

The application keeps the published value/unit unchanged and records calculated normalizations with their formulas and inputs. Only explicit CO₂-equivalent numerator units are accepted for product normalization. An unknown gas/GWP indicator is never substituted for GWP-total.

- Electronics: the licensed schema defines total lifecycle kg CO₂e for one product, allowing kg CO₂e/item. A per-kg factor additionally needs a positive explicitly reported product weight and unit evidence. Use/lifetime assumptions remain attached.
- EPDs: divide by the explicitly declared quantity to obtain kg CO₂e/kg, /m² or /m³. Optional mass conversions require dimensioned density or area-mass data. Ambiguous inverse “conversion to 1 kg” fields are not used.
- A paving-stone source has contradictory density, thickness and area-mass metadata. Its published per-area result remains available; the optional per-kg conversion is suppressed and an issue is raised. No unit typo is silently corrected.
- A1, A2 and A3 observations remain separate. Module D credits are never added to an A1–A3 result, and a manufacturing-only result is never labeled full lifecycle. Old and new GWP methods remain distinct by method ID.

Run `revalidate` after updating validation logic and before exporting an existing database. Changes to derived checks/factors are audited without changing original evidence. Unchanged manual decisions survive; changed results return to review. Invalid numeric records cannot be manually accepted.

### HS6 and manual review

No HS6 code is guessed from broad labels such as “cement”, “phone” or “aluminum”. `config/hs_rules.json` starts empty. An assignment requires a single exact-name rule with a six-digit code, the tariff edition and a real supporting classification reference. Missing or ambiguous matches enter the review queue. Product-family matches must first be checked for applicability. Inventory totals have no product HS classification.

Review a record in the dashboard or use:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos review 1 --reviewer "Your Name" --decision accepted --note "Evidence checked; record limitations retained"
```

This records a decision and note; it does not erase warnings, independently verify a report, or assign an HS code.

## 6. Tests and the original cement demo

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

All 28 original tests remain, with additional product, license-gating, normalization, revalidation, filtered export and dashboard tests. Synthetic values exist only in clearly labeled tests and isolated temporary databases. Real EPD/PCF regression tests use attributed files in `examples/phase2`.

The Phase 1 cement demonstration still works in a separate database:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/cement-registry.json --db data/demo.sqlite ingest --source owid-cement-snapshot --file examples/cement-source.csv
.\.venv\Scripts\python.exe -m gcc_cos --db data/demo.sqlite export exports/cement-inventories.xlsx
```

Those three observations are annual national CO₂ totals, not footprints per bag or tonne of cement.

## 7. Add sources safely

`config/sources.json` contains the full registry; `examples/phase2/sources.json` selects only the seven tested product files. Sources need a specific document URL, explicit permission/license evidence, attribution, approved HTTPS hosts, format, tested mapping and status. Public visibility alone is insufficient. Disabled entries do not imply working connectors or established reuse rights.

The original mapped CSV/XLSX/JSON and PDF-text workflows remain. `gcc_cos/ingest.py` implements source adapters; `gcc_cos/products.py` handles Boavizta and the supported ILCD+EPD JSON subset. PDFs still require human table interpretation; no general PDF/OCR footprint extractor is claimed.

Authorized HTML-index discovery remains available through `discover --source SOURCE_ID`; configure `discovery_document` with its URL, approved hosts and documented permission first. Discovered links are always disabled pending their own license and mapping review. No general web crawler or JavaScript catalogue connector is implemented.

Downloads honor robots rules/delays, HTTPS verification, host approvals, size limits and checksums. Failed sources roll back their records and record an error; other sources continue, with a nonzero batch exit code if an active source fails. A missing/denying robots response blocks collection except explicit 404/410. Do not run overlapping batches against a publisher or disable integrity checks to accept changed files.

Raw documents and databases live in `data/`; exports live in `exports/`. These generated folders are Git-ignored. Back up databases together with raw documents. Exact duplicate detection includes source/document/row evidence. Updated documents or distinct configurations may legitimately yield new observations; semantic merging across publications is not automated.

## 8. Next work

Direct publisher authentication/access and precise reuse terms are still needed before implementing further UK/EPA/ÖKOBAUDAT/LCA Commons sources. Next priorities are reusable plain cement, steel and glass EPDs; original-report crosschecks; explicit product configurations and uncertainty; then licensed vehicle, clothing, furniture and appliance data. API-specific adapters, native Windows validation, general PDF table extraction, an official versioned HS taxonomy, stronger concurrency and multi-user authentication remain incomplete.
