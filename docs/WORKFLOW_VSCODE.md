# Beginner workflow: Windows + VS Code

Use this as a clean installation for the **GCC-Final-System** repository.
Install Python 3.12, Git and VS Code. Open a terminal in a new folder:

```powershell
git clone https://github.com/MuhammadHussainHashim/GCC-Final-System.git
cd GCC-Final-System
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

Choose **Python: Select Interpreter** → `.venv\Scripts\python.exe` in VS Code.
The Python package remains named `gcc_cos` to avoid breaking its original
entry points. Native Windows tests are CI-configured but should be checked
on your PC as well.

## Offline reproducible demonstration

```powershell
.\.venv\Scripts\python.exe -m gcc_cos --registry examples/phase2/sources.json ingest --manifest examples/phase2/local-files.json
.\.venv\Scripts\python.exe -m gcc_cos revalidate
.\.venv\Scripts\python.exe -m gcc_cos export exports/products.xlsx --products-only
.\.venv\Scripts\python.exe -m streamlit run dashboard.py --server.address 127.0.0.1
```

The output contains source-reported records awaiting review, not verified
carbon-neutrality claims. Generated database and exports are intentionally
Git-ignored. The current reviewed/verified subset can be empty; this is honest.

## Prepare your newer manufacturer research

Copy your saved `Combined_Product_Carbon_Footprints.xlsx` into a local folder
outside the repo or beside it, then run:

```powershell
.\.venv\Scripts\python.exe -m gcc_cos research-prepare "C:\path\to\Combined_Product_Carbon_Footprints.xlsx" --output-dir exports\research-review
```

Inspect `records_review.csv`, `duplicate_candidates.csv`,
`conflicting_report_values.csv` and `audit_summary.json`. Do not copy these
records directly into verified-only reports. Review each underlying original
report and its permission terms before promoting any observation.

## Recover other local VS Code/Codex work

1. In VS Code, use **File → Open Recent** and identify every GCC/COS folder.
2. For each folder, run `git remote -v` and `git status --short` in its terminal.
3. Upload a ZIP of the folder **excluding** `.venv`, `.env`, API keys, tokens,
   databases with personal records, caches and `node_modules`; or push safe
   changes to a separate review branch.
4. Compare each missing module and document with `docs/ASSET_CATALOG.md`.

No cloud process can read unshared files from your Windows drive. Review
`archive/legacy/` for recovered source code from three older tool archives.
