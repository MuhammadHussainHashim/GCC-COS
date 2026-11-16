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

| Manufacturer | Products | Number found in the report | Not found | Report could not be opened or read |
|---|---|---|---|---|
| Apple | 91 | 91 | 0 | 0 |
| Google | 51 | 51 | 0 | 0 |
| Samsung | 7 | 7 | 0 | 0 |
| Dell | 525 | 300 | 2 | 223 |
| Lenovo | 365 | 172 | 0 | 193 |
| Microsoft | 36 | 4 | 2 | 30 |
| Seagate | 12 | 4 | 0 | 8 |
| Fairphone | 2 | 1 | 1 | 0 |
| HP | 124 | 0 | 0 | 124 |
| Lexmark | 11 | 0 | 0 | 11 |
| Asus | 2 | 0 | 0 | 2 |
| **Total** | **1,226** | **630** | **5** | **591** |

### Five records whose number is NOT in the manufacturer's report today

| Product | Value in our data (from Boavizta) | What the report says today |
|---|---|---|
| Dell PowerEdge R6515 | 8,160 kg CO2e | "estimated carbon footprint: 3450 kgCO2e" |
| Dell PowerEdge R7515 | 8,990 kg CO2e | "estimated carbon footprint: 3920 kgCO2e" |
| Microsoft Surface Laptop SE | 101 kg CO2e | lists production 42, transport 2, use 28 kg CO2eq; 101 does not appear |
| Microsoft Surface Pro X | 116 kg CO2e | lists production 137, transport 15, use 21 kg CO2eq; 116 does not appear |
| Fairphone 4 | 49.9 kg CO2e | headline "estimated to be 43 kg CO2 eq."; 49.9 appears only elsewhere in the document |

The likely cause is that the manufacturer replaced the report after Boavizta copied the figure, or that Boavizta used a different configuration. These five need a person to read the report and decide. They are still in the data, unchanged.

### 591 products that could not be checked

| Reason | Products |
|---|---|
| Dell's site refused automated download (HTTP 403) | 218 |
| Lenovo's site answered "unavailable" (HTTP 503) | 193 |
| HP's site failed the secure connection | 124 |
| Report no longer at its address (HTTP 404; mostly Microsoft, some Dell) | 35 |
| Lexmark, HPE and Asus sites not reachable from this environment | 23 |
| Seagate pages whose text is drawn by scripts and cannot be read this way | 8 |

These need a person with a normal web browser, which is what the Phase 4 human evidence review is for.

## 5. What is still NOT verified

- No product footprint has passed the human evidence review. 630 have a machine "number found in the report"; 596 have nothing.
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
