# COS Carbon Source Collector

This package is a local collector for your COS/GCC research. It downloads selected public spreadsheets/CSV files from official source endpoints, saves the originals in `raw_sources/`, and builds `COS_Collected_Carbon_Source_Data.xlsx`.

## Run on Windows

1. Extract this ZIP to a folder, for example `C:\COS_Carbon_Source_Collector`.
2. Open PowerShell or CMD in that folder.
3. Install requirements:

   ```powershell
   py -m pip install -r requirements.txt
   ```

4. Run:

   ```powershell
   py collect_sources.py
   ```

5. Open `COS_Collected_Carbon_Source_Data.xlsx` and inspect the `Download Log` sheet. The original files are saved under `raw_sources`.

## Sources this script attempts to download

- US EPA GHG Emission Factors Hub 2025 XLSX
- UK Government GHG Conversion Factors 2026 flat XLSX
- ÖKOBAUDAT 2024-II CSV export

URLs and endpoints can change. If a download fails, use the official URL in the workbook's Source Register and download manually, then rerun the script.

## Other resources in the Source Register

BONSAI, Federal LCA Commons/USLCI, Textile Exchange, openLCA Nexus, EPD International, IBU.data, CCaLC, and ecoinvent are listed for follow-up ingestion. Some require API keys, manual report extraction, account access, or paid/licensed access. This package does not claim to have downloaded those entire databases.

Federal LCA Commons API:
- API guide: https://www.lcacommons.gov/lca-commons-api-guide
- A free data.gov API key is required for automated API calls; do not put a personal key into a public script.
- Repository datasets are life-cycle inventory data and need further analysis/modeling to produce product LCA results.

BONSAI:
- https://www.bonsai.uno/
- Product footprint data is published under CC BY 4.0 according to the official site; provide attribution.
- API documentation and access can evolve; inspect the official docs before adding an API collector.

## Data integrity rules

- No fabricated carbon-footprint values.
- Keep the source file and source URL.
- Preserve original values and units.
- Keep geography, reference year, GWP indicator, functional/declared unit, and life-cycle boundary when available.
- Distinguish product-specific footprints from LCI process data and activity emission factors.
- Never call an estimate "verified" unless the evidence supports that status.
- Check licences before redistributing data. Publicly downloadable does not always mean freely redistributable.

## Current limitations

A complete global database of every product and every brand/model variant does not exist as one public download. Some datasets are very large, and this execution environment cannot directly fetch large binary downloads; running the collector on your own PC with internet access is the intended next step. The resulting workbook will contain whatever downloads succeed, with failures recorded transparently.
