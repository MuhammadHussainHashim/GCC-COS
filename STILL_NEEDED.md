# Still needed

These could not be downloaded from the build environment on 12 November 2026. Only GitHub could be reached; every site below refused the connection. Download each file on your own computer and upload it, and it can be loaded.

Where a file name is given, it is the name the workbook or the publisher states. Where the site decides the name, the page to open is given instead.

## Must

| # | What | Download from | File to get | Licence to confirm |
| --- | --- | --- | --- | --- |
| 1 | UK CBAM pages, to re-check all 570 values (especially 73065029) and add the 8-digit wording for iron and steel | https://www.gov.uk/government/publications/check-the-default-values-for-the-carbon-border-adjustment-mechanism-cbam | Save each of the five sector pages (iron and steel, aluminium, fertilisers, cement, hydrogen) as a web page or PDF | Open Government Licence v3.0 |
| 2 | Spend-based factors by industry (also gives an estimate for most HS codes through the HS-to-NAICS link) | https://catalog.data.gov/dataset/supply-chain-greenhouse-gas-emission-factors-v1-3-by-naics-6 | `SupplyChainGHGEmissionFactors_v1.3.0_NAICS_CO2e_USD2022.csv` | US government work |
| 3 | EU CBAM default values by country of origin | https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en | The default-values annex of the implementing regulation (PDF or Excel) | EU legal text; reuse allowed with acknowledgement |
| 4 | Footprint by diet type | https://www.nature.com/articles/s43016-023-00795-w | The article's supplementary data file (Scarborough et al. 2023) | Check the article's licence line (it is published open access) |
| 5 | Pakistan electricity prices | https://nepra.org.pk/ | The latest consumer-end tariff schedule (Schedule of Tariff, PDF) | Not stated on a page I could read; note the terms when you download |
| 6 | Pakistan gas and fuel prices | https://www.ogra.org.pk/ | The latest notified consumer gas prices and petroleum product prices (PDF) | As above |
| 7 | Pakistan household energy use by home type | https://www.pbs.gov.pk/ | Household Integrated Economic Survey (HIES) or PSLM report with fuel and electricity tables | As above |
| 8 | Material factors for a bill of materials | https://circularecology.com/embodied-carbon-footprint-database.html | Inventory of Carbon and Energy (ICE) database, Excel | Free to download; read its terms of use before reuse |
| 9 | Food and farm products per kg (longer list) | https://doc.agribalyse.fr/documentation-en/ | Agribalyse synthesis spreadsheet | Etalab Open Licence; credit ADEME and the version |
| 10 | ADEME materials, energy and transport factors | https://base-empreinte.ademe.fr/ | Base Empreinte export (registration needed) | Etalab Open Licence 2.0 |

## Should

| # | What | Download from | File to get | Licence to confirm |
| --- | --- | --- | --- | --- |
| 11 | Solid fuel factors, flights by cabin class and radiative forcing, well-to-tank uplift, ferry and taxi factors, and UK per-km and per-kWh factors (workbook rows 11 to 15, 18, 19, 23, 27) | https://www.gov.uk/government/collections/government-conversion-factors-for-company-reporting | The latest "conversion factors: full set" Excel file, or the flat file | Open Government Licence v3.0 |
| 12 | Recycling and landfill factors by material | https://www.epa.gov/warm | WARM emission-factor tables (Excel or PDF) | US government work |
| 13 | Waste per person and other EPA calculator assumptions, and a re-check of the 25 EPA values already loaded | https://www.epa.gov/ghgemissions/carbon-footprint-calculator | Save the calculator page and its assumptions page (https://www.epa.gov/node/273393) | US government work |
| 14 | Everyday equivalents | https://www.epa.gov/energy/greenhouse-gas-equivalencies-calculator | The "calculations and references" page | US government work |
| 15 | Carbon price (EU and UK allowances) | https://icapcarbonaction.com/en/ets-prices | The allowance price download for the EU ETS and UK ETS | Read the site's terms before reuse |
| 16 | Pakistan fuel emission factors | https://www.ipcc-nggip.iges.or.jp/EFDB/main.php | IPCC default factors for stationary and mobile combustion (2006 Guidelines, Volume 2), or Pakistan's national inventory report from the Ministry of Climate Change | IPCC material; check its copyright notice |
| 17 | Local transport averages for Pakistan (distance, fuel economy, occupancy) | No source identified | — | — |

## Later

| # | What | Download from | File to get |
| --- | --- | --- | --- |
| 18 | Vehicle make and model fuel economy | https://www.fueleconomy.gov/feg/download.shtml | `vehicles.csv` |
| 19 | 16 environmental impact indicators | EU Joint Research Centre, Environmental Footprint reference package | The EF reference package |
| 20 | Offset price and project list | A business decision: choose an offset provider first | — |
| 21 | Printing inputs | ClimateCalc data is not public; published LCA studies | — |
| 22 | Government share and national consumption accounts | National statistics offices | — |

## Needs a licence check, not a download

29 rows of the workbook's "Calculator reference data" were not loaded because no licence is given: 5 from carbonfootprint.com, 3 from The Nature Conservancy and 21 from WWF-UK. They cover target values (about 2 t per person), UK averages, assumed speeds and occupancy, food-waste adjustments and assumed prices. If you confirm each site's terms allow reuse, they can be loaded as they are. The rows are listed in `datasets/epa-calculator-reference/SOURCE.json`.

## Needs classification by a person, not a download

No HS code was assigned in this job, because no published table gives one for these:

- 201 ADEME everyday products (food, drinks, clothing, appliances, furniture, digital accessories).
- 63 ADEME activity factors (not goods; HS codes do not apply).
- 64 manufacturer product records with no code, and 372 with only a 4-digit heading.
- The 1,177 codes on manufacturer records are proposed mappings from an earlier job and are still marked not verified.

The only source-given HS codes in the system are the 283 on the UK CBAM values.
