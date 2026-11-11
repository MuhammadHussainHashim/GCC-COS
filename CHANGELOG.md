# Changelog

## 1.3.0 — Calculator refinements (2026-11-11)

Added after reviewing published descriptions of other calculators (see `docs/CALCULATOR.md`):
- Use phase versus making split, from the use-phase share each source reports (1,151 of the 1,226 electronics records report one).
- Biggest line and each line's share of the total; a bar chart of lines in the dashboard.
- Per year of use (from source-assumed lifetimes) and per person (`--people`).
- Same-manufacturer comparison for a specific product; wide-range flag for medians.

Not added because no sourced data exists in the project: transport by route, household energy and travel, "km driven" style equivalents.

Checked on Linux / Python 3.13: 178 of 178 tests pass; `ruff` clean. Windows untested.

## 1.2.0 — Calculator, layer 3 (2026-11-11)

### Added
- `gcc_cos/calculator.py`: products and quantities in, kg CO2e out. A line uses one source record, or the median of all source records for a product type or HS code, with the lowest and highest record shown.
- **Calculator** dashboard tab (pick products one by one, or upload a CSV basket; CSV and Excel downloads) and a `calculate` command.
- Two sample baskets in `examples/calculator/` and `docs/CALCULATOR.md`.

### How it stays honest
- Lines without data return "no value", are left out of the total, and mark the result INCOMPLETE.
- Every result carries NOT VERIFIED warnings for footprints and HS links.
- Totals are kept separate per lifecycle scope; transport is not included.

### Checked (Linux, Python 3.13)
- 168 of 168 tests pass; `ruff` reports no issues. The sample company basket was run against the 1,241 bundled records.
- Native Windows execution remains untested.

## 1.1.0 — HS codes, layer 2 (2026-11-11)

### Added
- HS 2022 code list (5,613 six-digit codes) in `reference/hs2022/`, with source, checksum and PDDL license recorded.
- Product-type HS mappings in `config/hs_mappings.json`. **All are marked `proposed_not_verified`.** 1,177 of the 1,241 bundled records get a code (805 at 6 digits, 372 at heading level only); 64 stay without a code, each with a written reason.
- HS columns in the dashboard, CSV/Excel exports and `records` output; an **HS codes** dashboard tab; `hs-lookup` and `hs-coverage` commands; `--hs` filter accepting 2, 4 or 6 digits.
- `docs/HS_CODES.md`, including how to replace a proposed mapping with a verified one.

### Not changed
- Stored records, carbon values, sources and licenses. HS columns are added when records are shown or exported.

### Checked (Linux, Python 3.13)
- 135 of 135 tests pass; `ruff` reports no issues. The HS tab was opened in a browser and rendered without errors.
- Native Windows execution remains untested. No mapping has been checked by a customs authority.

## 1.0.1 — one working copy (2026-11-11)

Merged the two parallel consolidations (the 1.0.0 clean-up and the "source 2" research snapshot) into one branch. No carbon values, source records, licenses or bundled input files were changed.

### Added from the research snapshot
- `research-prepare` command (`gcc_cos/research.py`) and its 4 tests: stages a manufacturer workbook for manual review without loading it into the database.
- `docs/` (project history, data policy, asset catalog, Windows workflow) and `archive/legacy/` (older prototypes, reference only).
- `research/2026-11-10/audit_summary.json` (counts only).

### Deliberately left out
- The three research CSV files (4,146 unverified rows and their duplicate/conflict lists). This repository is public and the right to redistribute those rows is not established. They can be regenerated locally with `research-prepare`.

### Checked (Linux, Python 3.13)
- 115 of 115 tests pass, including the Streamlit dashboard tests; `ruff` reports no issues.
- Offline load of the bundled data gives 1,241 observations.
- Native Windows execution remains untested.

## 1.0.0 — GCC-Final-System (2026-11-11)

Consolidation of the earlier `GCC-COS` repository into one clean repository. No carbon values, source records, licenses or bundled input files were changed; everything under `examples/` is byte-for-byte identical.

### Brought together
- `main` of `GCC-COS`: the Phase 1–4 application, dashboard, registries, tests, Windows scripts and CI workflow.
- The `claude/compassionate-hawking-utocuu` branch, which had never been merged: shared VS Code tasks, launch configurations, settings and extension recommendations, plus the matching README section and `.gitignore` rules.
- `codex/gcc-cos-phase1-4` was already fully contained in `main`; nothing further to take from it.

### Fixed
- Excel export: the formula-escaping step for audit sheets relied on a pandas behaviour that is deprecated and scheduled for removal. It now selects text columns explicitly and behaves the same on pandas 2 and later versions.
- Removed 13 unused imports across `gcc_cos/` and `tests/`.

### Added
- Lint check (`ruff`, real-error rules only) in the CI workflow and `pyproject.toml`.
- Quick start and repository map at the top of the README; clone instructions point to this repository.

### Checked for this release (Linux, Python 3.13)
- 107 of 111 tests pass. The other 4 are the Streamlit dashboard tests, which could not run in the build environment because Streamlit was not installed there; they are unchanged and run in CI.
- Every documented command was run end to end against a fresh database: offline Phase 2 and Phase 3 ingestion (1,241 observations), revalidate, sources, audit, CSV/Excel/SQLite export, review-prepare, review-workbook, verified-only export, source-template, the Phase 1 cement demo, `scripts/diagnose.py` and `scripts/smoke.py`.
- `ruff` (undefined names, unused imports, syntax) and `mypy` report no issues.
- Native Windows execution remains untested, as before.
