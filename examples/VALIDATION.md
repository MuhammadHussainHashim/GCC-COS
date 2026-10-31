# MVP validation — 30 October 2026

Executed in `/workspace/GCC-COS` on Linux, Python 3.12.14. Native Windows execution has not been tested.

## Results

- `python -m pytest -q`: **28 passed**, no skipped or expected-failure tests.
- `python -m pip check`: no broken requirements.
- Live `python -m gcc_cos ingest --source all`: **3 inserted** from `owid-cement`; seven disabled registry entries skipped. No publisher-specific success is inferred from a registry entry.
- Repeated live `ingest --source owid-cement`: **0 inserted, 3 duplicates**.
- Offline excerpt import into a separate database: **3 inserted**, then **0 inserted, 3 duplicates**. These are the same underlying observations, not three additional authentic observations.
- Default live database: **3 authentic observations**, **0 verified product footprints**, **0 product-level emission factors**. All three are `published_inventory`, flagged `needs_review` because annual country totals are not product factors.
- CSV and Excel generated successfully: `exports/cement.csv`, `exports/cement.xlsx`. Excel ingestion/review audit sheets included.
- Streamlit AppTest: both empty and three-record dashboards executed without exceptions.
- Local Streamlit service started successfully; HTTP health returned `ok` and root HTML served. This verifies startup in this instance, not publication or fresh-task restoration.

## Evidence and reuse

Live ingestion downloaded the commit-pinned OWID CSV using the implemented downloader, checked robots.txt (absent/404), preserved TLS verification, validated the configured SHA-256, selected three 2023 country records and archived the original document. Row-level exported evidence contains only country/year/cement_co2; other indicators are not redistributed in the record exports.

The original dataset SHA-256 is `7f78e2b218ce4bb8c538bbec04fdc9a7982e8d40bff972e650df603899edd5f6`. Exact URL, excerpt checksum and selection are in `provenance.json`. The original codebook describes `cement_co2` as annual CO₂ emissions from cement, unit `million tonnes (Mt)`; see `cement-codebook.csv`. The standardized unit label `Mt CO2` qualifies that mass unit with its gas. Only mass scaling to kg CO₂ is performed.

OWID’s README permits reuse of its work under CC BY 4.0 and requires checking upstream licenses. The inspected upstream OWID/GCP snapshot metadata explicitly identifies CC BY 4.0 and credits Andrew & Peters (2025). Copies of that metadata and OWID’s README are retained here with attribution. The metadata license URL points to an older Zenodo record; the exact upstream metadata is preserved rather than silently corrected.

## Source status

| Source | Observed result |
| --- | --- |
| OWID / Global Carbon Budget cement series | Live download and ingestion passed; 3 national annual totals |
| US EPA supply-chain-factors official GitHub | Read access and MIT-licensed generation code inspected; no published factor table ingested |
| UK Government 2025 factors publication page | HTTP 403 in this environment; workbook not downloaded or tested |
| US LCA Commons | No live connector implemented/tested |
| EPD / open LCA / manufacturer reports | Generic file infrastructure only; no live publisher-specific examples tested |
| Ecochain / calculators | No extraction or reuse permission asserted; reference-only |

## Remaining work

The system is a working collection infrastructure MVP. The intended worldwide product-factor database still needs explicitly reusable product/EPD sources, publisher-specific mappings and scientific review. PDF support extracts text only; numerical interpretation/OCR is unfinished. HTML link discovery has synthetic functional coverage but has not been tested on a real publisher index. HS rules require real tariff evidence and manual review; the cement inventory demo deliberately assigns none. Configured code and unit checks do not independently verify any carbon value.

## Reusable cloud configuration

`install_script` and `start_skill` were saved successfully to the environment configuration draft. They reproduce dependency preparation and describe service startup/readiness. Saving did not publish the environment. Review and save the changes in environment settings, then publish when desired. Publication and restoration in a fresh task have not been validated.
