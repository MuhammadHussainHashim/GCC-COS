# Still needed

Updated 12 November 2026, after the official data sites were allowed in the build environment.

## Obtained since the first version of this list

| What | Now in | Rows |
| --- | --- | --- |
| UK CBAM pages: all 570 values re-checked, no differences, official 8-digit descriptions added | `reference_values` | 570 |
| US EPA spend-based factors by industry | `spend_factors` | 1,016 |
| UK government conversion factors 2026: fuels (including coal and wood), vehicles, flights by cabin class with and without radiative forcing, well-to-tank, ferry, taxi, freight, waste disposal, material use, hotel stays | `activity_factors` | 2,622 |
| AGRIBALYSE foods per kg | `product_averages` | 2,451 |
| US EPA calculator values: all 25 re-checked against the EPA pages | `benchmarks` | 25 |
| Pakistan residential electricity tariff (NEPRA, February 2026), domestic gas slabs (OGRA, July 2025), LPG (November 2026) and kerosene (November 2026), transcribed from the scanned notifications | `energy_prices` | 30 |

## Reached, but not loaded yet

These sites now open. Each needs careful reading of PDF or web tables by hand, so they were not rushed in.

| # | What | Where | What is needed |
| --- | --- | --- | --- |
| 1 | Petrol and diesel prices for Pakistan | Set by the Ministry of Energy (Petroleum Division), not in OGRA's notifications, which cover kerosene, LPG and gas | The latest petrol (motor spirit) and high-speed diesel price notification |
| 2 | Monthly fuel charges and quarterly adjustments on electricity bills | https://nepra.org.pk/tariff/Distribution%20IESCO.php (monthly decisions) | Needed to turn a whole electricity bill into kWh; the base tariff is loaded |
| 3 | Pakistan household energy use | https://www.pbs.gov.pk/ | The right survey report (HIES or PSLM) with fuel and electricity tables. |
| 4 | Vehicle make and model fuel economy | https://www.fueleconomy.gov/feg/epadata/vehicles.csv | The file downloads (22 MB, about 48,000 vehicles). Not loaded: it is a "Later" item and US-specific. Say if you want it. |
| 5 | Recycling and landfill factors | https://www.epa.gov/waste-reduction-model/documentation-waste-reduction-model | The WARM documentation tables. (UK waste-disposal factors are already in `activity_factors`.) |
| 6 | Pakistan fuel emission factors | https://www.ipcc-nggip.iges.or.jp/EFDB/main.php | IPCC default factors are behind a search form; the 2006 Guidelines tables are PDFs. (UK fuel factors are already in `activity_factors`.) |
| 7 | Carbon price | https://icapcarbonaction.com/en/ets-prices | The price download; the site's reuse terms must be read first. |

## Still not obtained

| # | What | Why | What to do |
| --- | --- | --- | --- |
| 8 | EU CBAM default values by country of origin | EUR-Lex answers automated downloads with an empty page (it expects a browser), and getting round that was not attempted | Open https://eur-lex.europa.eu/eli/reg_impl/2025/2621/oj/eng in a browser, save the PDF of Implementing Regulation (EU) 2025/2621, and also save its correction, Implementing Regulation (EU) 2026/1740, then upload both |
| 9 | Footprint by diet type (Scarborough et al. 2023) | nature.com still refuses the connection | Download the supplementary data from https://www.nature.com/articles/s43016-023-00795-w and upload it |
| 10 | ICE database (materials) | Download needs registration, and the publisher now limits free use to teaching and academic research; professional use needs a paid licence | Only load it if your use qualifies or you buy a licence: https://circularecology.com/registerice.html |
| 11 | ADEME Base Empreinte | Registration required | https://base-empreinte.ademe.fr/ |
| 12 | Open CEDA spend factors | Link is sent by email after a form | https://openceda.org/ |
| 13 | 16 environmental impact indicators | Not attempted | EU Joint Research Centre, Environmental Footprint reference package |
| 14 | Offset price and project list | A business decision: choose a provider first | — |
| 15 | Printing inputs | Source data is not public | — |
| 16 | Local transport averages for Pakistan | No source identified | — |

## From the 19 November 2026 uploads

| What | Why it is not in the system | What to do |
| --- | --- | --- |
| 286 products where CarbonPDF and the held Boavizta record give different values | Same product; adding both would repeat it | A person reads both reports and decides which value to keep: `docs/data-verification/2026-11-19/carbonpdf-vs-held-boavizta-value-differences.csv` |
| 558 "proxy" HS-to-factor links | Guesses by an AI; the data policy forbids filling HS blanks with guesses | A person reviews `docs/data-verification/2026-11-19/hs-proxy-links.csv`; approved links can be added to the `hs_factor_links` dataset |
| 7 IPCC electricity values (utility and rooftop solar, concentrated solar, offshore wind, ocean, direct coal, direct gas) | ipcc.ch refused the connection, so they could not be re-checked | Download IPCC AR5 WGIII Annex III and compare Table A.III.2 |
| Poore & Nemecek oils (olive, palm, rapeseed, sunflower) | OWID gives no per-kg value | Take them from the paper's supplementary data |
| The Carbon Catalogue (866 products) and SU-EATABLE LIFE (food) | Figshare only; not downloaded | Download from figshare (doi 10.6084/m9.figshare.16908979 and 10.6084/m9.figshare.13271111) and upload |
| The Big Climate Database v1.2 (540 foods, CC BY 4.0) | Website not reached | Download from thebigclimatedatabase.com and upload |

## Needs a licence check, not a download

29 rows of the workbook's "Calculator reference data" were not loaded because no licence is given: 5 from carbonfootprint.com, 3 from The Nature Conservancy and 21 from WWF-UK. They are listed in `datasets/epa-calculator-reference/SOURCE.json`.

## Needs classification by a person, not a download

No HS code was assigned, because no published table gives one for these:

- 201 ADEME everyday products and 2,451 AGRIBALYSE foods.
- 64 manufacturer product records with no code, and 372 with only a 4-digit heading.
- The 1,177 codes on manufacturer records are proposed mappings from an earlier job and are still marked not verified.

The only source-given HS codes in the system are the 283 on the UK CBAM values. The EPA spend-based factors reach most HS codes through the HS-to-NAICS link, as an estimate per dollar, not a classification.

## One label in examples/ (now handled)

The calculator's own copy of the CBAM values (under `examples/phase5`) still carries the label "typed from the source page, not checked", because nothing under `examples/` is changed. The calculator now compares each of those records with the GOV.UK-checked table and drops the "not checked" warning when code and value agree, so results no longer show it.

## Found by the data verification of 16 and 17 November 2026

See `docs/DATA_VERIFICATION.md`. A person needs to read the manufacturer's report and decide for these nine products, whose stored value is not in the report today: Dell PowerEdge R6515 (8,160 stored; report says 3,450), Dell PowerEdge R7515 (8,990; report says 3,920), Microsoft Surface Laptop SE (101), Microsoft Surface Pro X (116), Fairphone 4 (49.9; report headline says 43), HP Chromebook x360 14a (315; report says 125), HP E24m G4 monitor (286; report gives 200 to 256 by region), HP Fortis 14" G10 Chromebook and Chromebook Enterprise (167 each; report says 160).

584 product reports could not be checked automatically: Dell, Lenovo and HP refuse automated downloads (520), 43 were removed by Microsoft, Seagate and Dell, and Lexmark and HPE were not reachable (21). These need checking in a web browser.
