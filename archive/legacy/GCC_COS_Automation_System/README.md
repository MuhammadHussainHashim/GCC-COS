# GCC Carbon Operating System (COS) — Starter Automation System

A Windows/VS Code starter app for the Green Carbon Corridor (GCC) data workflow. It imports product and emissions datasets, preserves provenance, validates HS codes and units, supports a limited UN Comtrade API preview, stores records in SQLite, and exposes review/export tools.

## Important scope note
This is a functional starter prototype, not an autonomous source of truth for every product footprint worldwide. There is no single open API that provides every HS code, every product footprint, every lifecycle boundary, and verified facility data. Data sources have different licences, units, scopes, and coverage. The app deliberately flags uncertain records for human review and never invents missing carbon factors.

## Run on Windows in VS Code
1. Install Python 3.11+ and VS Code.
2. Extract this folder and open it in VS Code.
3. Open Terminal > New Terminal.
4. Create a virtual environment:
   ```powershell
   py -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
   If PowerShell blocks activation, use:
   ```powershell
   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
   .\.venv\Scripts\Activate.ps1
   ```
5. Install packages:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
6. Start the application:
   ```powershell
   streamlit run app/main.py
   ```
7. Streamlit opens a local browser page. The SQLite database is created at `data/cos.db`.

## Main features
- Import CSV and Excel files into the review pipeline.
- Map common column names automatically; manually map columns when the source differs.
- Preserve source file, import time, raw row JSON, source URL, units, geography, year, and review status.
- Validate HS code shape (2/4/6/8/10 digits), but do not claim that a code is valid in a national tariff schedule unless checked against the relevant official nomenclature/version.
- Import carbon factors with original value and unit retained.
- Limited UN Comtrade preview fetch for trade statistics. Trade values/quantities are NOT carbon footprints.
- Search, filter, review, approve/reject, and export records.
- Store source registry and audit events in SQLite.
- No automatic conversion of unlike functional units. Conversion must be supported by a known dimension and valid product data.

## Data-source guidance
- UN Comtrade: trade statistics and HS-coded commodity information; not a product carbon-footprint database. API access and limits vary. See https://uncomtrade.org/docs/un-comtrade-api/
- UK Government GHG Conversion Factors 2026: useful for relevant activity-based emissions reporting, especially UK-context activity factors; not automatically a Pakistan-specific product footprint. https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026
- Verra VM0044: methodology reference for eligible biochar carbon removal projects; this is a project methodology, not a generic product-factor table. https://verra.org/methodologies/vm0044-biochar-utilization-in-soil-and-non-soil-applications-v1-2/
- World Customs Organization (WCO): official HS nomenclature authority; full current nomenclature may be subject to access/licensing conditions. Verify exact edition and national extensions before using codes operationally.

## Suggested input schema
`product_name, hs_code, sector, country, footprint_value, footprint_unit, functional_unit, boundary, data_year, source_name, source_url, evidence_type, notes`

For an emissions factor, make `footprint_value` the factor value, `footprint_unit` the impact unit such as `kg CO2e`, and `functional_unit` the denominator basis such as `per kg product`, `per tonne product`, or `per kWh`. Use `evidence_type` values such as `measured`, `published_factor`, `modelled`, `estimated`, or `unknown`.

## Review statuses
- `pending`: imported but not approved.
- `approved`: reviewed and accepted for a defined use.
- `rejected`: not suitable for the current use.
- `needs_source`: provenance is missing or weak.
- `needs_unit_review`: unit/boundary unclear.

Approval in this app means an internal data-review decision only. It is not independent verification, accreditation, or carbon-credit certification.

## Security and responsible operation
- Never commit API keys or `.env` to GitHub.
- Respect source terms, robots rules, rate limits, licences, and privacy.
- Prefer official APIs/downloads over scraping.
- Do not scrape login-protected pages or bypass controls.
- Keep raw files and original source values unchanged.
- Back up `data/cos.db` and imported source files.

## Roadmap
1. Add source-specific connectors only after their API/licence is checked.
2. Add a reviewed HS nomenclature table by edition and country.
3. Add a factor-specific unit dictionary and safe conversions.
4. Add a cement pilot module using real plant activity data.
5. Add MRV workflows for biochar only under a selected methodology.
6. Add authentication, roles, scheduled jobs, backup, deployment and external verification integration before production use.
