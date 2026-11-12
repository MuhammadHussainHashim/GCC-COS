# Data import notes (12 November 2026)

This file records what was found, what was decided and why, during the import of `GCC-carbon-data.xlsx` into the system. It was written while the work was done.

## Starting state

- The job description names `GCC-Final-System.zip` with 112 tests and 1,241 records. The zip held 111 tests. The working repository had already moved on from it: version 1.4.0, 184 tests, HS code layer, calculator, and the CBAM and ADEME product data from the previous job. **Decision:** work in the repository, not the older zip, so nothing already built is lost.
- All 184 tests passed before any change.
- The workbook's CBAM, common-product, HS code, HS-to-NAICS and product-footprint sheets are identical to the previous day's workbook.

## Inconsistencies found in the workbook

1. **Digital-use units.** The "Activity factors" sheet gives the unit of the seven digital-use rows as "use (see source page)". The publisher's file states the unit in each label (per email, per hour of video streaming, per GB). The publisher's unit is stored.
2. **Meal units** (found in the previous job). Ten "Meal with…" rows in "Common products" are listed per kg; the publisher gives them per meal.
3. **Transport unit wording.** The sheet says "km per passenger". The publisher's file says only "km". The stored unit is "per km", with a note that the workbook describes the values as per passenger.
4. **"Country data" has four columns all headed "Year".** They belong to the value on their left. The data was rebuilt from the publisher's files, one row per country and indicator, each with its own year.
5. **"Calculator reference data" has no licence column.** See decision 6.
6. **HS editions differ.** "HS codes" is HS 2022 (5,613 six-digit codes). "HS6 to NAICS" is based on 2017 US import codes (5,376 six-digit codes). The two lists do not match one to one.
7. **"Data to add" row 17** says target values are "In workbook", but they come from carbonfootprint.com and The Nature Conservancy, whose reuse terms are not stated.
8. **About sheet numbering** runs 1, 2, 3, 4, 5, 7, 9, 8, 6. No effect on the data.
9. **CBAM year.** The sheet has a publication date (16 October 2026) but no year column. Year 2026 is stored with that basis.
10. **ADEME values have no year.** The publisher's file states none. The year of the file version (2026) is stored, with the basis written beside it.

## Database design

Product footprints stay in the existing `records` table. Seven new tables hold the other kinds of data, plus one register:

| Table | Holds | Why separate |
| --- | --- | --- |
| `reference_values` | Values published by CN/HS code (UK CBAM defaults) | Regulatory defaults, not product footprints |
| `activity_factors` | Emission factors per activity (per km, per m2 per year, per hour) | A different unit basis from products |
| `country_data` | One row per country and indicator | Per-person and per-kWh country averages |
| `hs_codes` | The HS 2022 code list | A look-up list, so other tables can be joined to it |
| `hs_industry_links` | HS 6-digit to NAICS industry | A link table; holds no emission values |
| `benchmarks` | Published averages and assumptions | Quoted figures with their stated source |
| `airports` | Airports with coordinates | Needed later for flight distances |
| `reference_datasets` | One row per loaded dataset: publisher, licence, checksum, verification state | So every row can be traced |

Rules built into the loader (`gcc_cos/refdata.py`):

- A dataset is a folder with `data.csv` and `SOURCE.json`. The file's checksum must match.
- A dataset without a title, publisher, link, licence, licence link, attribution and verification status is refused.
- A value row without a unit, year, place and kind of value is refused, and then nothing from that file is loaded.
- Every value table has `value_original` + `unit_original` and `value_metric` + `unit_metric` side by side, with the conversion written out.
- Every value row carries `value_kind` (regulatory default value, activity emission factor, per-person country average, country electricity factor, published benchmark or assumption).
- Values are stored as text, exactly as supplied, so no digit is lost to rounding.
- Loading the same dataset twice adds nothing.

## Decisions made on your behalf

1. **Worked in the current repository** (see Starting state).
2. **CBAM values are held twice, on purpose.** The previous job loaded them as records (under `examples/phase5`) so the calculator can use them. This job asked for a separate table. Nothing under `examples/` may be changed, so both stay. The new `reference_values` table is the cleaner home; a later job can switch the calculator to it.
3. **"Common products" stays in the `records` table** (201 rows, loaded in the previous job). It is per-kg and per-item product data, which is what that table is for. The French name is kept in each record's evidence and the geography is FR. Six rows that repeat existing product types remain left out, as instructed then.
4. **CBAM values are loaded as "unverified".** GOV.UK could not be reached on 11 or 12 November 2026 (direct download and page fetch both failed). No value was re-checked, including 73065029, and none was corrected.
5. **Activity factors and country data were rebuilt from the publishers' own files**, not copied from the workbook. All 63 activity values and all 742 country values in the workbook equal the rebuilt ones.
6. **Only the 25 US EPA rows of "Calculator reference data" were loaded.** EPA material is a US government work. The 29 rows from carbonfootprint.com, The Nature Conservancy and WWF-UK were left out: the workbook gives no licence for them and their pages could not be opened. They are listed in `datasets/epa-calculator-reference/SOURCE.json`.
7. **Year, where the source states none:** the year of the published version is stored, with `year_basis` saying so. A year named in the stated source is used when there is one.
8. **Two extra country indicators were added** from the same Our World in Data file: electricity demand and generation per person. Primary energy per person was left out because one of its sources (Energy Institute) has unclear reuse terms.
9. **"World" is stored with code WLD** in `country_data`, as a reference row.
10. **Airports are limited** to large and medium airports with scheduled service and an IATA code (3,245 rows), so exports stay a usable size.
11. **No HS codes were assigned.** The only codes in the new tables are the ones the CBAM source gives. The everyday products and unmapped electronics are listed in `STILL_NEEDED.md` as needing classification by a person.
12. **Commits were not pushed**, as instructed.

## Second pass, after the data sites were allowed (12 November 2026)

- **UK CBAM:** the five GOV.UK pages were downloaded and read by program. All 570 codes and values equal the hand transcription; 73065029 is 2.811. No corrections. The dataset now carries the official 8-digit descriptions and the status "checked against the publisher's pages".
- **US EPA calculator values:** each of the 25 values was found, with its wording, on the EPA pages. Status changed to checked.
- **New table `spend_factors`:** 1,016 US EPA supply chain factors per 2022 US dollar (public domain). Kept separate because per-dollar factors are a different kind of number.
- **New table `product_averages`:** 2,451 AGRIBALYSE foods per kg (Licence Ouverte). Kept in a reference table, not in `records`, because nothing under `examples/` may be changed and the record loader's sources live there.
- **`activity_factors`** gained 2,622 UK government conversion factors for 2026. Only the "kg CO2e" rows with a value are loaded; per-gas rows and blanks are not. Rows given per mile, per tonne or per million litres keep that original and get a per-km, per-kg or per-litre value beside it.
- **Reloading:** a dataset file whose checksum changed now replaces that dataset's older rows.
- **Decision:** PDF-only sources (NEPRA, OGRA, PBS, IPCC, EPA WARM) were not rushed in. Reading tariff slabs out of PDFs by program risks wrong numbers, which breaks the first rule. They are listed in `STILL_NEEDED.md` as reached but not loaded.

## What was tried for each "Data to add" row marked Missing or Partly

Only files hosted on GitHub could be reached. Every other site named in the workbook refused the connection, and so did the second source tried.

| No. | Data | First source tried | Second source tried | Result |
| --- | --- | --- | --- | --- |
| 1 | Diet-type footprints | nature.com (Scarborough 2023) | ora.ox.ac.uk | Blocked; in STILL_NEEDED |
| 2, 9 | Spend-based factors | catalog.data.gov, pasteur.epa.gov | USEPA/supply-chain-factors on GitHub (code only, no factor file) | Not obtained; in STILL_NEEDED |
| 3 | EU CBAM defaults | taxation-customs.ec.europa.eu | eur-lex.europa.eu | Blocked; in STILL_NEEDED |
| 4 | HS codes for products | Not a download | — | Needs classification; in STILL_NEEDED |
| 5 | Energy prices (Pakistan) | nepra.org.pk, ogra.org.pk | api.worldbank.org | Blocked; in STILL_NEEDED |
| 6 | Household energy use | pbs.gov.pk | Our World in Data (reached) | Electricity per person loaded; household figures in STILL_NEEDED |
| 7 | Reduction actions | Depends on 5 | — | EPA assumptions loaded; rest in STILL_NEEDED |
| 8 | Material factors | circularecology.com (ICE) | base-empreinte.ademe.fr, data.ademe.fr | Blocked; in STILL_NEEDED |
| 18, 19, 23, 27 | UK DESNZ conversion factors | gov.uk | assets.publishing.service.gov.uk | Blocked; in STILL_NEEDED |
| 20 | Airports | OurAirports on GitHub | — | **Loaded** |
| 21, 24, 25 | EPA WARM, waste, equivalents | epa.gov | — | Blocked; in STILL_NEEDED |
| 22 | Carbon price | icapcarbonaction.com | ember-energy.org | Blocked; in STILL_NEEDED |
| 28 | Vehicle fuel economy | fueleconomy.gov | — | Blocked; in STILL_NEEDED |
| 31 | 16 impact indicators | EU sites | — | Blocked; in STILL_NEEDED |
| 29, 30, 32, 33 | Offsets, printing, WWF adjustments, government share | Not public, a business decision, or licence unclear | — | In STILL_NEEDED |
| Pakistan fuel factors | ipcc-nggip.iges.or.jp | iea.org | — | Blocked; in STILL_NEEDED |
