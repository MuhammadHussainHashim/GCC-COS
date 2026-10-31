# Authentic Phase 2 source snapshots

Publication note: this is historical documentation. Machine-generated JSON/CSV reports are not versioned; regenerate current results with the audit, diagnostic and smoke commands in the root instructions. Licensed source inputs and provenance manifests remain versioned.
These files are real source data, not synthetic fixtures.

- `boavizta-products.csv` is the complete pinned Boavizta English-language dataset, unmodified. Its database license is ODbL 1.0, individual contents DbCL 1.0; see `Boavizta-README.md` for attribution, terms and limitations. Manufacturer PDFs are not included.
- `epd/*.json` are unmodified public ILCD+EPD datasets from the pinned `ocni-dtu/epdx` mirror. Only datasets explicitly stating “Free of charge for all users and uses” and access restrictions “None” were selected. Copyright owner, original source and review metadata remain in each document. No rights are inferred from the mirror's software license.
- `sources.json`, `local-files.json` and `provenance.json` identify sources, license evidence, attribution, original locations, commits, hashes and local snapshots.
- `collection-summary.json` is a measured collection summary, not a source of carbon factors.

Boavizta-derived data redistributed from this collection remains subject to its ODbL/DbCL obligations. Independent EPD datasets retain their per-document terms. Always retain attribution and license notices when sharing exports. This collection does not license original manufacturer PDF documents.

See the root README for one-command live/offline collection and export. `VALIDATION.md` records the actual validation outcome and limitations.
