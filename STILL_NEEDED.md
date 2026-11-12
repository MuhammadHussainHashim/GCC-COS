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

## Reached, but not loaded yet

These sites now open. Each needs careful reading of PDF or web tables by hand, so they were not rushed in.

| # | What | Where | What is needed |
| --- | --- | --- | --- |
| 1 | Pakistan electricity prices | https://nepra.org.pk/tariff/Distribution%20WAPDA.php and https://nepra.org.pk/tariff/Distribution%20K-Electric.php | The current consumer-end tariff schedule (PDF notifications). Tell me which distribution company and date you want, or I will take the latest uniform tariff. |
| 2 | Pakistan gas and fuel prices | https://www.ogra.org.pk/consumer-gas-prices and https://www.ogra.org.pk/notified-petroleum-prices | The latest notified prices (PDF notifications). |
| 3 | Pakistan household energy use | https://www.pbs.gov.pk/ | The right survey report (HIES or PSLM) with fuel and electricity tables. |
| 4 | Vehicle make and model fuel economy | https://www.fueleconomy.gov/feg/epadata/vehicles.csv | The file downloads (22 MB, about 48,000 vehicles). Not loaded: it is a "Later" item and US-specific. Say if you want it. |
| 5 | Recycling and landfill factors | https://www.epa.gov/waste-reduction-model/documentation-waste-reduction-model | The WARM documentation tables. (UK waste-disposal factors are already in `activity_factors`.) |
| 6 | Pakistan fuel emission factors | https://www.ipcc-nggip.iges.or.jp/EFDB/main.php | IPCC default factors are behind a search form; the 2006 Guidelines tables are PDFs. (UK fuel factors are already in `activity_factors`.) |
| 7 | Carbon price | https://icapcarbonaction.com/en/ets-prices | The price download; the site's reuse terms must be read first. |

## Still not obtained

| # | What | Why | What to do |
| --- | --- | --- | --- |
| 8 | EU CBAM default values by country of origin | The Commission page opens, but I did not find the annex file on it | Download the default-values annex (PDF or Excel) from https://taxation-customs.ec.europa.eu/carbon-border-adjustment-mechanism_en and upload it |
| 9 | Footprint by diet type (Scarborough et al. 2023) | nature.com still refuses the connection | Download the supplementary data from https://www.nature.com/articles/s43016-023-00795-w and upload it |
| 10 | ICE database (materials) | The page opens but offers no direct file link | Download the Excel file from https://circularecology.com/embodied-carbon-footprint-database.html and upload it; check its terms of use |
| 11 | ADEME Base Empreinte | Registration required | https://base-empreinte.ademe.fr/ |
| 12 | Open CEDA spend factors | Link is sent by email after a form | https://openceda.org/ |
| 13 | 16 environmental impact indicators | Not attempted | EU Joint Research Centre, Environmental Footprint reference package |
| 14 | Offset price and project list | A business decision: choose a provider first | — |
| 15 | Printing inputs | Source data is not public | — |
| 16 | Local transport averages for Pakistan | No source identified | — |

## Needs a licence check, not a download

29 rows of the workbook's "Calculator reference data" were not loaded because no licence is given: 5 from carbonfootprint.com, 3 from The Nature Conservancy and 21 from WWF-UK. They are listed in `datasets/epa-calculator-reference/SOURCE.json`.

## Needs classification by a person, not a download

No HS code was assigned, because no published table gives one for these:

- 201 ADEME everyday products and 2,451 AGRIBALYSE foods.
- 64 manufacturer product records with no code, and 372 with only a 4-digit heading.
- The 1,177 codes on manufacturer records are proposed mappings from an earlier job and are still marked not verified.

The only source-given HS codes in the system are the 283 on the UK CBAM values. The EPA spend-based factors reach most HS codes through the HS-to-NAICS link, as an estimate per dollar, not a classification.

## One label that is now out of date

The calculator's own copy of the CBAM values (under `examples/phase5`) still carries the label "typed from the source page, not checked". The values are identical to the checked ones. That folder was left untouched because an earlier instruction said not to change anything under `examples/`. Say the word and the label will be updated.
