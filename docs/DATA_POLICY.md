# Carbon evidence, quality and release policy

This repository is intentionally conservative. A footprint must be traceable
from an exact source document and product/configuration to the value, unit,
functional unit, geography, lifecycle boundary, date, applicable GWP method,
reuse permission, and reviewer decision. Missing cells stay missing.

## Trust levels

1. **Research import (unverified):** spreadsheet extracts, chat-supplied
   numbers, OCR output, model estimates and unexamined URLs. These belong in
   `research/`; no public-facing verified-only calculation may consume them.
2. **Source-reported with provenance:** a pinned authorized dataset, checksum
   and original row. This supports reproducible inspection, not automatically
   a verified carbon claim.
3. **Human-reviewed original report:** an authorized reviewer inspects the
   original publisher evidence, source validity, functional unit, expiry,
   boundaries and documented permission, then attests. Even this does not mean
   a government or third-party certification.
4. **Externally assured/verified:** requires a specific, independently
   identifiable assurance statement, scope and period. Do not infer it.

## Non-negotiable separation

- National annual emissions cannot serve as product intensity without a
  documented denominator and methodology.
- kg CO₂, kg CO₂e, kg CO₂e/kg, kg CO₂e/item, kg CO₂e/m² and kg CO₂e/kWh
  are different measures. No implicit conversion from one to another.
- EPD A1–A3, full lifecycle, operational, end-of-life and module D may not
  be combined without an explicit compatible method.
- Variant differences (storage, size, geography, use lifetime, accounting
  scenario) are not duplicates merely because the model name matches.
- HS6 is a customs classification, not an emissions factor. The 5,613-row
  historical HS file has *indicative estimates* and no source-level validation
  for every code. The expanded-unit workbook correctly leaves ungrounded
  factors blank; **never repopulate those blanks with guessed defaults**.
- A source listing, search hit, OCR result, product brochure or calculation
  website is insufficient to claim a verified footprint.
- Research results from the 4,146-row workbook are kept in review on the
  user's own PC with the exact original report links, where provided. The tool flags candidates; it
  does not remove or reconcile values automatically.
- CSV review exports escape formula-looking text before Excel opens it.
  The original workbook remains the checksum-protected source of raw cells.

## 11 November 2026 research audit

`research/2026-11-10/audit_summary.json` records the exact workbook hash and
row counts, including 4,146 preserved rows, 77 possible duplicate rows,
159 same-report conflict rows, and 21 missing total values. All 4,146 have
`pending_original_report_review`. **No row is independently verified by this
consolidation.** The audit is reproducible with `research-prepare`; its input
spreadsheet is kept separate from this Git repository pending permission review.

## Security and publication

- The research compilation rows are kept **out of this repository** (it is
  public) until third-party rights are established. Never upload API keys, reviewer
  passwords, `.env` files, local databases or customer information.
- Treat the old Windows utility tools as archived historical source, not
  supported security-checked production components.
- Preserve upstream license and attribution statements already provided in
  `DATA_LICENSES.md`. Do not presume a publisher PDF is freely redistributable.
- The dashboard is for localhost. Internet deployment needs authentication,
  authorization, logging privacy review and application hardening.
- Do not present counts as coverage of every product/HS code/company in the
  world. Keep coverage gaps explicit and update sources only by permissioned,
  documented connectors.
