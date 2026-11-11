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

## What the data can answer today

Mostly electronics: laptops, monitors, desktops, servers, smartphones, tablets, printers and a few others, plus a handful of construction products. Any other product returns "no value".
