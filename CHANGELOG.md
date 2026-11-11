# Changelog

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
