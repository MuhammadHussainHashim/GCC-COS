# Bundled data licenses and publication review

This notice covers data bundled for offline demonstrations and regression tests. It does not assign a new license to GCC-COS application code or override any upstream data terms. Dependencies retain their own licenses.

| Included input | Source and applicable terms | Attribution/provenance |
| --- | --- | --- |
| `examples/cement-source.csv` | Three-row selection from OWID's CO₂ dataset / Global Carbon Budget (2025); CC BY 4.0 as identified by OWID and upstream metadata | Andrew, R. M. & Peters, G. P. (2025), Global Carbon Project fossil CO₂ emissions dataset (2025v15), doi:10.5281/zenodo.17417124; processing by Our World in Data. `examples/provenance.json`, `OWID-README.md`, `GCP-license-metadata.yml` and `cement-codebook.csv` retain selection, definitions, source and attribution. Values are unchanged national inventories, not product factors. |
| `examples/phase2/boavizta-products.csv` | Unmodified pinned Boavizta database, ODbL 1.0; individual contents DbCL 1.0 | Boavizta Environmental Footprint Data contributors and the per-row manufacturers/reports. `examples/phase2/Boavizta-README.md`, `sources.json` and `provenance.json` preserve terms, attribution, source commit and SHA-256. Retain attribution and applicable share-alike obligations when distributing the database or derivatives. |
| Nine `examples/phase2/epd/*.json` and `examples/phase3/epd/*.json` files (six plus three) | Each selected ILCD+EPD document explicitly declares “Free of charge for all users and uses” and access restrictions “None” | Original copyright owners, registration numbers, original publisher references and review metadata are retained in each unmodified document and the source/provenance registries. These are individually declared data permissions, not CC0. The mirror repository's software MIT license is **not** asserted as a license for EPD data. |
| `tests/fixtures/synthetic.csv` and test-generated data | Clearly labeled synthetic test inputs, not authentic footprint factors | Restricted to isolated tests/temporary databases; not ingested as production data. |

The Boavizta data is provided as an attributable, machine-readable database under its upstream terms; no blanket permissive license is applied to it. ODbL/DbCL references: https://opendatacommons.org/licenses/odbl/1-0/ and https://opendatacommons.org/licenses/dbcl/1-0/. The complete pinned database and attribution are provided, and derived exports retain license notices. Consult the upstream terms for attribution, notice and share-alike obligations.

The EPD files were selected individually based on their embedded permission metadata. That metadata is retained as evidence of declared permission; it is not a legal opinion or an independent revalidation of original publisher terms. Expired declarations remain labeled historical. A public mirror's software license does not grant rights to unrelated source materials.

No original manufacturer PDFs, presentations, paywalled datasets, or purportedly independently verified factors are bundled. Links to original publisher documents do not establish permission to redistribute those documents. Importing publisher evidence requires documented permissions and human review; the initial verified-only export is empty.

Publication review excludes local databases (including reviewer credentials), original-document caches, virtual environments, generated Excel/CSV/SQLite exports, temporary reports, machine diagnostics and access logs. Historical Markdown reports remain as dated documentation; their runtime report files are regenerated with the documented commands and are not application inputs.

## Reproduce the input checks

From the repository root, run the existing tests and `python scripts/smoke.py` using the installed project interpreter. Tests verify pinned input checksums, per-document EPD permission gates, provenance, source attribution and unchanged record behavior. Application-level checks preserve declared terms; they do not establish legal rights beyond that evidence or independently verify product claims.
