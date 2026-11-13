# GCC Carbon Footprint Calculator (web app)

A guided household calculator that runs in your browser and reads the GCC database **read-only**.
It is separate from the Streamlit administration dashboard (`dashboard.py`), which is unchanged.

## Start it (Windows, VS Code terminal)

1. Set up and load the data once (VS Code: **Terminal → Run Task…** → `GCC-COS: 1 Set up (run once)`, then `GCC-COS: 2 Load bundled data (offline)`).
2. Approve the datasets the calculator may use (see "Approval" below). Nothing is approved by default.
3. Run the task `GCC-COS: 4 Run calculator (web)`, or type:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos.web --db data\carbon.sqlite
```

4. Open http://127.0.0.1:8000/ in your browser. Press `Ctrl+C` in the terminal to stop.

## What it does

Six steps, then results: household (country, year, people) → home energy (electricity, natural gas, LPG) → transport (cars, motorbikes, bus, rail, flights) → food → products (exact manufacturer, model and variant) → review → results.
You can go back, change any answer, skip a line or a whole section, and review everything before calculating. Every question states its unit and period.

The results show the yearly total in kg and tonnes CO2e, a per-person figure, a donut chart by section, a bar chart of the biggest entries, coverage, what is missing and why, the factor, publisher, licence, year and lifecycle boundary behind every entry, suggestions worked out from the same published rows, and downloads (HTML report, CSV, JSON).

## Rules the calculation follows

| Rule | What happens |
|---|---|
| Exact match | An entry is calculated only when exactly one published row matches its activity, unit, country, reporting year and lifecycle boundary. |
| Approval | The row's dataset must be approved for the calculator (or the product record must have passed the existing human evidence review). Otherwise: `not_approved`. |
| Other country / other year | Refused (`geography_mismatch`, `year_mismatch`) unless the person switches on "stand-in factors". Then the entry is calculated and labelled as a stand-in everywhere. |
| No row | `missing_factor`. Nothing is estimated. |
| Row in another unit | `unit_mismatch`. Units are not converted with outside numbers. |
| Two or more rows | `duplicate_factor`. None is used. |
| Production-stage-only record (for example EPD modules A1-A3) | `boundary_mismatch`. Not mixed into the total. |
| Partial results | The total is always called "footprint of the activities you entered" with the badge "Partial: not a complete carbon footprint". `is_complete_footprint` is always `false`. |

Product footprints are the manufacturer's own published figures. They are shown as "approved for estimation … not independently verified" unless the record passed human evidence review.

## Approval (administrator)

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --db data\carbon.sqlite calculator-approve owid-country-data --approver "Your Name" --note "What you checked"
.\.venv\Scripts\python.exe -m gcc_cos --db data\carbon.sqlite calculator-approvals
.\.venv\Scripts\python.exe -m gcc_cos --db data\carbon.sqlite calculator-revoke owid-country-data --by "Your Name" --note "Why"
```

Dataset ids the calculator can use: `owid-country-data` (electricity by country), `uk-desnz-conversion-factors-2026` (gas, LPG, vehicles, bus, rail, flights), `agribalyse-3.2-synthesis` (foods), and the product sources already in the records (for example `boavizta-products`).
Approvals are stored in their own table, `calculation_approvals`, with the person, date and note. Withdrawing one keeps the history. No existing table is changed.

## API (version 1, read-only)

Interactive documentation: http://127.0.0.1:8000/api/v1/docs

| Method and path | Purpose |
|---|---|
| `GET /api/v1/health` | Database found, approved datasets |
| `GET /api/v1/catalog` | Activities, options, units, periods |
| `GET /api/v1/countries` | Countries with an electricity figure |
| `GET /api/v1/data-status?country=PAK&year=2025` | Which activities have a matching, approved factor |
| `GET /api/v1/foods?q=` · `/products?q=` · `/airports?q=` | Search |
| `POST /api/v1/calculate` | Calculate |
| `POST /api/v1/reports/{csv,json,html}` | Download a report |

There are no write endpoints. The database is opened with SQLite `mode=ro`, so the calculator cannot change data even by mistake. Input is validated (unknown fields are rejected), and responses carry a content security policy.
The server listens on `127.0.0.1` only. Do not expose it to the internet without adding authentication and HTTPS in front of it.

## Code map

| Path | Role |
|---|---|
| `gcc_cos/approvals.py` | Approval records |
| `gcc_cos/footprint/catalog.py` | Activities and which published rows they use |
| `gcc_cos/footprint/repository.py` | Read-only queries |
| `gcc_cos/footprint/engine.py` | The calculation and its rules |
| `gcc_cos/footprint/report.py` | CSV, JSON and HTML reports |
| `gcc_cos/web/app.py` | FastAPI endpoints |
| `gcc_cos/web/static/` | The interface (plain HTML, CSS and JavaScript modules; no build step) |
| `tests/test_footprint.py`, `tests/test_ui_flow.py`, `tests/ui/calculator_flow.js` | Tests |

## Limits you should know (honest list)

- **Only electricity has a Pakistan figure** (Our World in Data, latest year held). Gas, LPG, vehicles, bus, rail and flights are UK government factors for 2026; foods are French averages (AGRIBALYSE 3.2). For a household in Pakistan these are used only as labelled stand-ins.
- **No dataset is approved by default**, and no approval has been given by a real person yet. Until someone approves, every entry returns `not_approved`.
- **No product record has passed independent review.** Product figures are manufacturer-reported.
- UK "direct" fuel and vehicle factors exclude fuel production (well-to-tank). Battery electric cars show 0 because charging is counted under electricity.
- Flights by airport use the straight great-circle distance, with no allowance for detours.
- The electricity figure is a country generation average; it excludes grid losses and your supplier's own mix.
- The total adds entries with different lifecycle boundaries; it is an indication, not a certified footprint.
- The scale comparison is the country's total emissions per person, not a household average.
- Fonts load from Google Fonts; offline, the page falls back to system fonts.
- Tested on Linux with Python 3.13 and Chromium. **Not tested on Windows** or in other browsers.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The browser test runs only if Node.js and Playwright are installed; otherwise it is skipped and says so.
