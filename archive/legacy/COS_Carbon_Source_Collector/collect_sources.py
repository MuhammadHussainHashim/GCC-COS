"""
COS Carbon Source Collector
Downloads selected publicly accessible source files and builds a traceable Excel workbook.

Run:
    py -m pip install -r requirements.txt
    py collect_sources.py

Important:
- This script downloads source files to raw_sources/ and does not modify them.
- It combines spreadsheet tabs only as raw rows with source_file/source_sheet metadata.
- It does NOT assume every row is a finished-product carbon footprint.
- Some sources need manual download, API keys, or paid/licensed access; see README.md.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import time
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw_sources"
RAW.mkdir(exist_ok=True)
OUT = ROOT / "COS_Collected_Carbon_Source_Data.xlsx"
TIMEOUT = 120
HEADERS = {"User-Agent": "COS-Research-Collector/1.0 (academic research; contact project owner before production use)"}

DOWNLOADS = [
    {
        "source": "US EPA GHG Emission Factors Hub",
        "url": "https://www.epa.gov/system/files/other-files/2025-01/ghg-emission-factors-hub-2025.xlsx",
        "filename": "EPA_GHG_Emission_Factors_Hub_2025.xlsx",
        "kind": "activity_emission_factors",
        "note": "Government activity factors; not a universal product-specific footprint database."
    },
    {
        "source": "UK Government GHG Conversion Factors 2026 - flat file",
        "url": "https://assets.publishing.service.gov.uk/media/6a6c9748862aaf18d9c62ac9/ghg-conversion-factors-2026-flat-format-revised.xlsx",
        "filename": "UK_GHG_Conversion_Factors_2026_Flat.xlsx",
        "kind": "activity_emission_factors",
        "note": "UK activity factors. Keep geography and reporting year; not a global product footprint catalogue."
    },
    {
        "source": "ÖKOBAUDAT 2024-II CSV export",
        "url": "https://www.oekobaudat.de/OEKOBAU.DAT/resource/datastocks/cc64f7e1-14d8-4a57-b11b-2cf03d200c82/exportCSV",
        "filename": "OEKObaudat_2024-II.csv",
        "kind": "construction_LCA_data",
        "note": "Construction-focused LCA dataset. Official page says the generic database was last updated 2024-10-02. Check reuse terms."
    },
]

SOURCES = [
    ["BONSAI Climate Footprint Analyser", "https://www.bonsai.uno/", "Open product footprints and recipes", "Website/API/triplestore", "Product-footprint data stated as CC BY 4.0 with attribution", "Broad modeled generic product/activity coverage; not every brand/model variant", "Not downloaded automatically by this script; API and data access routes are evolving."],
    ["Federal LCA Commons / USLCI", "https://www.lcacommons.gov/lca-collaboration/", "LCI process datasets and LCIA methods", "Repository downloads/API", "Free downloads; review individual dataset terms", "Materials, energy, transport, agriculture, industrial processes", "LCI data usually requires additional modeling to produce a product footprint."],
    ["ÖKOBAUDAT", "https://oekobaudat.de/en/service/downloads.html", "Construction-product LCA datasets", "ZIP or CSV", "Review source terms", "Construction products/materials", "CSV download is attempted by this script; if endpoint changes, download from official page."],
    ["Textile Exchange LCI Library", "https://textileexchange.org/lci-library/", "Textile raw-material life-cycle inventory", "Website download workflow", "Check dataset and component licences", "Fibres, textile raw materials, selected processing", "Manual access/extraction may be required; not necessarily finished-garment footprints."],
    ["openLCA Nexus", "https://nexus.openlca.org/search", "LCA datasets/databases", "Dataset-specific downloads", "Mixed free/paid; licence varies", "Multiple sectors and process types", "Only import datasets whose terms permit the intended use."],
    ["US EPA Emission Factors Hub", "https://www.epa.gov/climateleadership/ghg-emission-factors-hub", "GHG activity factors", "XLSX/PDF", "Public government resource; check terms", "Fuel, electricity, transport, waste, selected business factors", "2025 XLSX direct download is attempted by this script."],
    ["UK Government GHG Conversion Factors", "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026", "Annual activity conversion factors", "XLSX", "Open Government Licence v3.0 except where otherwise stated", "UK activities: fuel, electricity, transport, waste and related factors", "2026 flat file direct download is attempted by this script."],
    ["EPD International Library", "https://www.environdec.com/library", "Environmental Product Declarations", "Search/download individual declarations", "Check EPD/programme terms", "Product-specific declarations across sectors", "Individual PDFs need extraction and scope/verification checks."],
    ["IBU.data", "https://ibu-epd.com/en/ibu-data-start/", "Machine-readable construction EPDs", "Provider access workflow", "Check provider terms", "Construction products", "Registration/download access may apply."],
    ["CCaLC", "https://www.ccalc.org.uk/", "Carbon/LCA calculation tools and supporting data", "Download resources", "Check each resource's terms", "Materials, energy, transport, packaging, waste use cases", "Treat factors as contextual calculation inputs."],
    ["ecoinvent", "https://ecoinvent.org/database/", "Life-cycle inventory database", "Licensed database download", "Licence/subscription normally required", "Broad industrial and supply-chain processes", "Do not redistribute restricted raw records unless licence permits."],
    ["US EPA Supply Chain Emission Factors", "https://www.epa.gov/climateleadership/calculator-resources", "US industry/commodity supply-chain factors", "EPA download links", "Check source terms", "Commodity/industry spend-based factors", "Useful as screening factors; not product-specific physical footprints."],
    ["World Customs Organization", "https://www.wcoomd.org/", "HS nomenclature reference", "Official publications/access", "Check access terms", "Trade product classification", "HS codes classify products; they do not contain carbon footprints."],
]

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def download_file(item):
    target = RAW / item["filename"]
    status = "already_present"
    error = ""
    if not target.exists() or target.stat().st_size == 0:
        try:
            with requests.get(item["url"], headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True) as r:
                r.raise_for_status()
                content_type = r.headers.get("content-type", "")
                with open(target, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            # Reject obvious HTML error pages saved as .xlsx/.csv
            if target.stat().st_size < 100 or (target.suffix.lower() == ".xlsx" and not target.read_bytes()[:2] == b"PK"):
                target.unlink(missing_ok=True)
                raise ValueError(f"Downloaded content did not look like the expected file (content-type={content_type})")
            status = "downloaded"
        except Exception as e:
            target.unlink(missing_ok=True)
            status = "failed"
            error = str(e)
    return {
        "source": item["source"], "url": item["url"], "filename": item["filename"],
        "kind": item["kind"], "status": status, "bytes": target.stat().st_size if target.exists() else None,
        "sha256": sha256_file(target) if target.exists() else None, "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "error": error, "note": item["note"]
    }

def read_tabular(path):
    frames = []
    try:
        if path.suffix.lower() in [".xlsx", ".xlsm"]:
            book = pd.ExcelFile(path)
            for sheet in book.sheet_names:
                try:
                    df = pd.read_excel(path, sheet_name=sheet, dtype=object)
                    if not df.empty:
                        df.insert(0, "source_sheet", sheet)
                        df.insert(0, "source_file", path.name)
                        frames.append(df)
                except Exception as e:
                    print(f"  Could not read sheet {sheet}: {e}")
        elif path.suffix.lower() == ".csv":
            # Try common encodings/separators; keep text values unchanged where possible.
            try:
                df = pd.read_csv(path, dtype=object, low_memory=False)
            except UnicodeDecodeError:
                df = pd.read_csv(path, dtype=object, encoding="latin1", low_memory=False)
            if not df.empty:
                df.insert(0, "source_sheet", "CSV")
                df.insert(0, "source_file", path.name)
                frames.append(df)
    except Exception as e:
        print(f"  Could not parse {path.name}: {e}")
    return frames

def main():
    log = [download_file(item) for item in DOWNLOADS]
    # Add manual source register entries to workbook.
    frames = []
    for path in sorted(RAW.iterdir()):
        if path.is_file() and path.suffix.lower() in [".xlsx", ".xlsm", ".csv"]:
            print(f"Reading {path.name} ...")
            frames.extend(read_tabular(path))

    with pd.ExcelWriter(OUT, engine="openpyxl") as writer:
        pd.DataFrame([{
            "Purpose": "COS/GCC starter collection from selected public sources",
            "Important": "This workbook preserves raw rows; it does not certify them as product-specific footprints.",
            "Data policy": "Do not invent missing values. Preserve source, original unit, geography, year, impact indicator, and life-cycle boundary.",
            "Usage": "Review source-specific sheets and collection log. Keep original downloaded files in raw_sources/.",
            "Last run UTC": datetime.now(timezone.utc).isoformat()
        }]).to_excel(writer, sheet_name="README", index=False)
        pd.DataFrame(SOURCES, columns=["Source", "Official URL", "Data type", "Access method", "Licence/access", "Coverage", "Limitations/status"]).to_excel(writer, sheet_name="Source Register", index=False)
        pd.DataFrame(log).to_excel(writer, sheet_name="Download Log", index=False)
        pd.DataFrame([
            ["product_name", "Generic product/material/activity name"],
            ["brand_model_variant", "Only where explicitly stated in source"],
            ["footprint_value_original", "Exact source value; never infer missing values"],
            ["footprint_unit_original", "Exact source unit"],
            ["impact_indicator", "e.g. GWP-total; retain source definition"],
            ["declared_functional_unit", "Reference unit from source"],
            ["lifecycle_boundary", "e.g. cradle-to-gate or modules A1-A3"],
            ["geography", "Country/region/global scope"],
            ["reference_year", "Year represented by the data"],
            ["source_name_url", "Provider and exact dataset/document URL"],
            ["verification_status", "Independent verification/company-reported/modeled/unknown"],
            ["data_type", "Product-specific footprint / LCI process / activity factor / estimate"],
            ["licence", "Reuse terms and restrictions"],
        ], columns=["Field", "Definition"]).to_excel(writer, sheet_name="Recommended Schema", index=False)
        if frames:
            # Keep source rows separate to avoid destructive merging of incompatible columns.
            all_cols = []
            for df in frames:
                for c in df.columns:
                    if c not in all_cols:
                        all_cols.append(c)
            normalized = pd.concat([df.reindex(columns=all_cols) for df in frames], ignore_index=True)
            normalized.to_excel(writer, sheet_name="Collected Raw Rows", index=False)
        else:
            pd.DataFrame(columns=["source_file", "source_sheet", "raw_record"]).to_excel(writer, sheet_name="Collected Raw Rows", index=False)

    # Make sheets readable.
    from openpyxl import load_workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    wb = load_workbook(OUT)
    for ws in wb.worksheets:
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for cell in ws[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="245B4A")
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        for col in ws.columns:
            letter = get_column_letter(col[0].column)
            maxlen = max((len(str(c.value)) for c in col[:100] if c.value is not None), default=12)
            ws.column_dimensions[letter].width = min(max(maxlen + 2, 14), 45)
            for c in col:
                c.alignment = Alignment(vertical="top", wrap_text=True)
    wb.save(OUT)
    print("\nFinished.")
    print(f"Workbook: {OUT}")
    print(f"Raw downloads: {RAW}")
    print("Review Download Log; failed sources may need manual download from their official pages.")
    print("No numeric values are fabricated and no LCI process is relabeled as a finished-product footprint.")

if __name__ == "__main__":
    main()
