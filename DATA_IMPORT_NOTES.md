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
- One workbook note could not be confirmed: the row "Fuel saved by regular vehicle maintenance" says the EPA page also lists 1.6% from a 2024 source. That figure was not found on the page. The value itself (7%) was.
- **New table `spend_factors`:** 1,016 US EPA supply chain factors per 2022 US dollar (public domain). Kept separate because per-dollar factors are a different kind of number.
- **New table `product_averages`:** 2,451 AGRIBALYSE foods per kg (Licence Ouverte). Kept in a reference table, not in `records`, because nothing under `examples/` may be changed and the record loader's sources live there.
- **`activity_factors`** gained 2,622 UK government conversion factors for 2026. Only the "kg CO2e" rows with a value are loaded; per-gas rows and blanks are not. Rows given per mile, per tonne or per million litres keep that original and get a per-km, per-kg or per-litre value beside it.
- **Reloading:** a dataset file whose checksum changed now replaces that dataset's older rows.
- **Decision:** PDF-only sources (NEPRA, OGRA, PBS, IPCC, EPA WARM) were not rushed in. Reading tariff slabs out of PDFs by program risks wrong numbers, which breaks the first rule. They are listed in `STILL_NEEDED.md` as reached but not loaded.

## Third pass (12 November 2026)

- **Pakistan prices (new table `energy_prices`, 30 rows):** NEPRA's uniform residential tariff (S.R.O. 279(I)/2026, approved 11 February 2026), OGRA's domestic gas slabs (effective 1 July 2025, the latest on OGRA's consumer gas page), LPG (1 November 2026) and kerosene (7 November 2026). All four notices are scanned images, so the values were read from the page images by eye and are labelled "transcribed from the scanned notification". Totals printed in the LPG and kerosene notices were checked against their parts.
- **Decision:** the publishers state no licence. The prices were loaded anyway, because they are regulated prices published for the Gazette and you named NEPRA and OGRA as sources; each row says no licence is stated.
- **NEPRA's "applicable tariff" web page** shows 2019–20 rates and was not used.
- **Petrol and diesel** are priced by the Petroleum Division, not in OGRA's notices; listed as still needed.
- **EU CBAM:** EUR-Lex returns an empty page to automated downloads. Fetching it through a headless browser was blocked by this session's safety checks, so it was left for you to download.
- **ICE:** its terms now limit free use to teaching and research, so it was not loaded.
- **Calculator:** now accepts AGRIBALYSE foods (`food`) and the UK conversion factors (as `activity` lines). For the CBAM records under `examples/phase5`, it compares each with the GOV.UK-checked table instead of changing the folder.

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

## Import of 19 November 2026 (version 1.10.0)

Five files were uploaded: `GCC_Carbon_Footprint_Database_2026_1.xlsx`, `GCC_HS_Code_Footprints_2026.xlsx` with its CSV copy `gcc_hs_footprints_2026.csv`, and `GCC_Product_Footprints_Electronics.xlsx` with its CSV copy `gcc_product_footprints_electronics.csv`. Each CSV equals its workbook sheet row for row. Their checksums are in `docs/data-verification/2026-11-19/import_summary.json`. The uploads themselves are not committed; `scripts/build_phase6.py` takes the values from the publishers' files and uses the uploads only to find which rows were offered and to compare numbers.

### What was compared with what the system already holds

| Offered | Already held? | Result |
| --- | --- | --- |
| 728 Boavizta products | Yes, all in `examples/phase2` (same maker and name, same report link) | Not added |
| 1,735 CarbonPDF products | 523 are the same products as held Boavizta records (same report link, or same maker and product name ignoring a leading maker name such as "HP 255 G9" = "255 G9") | 1,212 added; 523 not added |
| 2,622 UK DESNZ 2026 factors | Yes (`uk-desnz-conversion-factors-2026`) | Not added. 2,618 equal; 4 differ only by float noise in the held file (for example 0.13388999999999998 held, 0.13389 offered). The held file was not changed. |
| 213 country electricity factors (Ember via OWID) | Yes (`owid-country-data`, `electricity_carbon_intensity`) | Not added; all 213 equal, same years |
| HS code list (6,940 rows) | Yes (`reference/hs2022`) | Not added; same 6,939 codes plus the "TOTAL" root |
| 38 foods (Poore & Nemecek 2018) | No | Added to `product_averages` |
| 15 electricity-by-technology values | No | Added to `activity_factors` |
| HS-to-factor links | No | 235 direct and country-specific links added to the new table `hs_factor_links`; 558 proxies not added |

### Decisions made on your behalf

1. **Same product, different value.** For 286 of the 523 overlapping products the CarbonPDF value differs from the held Boavizta value (often a newer report edition, for example HP E24 G4 monitor: 250 now, 565 held). These were not added as second records, because you asked for no repeats, and the held records were not changed. They are listed in `docs/data-verification/2026-11-19/carbonpdf-vs-held-boavizta-value-differences.csv` for a person to decide.
2. **Values come from the publishers.** CarbonPDF rows are copied from `pittcps/carbonpdf-dataset` (commit `400e9d8…`), not from the upload; all 1,735 uploaded values equal the publisher's. Food values come from the OWID file at commit `13b8cd7…` (August 2022; OWID emptied the file in February 2023); all 38 equal.
3. **CarbonPDF licence.** The repository's README states none; the AWS Open Data Registry entry for CarbonPDF states CC BY 4.0, and that is recorded.
4. **No year, no place, no HS code invented for CarbonPDF products.** The dataset gives no report year or use location, so those stay blank and the records carry the "missing" warnings. The upload's HS codes and product types were suggested by an AI and were not used; the project's own product-type rules apply as for every other record.
5. **IPCC values partly checked.** ipcc.ch refused the connection. Eight of the fifteen values (coal, gas, biomass, geothermal, hydro, nuclear, onshore wind, oil) equal the Electricity Maps open configuration; the other seven are stored with the note "not re-checked".
6. **Proxy HS links kept out of the database.** `docs/DATA_POLICY.md` says HS blanks must never be filled with guesses. "Proxy (closest available)" links are guesses, so the 558 of them are in `docs/data-verification/2026-11-19/hs-proxy-links.csv` for review. The 233 direct and 2 country-specific links were loaded, labelled as suggested by an AI and not checked by a person; each per-kg value was checked against the linked factor.
7. **Upload's food categories and suggested HS codes on food rows** were made by an AI and are not stored.
8. **The uploads' "Not Included" sheets** name AGRIBALYSE and the US EPA supply chain factors as missing; the system already holds both. The others are added to `STILL_NEEDED.md`.

## Import of 20 November 2026: IPCC Emission Factor Database (version 1.11.0)

One file was uploaded: `IPCC_EFDB_All_Emission_Factors_2026.xlsx` (sha256 `bd239443dde9…`), an export of every record of the IPCC Emission Factor Database (EFDB) made on 19 November 2026. `scripts/build_efdb.py` makes `datasets/ipcc-efdb-2026-11/` from it; the counts and the check are in `docs/data-verification/2026-11-20/efdb-import-summary.json`.

### What was added and what was not

| | Records |
| --- | --- |
| In the upload | 27,566 |
| Repeats: identical to another record in every field except the EF ID, stored once under the lowest EF ID (the others are in `also_listed_as`) | 778 |
| No value, left out | 294 |
| **Added to the new table `inventory_factors`** | **26,494** |

The system held no EFDB data before, so nothing else was a repeat. (The 15 IPCC AR5 electricity values loaded on 19 November come from a different IPCC report.)

### Decisions made on your behalf

1. **A table of its own.** EFDB records are per-gas inventory parameters (for example kg CH4 per TJ, t dry matter per ha, or a fraction), not CO2e and not product footprints; the export says so itself. They are stored in `inventory_factors`, values and units exactly as given, and are not used by the calculator or added to any footprint total. Turning them into CO2e needs a chosen GWP set, which is a method decision for a person.
2. **Text lost in the export was restored from the EFDB website.** A check against the website showed that the export lost text: descriptions left blank, units left blank, and characters such as "≤", "₂" or "°" turned into "?" (for example a value "? 0.001" that the website gives as a bounded value). 3,768 records had at least one such gap; 3,768 were fetched from the EFDB website and 3,557 were repaired. Fields restored: abatement 28, conditions 419, description 3,044, other_properties 32, region 53, technologies 134, unit_original 78, value_original 12. A field with "?" was replaced only when the website text equals the exported text with each "?" standing for one or more characters, and every restored field is named in the record's `fixed_from_efdb_site` column. Left as exported: 21 records with no description (the website has none either, or did not answer), 46 with no unit and 3 with "?" still in the value or unit.
3. **Checked against the publisher.** After the repair, 300 records chosen at random were compared with the EFDB website field by field: 300 equal in value and unit, gas, description and type of parameter; 0 differ; 0 could not be reached. The differences are listed in the summary file.
4. **Licence.** The EFDB website states no licence. It is published IPCC material, and the EFDB says its content has not been subject to formal IPCC review. The records are kept for the project's own work; confirm reuse terms with the IPCC before publishing them outside the project.
5. **Sector names** (`sector_2006`) are read from the first digit of the IPCC 2006 category (1 Energy, 2 Industrial processes and product use, 3 Agriculture, forestry and other land use, 4 Waste). Records without a 2006 category say "Not stated".
