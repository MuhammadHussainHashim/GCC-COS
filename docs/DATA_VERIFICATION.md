# Data verification report (16 November 2026)

What was checked, how, and what was found. "Matches" below means **our copy equals the publisher's file or page today**. It does not mean anyone has confirmed that the publisher's number is scientifically right.

Raw results: `docs/data-verification/publisher-files.json` and `docs/data-verification/manufacturer-reports.json`.

## 1. Every bundled value against a fresh download of its publisher's file

Each file was downloaded again and read by a separate checker (`scripts/verify_data.py`), not by the code that built the datasets.

| Data | Compared with | Values compared | Differences |
|---|---|---|---|
| UK government conversion factors 2026 (2,622 rows) | GOV.UK flat file, every row | 15,732 | 0 |
| AGRIBALYSE 3.2 foods (2,451) | data.ademe.fr file, every food | 12,255 | 0 |
| US EPA supply chain factors (1,016) | EPA ScienceHub file, every industry | 4,064 | 0 |
| Our World in Data country data (1,184) | the two source files, latest year per country | 3,552 | 0 |
| ADEME activity factors (63) | ADEME Impact CO2 values file | 126 | 0 |
| Airports (3,245) | OurAirports file | 16,187 | 0 |
| UK CBAM default values (570) | the five GOV.UK pages, every commodity code | 1,710 | 0 |
| US EPA calculator figures (25) | the two EPA pages (is each number printed there?) | 25 | 0 |
| HS 2022 code list (6,939 codes) | publisher's file, byte for byte | 6,940 | 0 |
| Boavizta product file (1,226) | publisher's file, byte for byte | 1,226 | 0 |
| **Total** | | **61,817** | **0** |

Also confirmed: the publisher files for the UK factors, AGRIBALYSE, EPA factors and Our World in Data have the same checksums as when first downloaded; every metric conversion (÷1000, ÷1,000,000, ÷1.609344, feet × 0.3048) follows from the original value; no publisher row that should be included is missing.

## 2. Every stored record against the file it came from

| Records | Compared with | Values compared | Differences |
|---|---|---|---|
| Boavizta products (1,226) | the row of the Boavizta file each record names | 4,904 | 0 |
| UK CBAM (570) | the GOV.UK-checked table | 1,710 | 0 |
| ADEME everyday products (201) | ADEME values file | 201 | 0 |
| EPD records (15, from 9 documents) | each EPD file, downloaded again | 30 | 0 |
| All 2,012 records have a source, licence, unit and value | | 2,012 | 0 |

## 3. Other checks

- **HS-to-industry links (6,322 pairs):** every pair exists in the published concordance package; every share equals lines ÷ total lines; shares add up to 1 for every code.
- **Pakistan energy prices (30 values):** the five official notices were downloaded again and are unchanged (same checksums). All 30 values and the fixed charges were read a second time from the scanned pages and match. These are still hand-read from scans, and the notices state no reuse licence.
- **HS code mappings (26 product types):** every proposed code exists in the HS 2022 list. The mappings themselves remain **proposed, not verified**: only a customs expert can confirm them.
- **Live dashboard:** its copies of the foods, UK factors, country data, activity factors, prices and records equal the repository data (the only difference is stray spaces in four product names).

## 4. Product footprints against the manufacturers' own reports

`scripts/check_manufacturer_reports.py` downloaded the report each Boavizta product links to and looked for the product's total footprint in its text. This is a screening aid. "Found" means the number is printed in the document next to CO2 or kg; it does not prove the number belongs to the same model and configuration, and it is **not** the human evidence review. No record's status was changed.

| Manufacturer | Products | Number found in the report | Not in the report today | Report removed by the maker | Report could not be opened |
|---|---|---|---|---|---|
| Apple | 91 | 91 | 0 | 0 | 0 |
| Google | 51 | 51 | 0 | 0 | 0 |
| Samsung | 7 | 7 | 0 | 0 | 0 |
| Asus | 2 | 2 | 0 | 0 | 0 |
| Dell | 525 | 300 | 2 | 5 | 218 |
| Lenovo | 365 | 172 | 0 | 0 | 193 |
| HP (including HPE) | 124 | 1 | 4 | 0 | 119 |
| Microsoft | 36 | 4 | 2 | 30 | 0 |
| Seagate | 12 | 4 | 0 | 8 | 0 |
| Fairphone | 2 | 1 | 1 | 0 | 0 |
| Lexmark | 11 | 0 | 0 | 0 | 11 |
| **Total** | **1,226** | **633** | **9** | **43** | **541** |

Second pass (17 November 2026): HP's server sends an incomplete certificate chain (it leaves out DigiCert's public "Global G2 TLS RSA SHA256 2020 CA1" intermediate, which web browsers fetch for themselves). The check was repeated with that public certificate added to the trusted list, with verification left on. Asus's reports had moved to esg.asus.com. That pass found 3 more reports and 4 more mismatches. Archived copies on the Internet Archive could not be used: this environment does not allow web.archive.org.

### Nine records whose number is NOT in the manufacturer's report today

| Product | Value in our data (from Boavizta) | What the report says today |
|---|---|---|
| Dell PowerEdge R6515 | 8,160 kg CO2e | "estimated carbon footprint: 3450 kgCO2e" |
| Dell PowerEdge R7515 | 8,990 kg CO2e | "estimated carbon footprint: 3920 kgCO2e" |
| Microsoft Surface Laptop SE | 101 kg CO2e | lists production 42, transport 2, use 28 kg CO2eq; 101 does not appear |
| Microsoft Surface Pro X | 116 kg CO2e | lists production 137, transport 15, use 21 kg CO2eq; 116 does not appear |
| Fairphone 4 | 49.9 kg CO2e | headline "estimated to be 43 kg CO2 eq."; 49.9 appears only elsewhere in the document |
| HP Chromebook x360 14a | 315 kg CO2e | "125 kg CO2 eq." |
| HP E24m G4 FHD USB-C Conferencing Monitor | 286 kg CO2e | 218 (North America), 200 (Europe), 256 (Asia Pacific) kg CO2e; 286 is the figure in HP's report for the E24mv G4 |
| HP Fortis 14" G10 Chromebook Enterprise | 167 kg CO2e | 160 kg CO2e (range 140 to 200) |
| HP Fortis 14" G10 Chromebook | 167 kg CO2e | 160 kg CO2e (range 140 to 200) |

The likely cause is that the manufacturer replaced the report after Boavizta copied the figure, or that Boavizta used a different configuration. These nine need a person to read the report and decide. They are still in the data, unchanged.

### 584 products that could not be checked

| Reason | Products |
|---|---|
| Dell refuses automated downloads (HTTP 403) | 218 |
| Lenovo refuses automated downloads (HTTP 503) | 193 |
| HP refuses automated downloads (HTTP 503 from www8.hp.com) | 109 |
| Report removed by Microsoft (HTTP 404) | 30 |
| Lexmark site not reachable (server error) | 11 |
| HPE site not reachable (connection error) | 10 |
| Report removed by Seagate (old page now redirects to a general page) | 8 |
| Report removed by Dell (HTTP 404) | 5 |

Dell, Lenovo and HP block automated tools; retrying while posing as a normal browser was deliberately not done. These need a person with a normal web browser, which is what the Phase 4 human evidence review is for. Removed reports can only be checked against an archived copy or a new report from the maker.

## Where each dataset was verified, and on which second platform

The addresses of every source are in `docs/data-verification/where-verified.json`. "Second platform" means a place other than the file the data was copied from. Some are the same publisher's other service; only the World Bank, UN Comtrade (for the HS list), OpenFlights and the manufacturers' reports are separate organisations.

| Data | First check (the publisher's file) | Second platform | Standing |
|---|---|---|---|
| UK government conversion factors 2026 (2,622) | GOV.UK flat file: 15,732 values, 0 differences | GOV.UK full-set workbook (separate file, same publisher): 2,622 of 2,622 agree | Matches the publisher on two files |
| AGRIBALYSE 3.2 foods (2,451) | data.ademe.fr download: 12,255 values, 0 differences | data.ademe.fr query API (same publisher, different service): 2,451 of 2,451 agree | Matches the publisher on two services |
| Our World in Data country data (1,184) | Our World in Data files on GitHub (co2-data, energy-data): 3,552 values, 0 differences | World Bank API (independent estimate, different method): CO2 per person: 158 of 197 countries within 25%; all gases: 125 of 191 within 25% (methods differ). Electricity carbon intensity: no second platform could be reached | Matches the publisher; per-person figures broadly agree with an independent source; electricity figure checked on one platform only |
| UK CBAM default values (570) | GOV.UK sector pages: 1,710 values, 0 differences | GOV.UK content API (same publisher, data feed): 570 of 570 agree | Matches the publisher on two services |
| HS 2022 code list (6,939 codes) | datasets/harmonized-system on GitHub: 6,940 values, 0 differences | UN Comtrade reference list, HS2022 (original publisher): all 6,939 codes and descriptions identical | Matches two platforms |
| ADEME activity factors (63) | ADEME Impact CO2 source file on GitHub: 126 values, 0 differences | ADEME Impact CO2 live API (same publisher, live service): transport 47 of 47 agree; heating 9 of 9 agree; digital use not checked on a second platform | Matches the publisher on two services (transport and heating) |
| Airports (3,245) | OurAirports file on GitHub: 16,187 values, 0 differences | OpenFlights database (separate project, partly based on OurAirports): 3,085 of 3,129 agree within 5 km; the 44 others are moved airports or reused codes in the older OpenFlights list | Matches the publisher; mostly agrees with a second list |
| US EPA supply chain factors (1,016) | EPA ScienceHub file: 4,064 values, 0 differences | None reachable: not checked on a second platform | Matches the publisher (one platform) |
| US EPA calculator figures (25) | EPA calculator page and assumptions page: 25 values, 0 differences | None exists: single source | Each number is printed on the publisher's pages |
| HS-to-industry links (6,322) | concordance R package on GitHub: 6,322 pairs, 0 missing from the package | None reachable: not checked on a second platform | Pairs match the package; line counts could not be re-derived |
| Pakistan energy prices (30) | NEPRA and OGRA official notices (scanned PDFs): 30 values read twice from the scans, 0 differences; notices unchanged (same checksums) | None: the regulators' web pages could not be read by machine: not checked on a second platform | Read twice by eye from the official notice |
| Boavizta product footprints (1,226 records) | Boavizta file on GitHub: 4,904 values, 0 differences | Each manufacturer's own report (independent of Boavizta): 633 found in the report; 9 not in the report today; 43 reports removed; 541 could not be opened | 633 confirmed in the maker's report by machine; none by the human review |
| ADEME everyday products (201 records) | ADEME Impact CO2 source file on GitHub: 201 values, 0 differences | Not checked: not checked on a second platform | Matches the publisher (one platform) |
| EPD construction records (15) | Each EPD's public data file (ocni-dtu/epdx mirror): 30 values, 0 differences | The signed EPD documents were not opened: not checked on a second platform | Matches the public data file (one platform) |
| HS code mappings (26 product types) | Each code exists in the HS 2022 list: 26 of 26 codes exist | No authority has confirmed them: proposed, not verified | NOT verified: needs a customs expert |

Notes on the second-platform results (script: `scripts/cross_check.py`, raw results: `docs/data-verification/second-platform.json`):

- **World Bank against Our World in Data.** These are different research groups with different methods, so they should be close, not equal. Pakistan: CO2 per person 0.83 t (ours, 2025) against 0.81 t (World Bank, 2024); all gases 1.89 t (ours, includes land use) against 2.09 t (World Bank, excludes land use). The large gaps are very small island states and forest countries, where land-use accounting dominates.
- **Airports.** 44 airports are more than 5 km from the OpenFlights position. They are new airports that replaced old ones (for example Phnom Penh, Hefei, Yantai) or codes reused for a different airport. Our list is the newer one.
- **Electricity carbon intensity**, the one Pakistan-specific factor the calculator uses, could only be checked on one platform (Our World in Data, which takes it from Ember).

## Devices the web calculator was tested on

The whole questionnaire was run automatically on: desktop (1280 px), a 390 px phone, a 320 px phone, and emulated Galaxy S9+, iPhone 13, iPhone SE, Pixel 7, iPad (7th generation) and Galaxy Tab S4. All pass. The 320 px test found a real fault (the header pushed the page wider than the screen so the Next button was out of reach); it is fixed.

The Python tests pass on Linux and on Windows (GitHub's test machines). Device runs use the Chromium browser engine with each device's screen size and touch settings; Firefox and Safari engines were not available here, and no physical phone was used.

## 5. What is still NOT verified

- No product footprint has passed the human evidence review. 633 have a machine "number found in the report"; 9 do not match the report today; 584 could not be checked.
- The 15 EPD records were compared with their public data files, not with the signed EPD PDFs.
- HS code mappings are proposals.
- The EPA calculator check finds each number on the page; the meaning beside it was read once by a person.
- Nobody has checked that publishers' numbers are correct, only that ours equal theirs.
- Factors for Pakistan other than electricity do not exist in the system (see `docs/CALCULATOR_APP.md`).

## How to repeat this

Download the publisher files into a folder laid out as the top of `scripts/verify_data.py` describes, then:

```powershell
.\.venv\Scripts\python.exe scripts\verify_data.py --downloads C:\path\to\downloads --db data\carbon.sqlite
.\.venv\Scripts\python.exe scripts\check_manufacturer_reports.py --cache C:\path\to\cache --out manufacturer-reports.json
```

Run on Linux with Python 3.13. Not run on Windows.
