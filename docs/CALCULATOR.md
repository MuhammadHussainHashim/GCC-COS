# Footprint calculator (layer 3)

You give it products and quantities. It gives a total in kg CO2e, shows where every number came from, and says clearly what it could not answer.

## Three ways to name a product

| You enter | What the calculator uses |
| --- | --- |
| A **specific product** (its record id, for example `1`) | That one source record |
| A **product type** (for example `Laptop`) | The median of all source records of that type |
| An **HS code**, 4 or 6 digits (for example `847130`) | The median of all source records linked to that code |

When a line uses a median, the result also shows the lowest and highest record, so you can see how wide the range is.

## Rules it follows

- **No invented numbers.** If there is no data for a line, the line says "no value" and is left out of the total. The result is then marked INCOMPLETE.
- **Everything is flagged NOT VERIFIED.** Footprints are the figures publishers reported. HS code links are proposed mappings.
- **Different lifecycle scopes are never added together.** Electronics figures cover the full lifecycle. Construction figures cover single production stages (EPD modules such as A1-A3). You get one total per scope.
- **Units are respected.** Electronics are per item. Construction products are per kg, m2 or m3, and the quantity must be in that unit.
- **A product type with mixed units or stages gets no median.** Pick one record by id instead.
- **Transport is not included.**

## What a result shows

- **Total** in kg CO2e, with the lowest and highest possible total from the source records.
- **Biggest line** and each line's share of the total, so you can see where the footprint comes from.
- **Use phase versus making.** Where the source reports what share of a product's footprint comes from using it, the result splits the total into "use phase" and "making, transport and end of life". If any line has no reported share, the split is left out instead of estimated.
- **Per year of use**, using the number of years of use each source assumed.
- **Per person**, if you enter how many staff or household members share the footprint.
- **Same-manufacturer comparison** for a specific product: how it compares with the median of the same manufacturer's products of the same type (needs at least three such records). Comparisons across manufacturers are not shown, because the source dataset warns against them.
- **Wide range flag** when the highest source record for a line is more than three times the lowest.

## Use it in the dashboard

1. **Terminal → Run Task… → GCC-COS: 3 Run dashboard**.
2. Open the **Calculator** tab.
3. For a few products: choose **Pick products one by one**, pick a product, enter a quantity, click **Add to basket**.
4. For many products: choose **Upload a CSV basket** and upload a file like `examples/calculator/company-basket.csv`.
5. Read the warnings, then use **Download result CSV** or **Download result Excel**.

## Use it from the terminal

```powershell
.\.venv\Scripts\python.exe -m gcc_cos calculate examples/calculator/company-basket.csv --output exports/footprint.xlsx
.\.venv\Scripts\python.exe -m gcc_cos calculate --item type=Laptop:1 --item type=Smartphone:1
.\.venv\Scripts\python.exe -m gcc_cos calculate --item hs=847130:120 --item record=1:2 --output exports/footprint.json
```

## Basket CSV format

One row per product. A `quantity` column is required. Fill in exactly one of `hs_code`, `product_type` or `record_id` in each row. A `note` column is optional.

```csv
hs_code,product_type,record_id,quantity,note
847130,,,120,Laptops for the new office
,Smartphone,,40,Staff phones
,,1,2,Two specific laptops
```

## Features taken from other calculators

On 11 November 2026 I reviewed published descriptions and reviews of other calculators (not hands-on tests of each one). Features they share, and what this project did with each:

| Feature seen elsewhere | Seen in | Here |
| --- | --- | --- |
| Breakdown by lifecycle stage | Product footprint tools such as ECODESIGN+, ECOSPEED Product; Boavizta's Datavizta | Added: use phase versus making, from source-reported shares |
| Hotspots (biggest contributors) | ECODESIGN+, ClimatePartner | Added: biggest line and share per line |
| Compare alternatives / benchmark | ECODESIGN+, ECOSPEED Product; WWF compares with a national target | Added in a limited form: same-manufacturer comparison only |
| Quick, plain-language entry | WWF, UN calculators | Added: pick by product type, search for a product |
| Bulk entry for businesses | SME Climate Hub, EPA Simplified GHG Emissions Calculator (spreadsheet) | Already present: CSV basket and Excel export |
| Per-person or per-employee figures | Business calculators | Added: optional number of people |
| Sources and assumptions shown with the result | Product footprint reporting guides | Already present, extended |
| Reduction tips after the result | WWF | Not yet: layer 4 |
| Offsetting after the result | UN, CoolClimate, carbonfootprint.com | Not yet: layer 4 |
| Transport leg by route and mode | EcoTransIT World, Searoutes, Flexport, Maersk | Not added: needs a sourced emission-factor dataset (GLEC / ISO 14083 style) |
| Household energy, travel, food | EPA, CoolClimate, WWF | Not added: outside this project's product data |
| Equivalents such as "km driven" | Several consumer calculators | Not added: needs a sourced conversion factor |

Sources read: [Sustainable Atlas comparison](https://sustainableatlas.org/post/comparison-carbon-footprint-calculators-accuracy-usability-actionability-1716), [North Herts council review](https://democracy.north-herts.gov.uk/documents/s17833/Carbon%20Footprint%20Calculators%20Review.pdf), [Climatiq list of business calculators](https://climatiq.io/blog/list-free-business-carbon-footprint-calculators), [SME Climate Hub methodology](https://faq.smeclimatehub.org/hc/en-us/articles/18549522528786-What-methodology-are-the-calculators-using-to-calculate-emissions), [Net Zero Compare: ECODESIGN+](https://netzerocompare.com/software/ecodesign-plus), [Net Zero Compare: ECOSPEED Product](https://netzerocompare.com/software/ecospeed-product), [Net Zero Compare: EcoTransIT World](https://netzerocompare.com/software/ecotransit-world), [Searoutes on GLEC and ISO 14083](https://searoutes.com/en/blog/glec-framework-2025-the-ultimate-guide-to-iso-14083-sustainable-logistics), [Boavizta Datavizta](https://www.github.com/Boavizta/datavizta). Several of these are vendor pages, so their feature claims are self-reported.

## What the data can answer today

Mostly electronics: laptops, monitors, desktops, servers, smartphones, tablets, printers and a few others, plus a handful of construction products. Any other product returns "no value".
