"""Reference data kept apart from product records: one table per kind of number.

Product footprints stay in the `records` table. Everything here is a different kind of
value (regulatory defaults, activity factors, country averages, benchmarks) or a
look-up list (HS codes, HS-to-industry links, airports). Each table has its own label
for the kind of value, so they are never mixed in a calculation by accident.

A dataset is a folder with data.csv and SOURCE.json. The loader refuses a file whose
checksum differs from SOURCE.json, a column it does not know, or a value row without
a unit, year, geography and licence. Values are stored as text exactly as supplied.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

from .storage import now

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"
PROVENANCE = ["dataset_id", "source_title", "source_url", "license", "license_url", "attribution", "verification_status", "loaded_at"]

# table -> (columns read from data.csv, columns that identify a row, columns that must not be empty, Excel sheet name)
TABLES = {
    "reference_values": (
        ["scheme", "code_system", "code", "hs6", "hs4", "hs_code_basis", "sector", "description", "description_basis",
         "value_original", "unit_original", "value_metric", "unit_metric", "conversion", "value_kind", "geography", "year", "year_basis",
         "published", "source_page", "note"],
        ["scheme", "code"], ["scheme", "code", "value_original", "unit_original", "value_kind", "geography", "year"], "Reference values by code"),
    "activity_factors": (
        ["activity_id", "area", "name_en", "name_original", "language_original", "upstream_label_en", "value_original", "unit_original",
         "value_metric", "unit_metric", "conversion", "value_kind", "geography", "year", "year_basis", "source_page", "note"],
        ["dataset_id", "activity_id"], ["activity_id", "name_en", "value_original", "unit_original", "value_kind", "geography", "year"], "Activity factors"),
    "country_data": (
        ["iso3", "country", "indicator", "indicator_title", "value_original", "unit_original", "value_metric", "unit_metric", "conversion",
         "value_kind", "year", "year_basis", "upstream_file", "upstream_column", "original_source"],
        ["dataset_id", "iso3", "indicator"], ["iso3", "country", "indicator", "value_original", "unit_original", "value_kind", "year"], "Country data"),
    "hs_codes": (
        ["edition", "code", "level", "description", "parent", "section"],
        ["edition", "code"], ["edition", "code", "level", "description"], "HS codes"),
    "hs_industry_links": (
        ["hs6", "hs_edition", "industry_system", "industry_code", "import_lines", "share_of_lines", "geography", "year", "year_basis"],
        ["dataset_id", "hs6", "industry_code"], ["hs6", "industry_system", "industry_code", "geography", "year"], "HS to industry links"),
    "benchmarks": (
        ["publisher", "item", "value_original", "unit_original", "factor_to_metric", "value_metric", "unit_metric", "value_kind",
         "stated_source", "geography", "year", "year_basis", "source_page", "note"],
        ["publisher", "item"], ["publisher", "item", "value_original", "unit_original", "value_kind", "geography", "year"], "Benchmarks and assumptions"),
    "spend_factors": (
        ["industry_system", "industry_code", "industry_title", "ghg", "value_original", "unit_original", "value_metric", "unit_metric", "conversion",
         "value_without_margins", "value_of_margins", "reference_useeio_code", "value_kind", "geography", "year", "year_basis"],
        ["dataset_id", "industry_code"], ["industry_system", "industry_code", "industry_title", "value_original", "unit_original", "value_kind", "geography", "year"], "Spend-based factors"),
    "airports": (
        ["ident", "iata_code", "icao_code", "name", "type", "municipality", "iso_country", "iso_region", "latitude_deg", "longitude_deg",
         "elevation_ft", "elevation_m"],
        ["ident"], ["ident", "iata_code", "name", "iso_country", "latitude_deg", "longitude_deg"], "Airports"),
}
BUNDLED = {
    "reference_values": ["uk-cbam-defaults"], "activity_factors": ["ademe-activity-factors", "uk-desnz-conversion-factors-2026"], "country_data": ["owid-country-data"],
    "hs_industry_links": ["hs6-naics-2017"], "benchmarks": ["epa-calculator-reference"], "spend_factors": ["epa-supply-chain-factors"], "airports": ["ourairports"],
}
REGISTRY = ["dataset_id", "table_name", "title", "publisher", "url", "license", "license_url", "attribution", "obtained",
            "verification_status", "verification_note", "file_sha256", "rows_in_file", "rows_loaded", "loaded_at"]


def schema(db):
    """Create the reference tables if they are missing. Existing tables and rows are left alone."""
    for table, (columns, key, _, _) in TABLES.items():
        fields = ", ".join(f'"{c}" TEXT' for c in columns + [p for p in PROVENANCE if p not in columns])
        db.execute(f'CREATE TABLE IF NOT EXISTS {table}(id INTEGER PRIMARY KEY, {fields}, UNIQUE({", ".join(key)}))')
    db.execute(f'CREATE TABLE IF NOT EXISTS reference_datasets({", ".join(c + " TEXT" for c in REGISTRY)}, PRIMARY KEY(dataset_id))')
    db.commit()


def _insert(db, table, rows, source, sha256, rows_in_file):
    columns = TABLES[table][0] + [p for p in PROVENANCE if p not in TABLES[table][0]]
    stamp = now()
    added = 0
    with db:
        # A changed data file replaces that dataset's rows, so corrected or re-checked values take effect.
        known = db.execute("SELECT file_sha256 FROM reference_datasets WHERE dataset_id=?", (source["id"],)).fetchone()
        replaced = bool(known and known[0] != sha256)
        if replaced:
            db.execute(f"DELETE FROM {table} WHERE dataset_id=?", (source["id"],))
        for row in rows:
            full = {"dataset_id": source["id"], "source_title": source["title"], "source_url": source["url"], "license": source["license"],
                    "license_url": source["license_url"], "attribution": source["attribution"],
                    "verification_status": source["verification_status"], "loaded_at": stamp, **row}
            cursor = db.execute(f'INSERT OR IGNORE INTO {table}({", ".join(columns)}) VALUES ({", ".join("?" * len(columns))})',
                                [None if full.get(c) in ("", None) else str(full[c]) for c in columns])
            added += cursor.rowcount
        total = db.execute(f"SELECT count(*) FROM {table} WHERE dataset_id=?", (source["id"],)).fetchone()[0]
        db.execute(f'INSERT OR REPLACE INTO reference_datasets({", ".join(REGISTRY)}) VALUES ({", ".join("?" * len(REGISTRY))})',
                   [source["id"], table, source["title"], source["publisher"], source["url"], source["license"], source["license_url"],
                    source["attribution"], source.get("obtained"), source["verification_status"], source.get("verification_note"),
                    sha256, str(rows_in_file), str(total), stamp])
    return {"dataset": source["id"], "table": table, "rows_in_file": rows_in_file, "inserted": added, "already_present": rows_in_file - added, "replaced_older_version": replaced}


def load_dataset(db, folder, expected_table=None):
    """Load one dataset folder. Loading the same file twice adds nothing."""
    folder = Path(folder)
    if not (folder / "SOURCE.json").is_file():
        raise ValueError(f"No SOURCE.json in {folder}")
    source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    table = source.get("table")
    if table not in TABLES or table == "hs_codes":
        raise ValueError(f"Unknown table in SOURCE.json: {table!r}")
    if expected_table and table != expected_table:
        raise ValueError(f"This dataset belongs to the {table} table, not {expected_table}")
    for field in ("id", "title", "publisher", "url", "license", "license_url", "attribution", "verification_status", "file", "sha256"):
        if not str(source.get(field) or "").strip():
            raise ValueError(f"SOURCE.json must state {field}; data without a source and licence is not loaded")
    raw = (folder / source["file"]).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != source["sha256"]:
        raise ValueError("The data file does not match the checksum in SOURCE.json")
    columns, _, required, _ = TABLES[table]
    reader = csv.DictReader(raw.decode("utf-8").splitlines())
    allowed = set(columns) | {"license"}
    unknown = [c for c in reader.fieldnames or [] if c not in allowed]
    if unknown:
        raise ValueError(f"Unknown columns for {table}: {unknown}")
    rows = list(reader)
    for number, row in enumerate(rows, start=2):
        missing = [c for c in required if not str(row.get(c) or "").strip()]
        if missing:
            raise ValueError(f"Row {number} has no {', '.join(missing)}; nothing was loaded")
        for column in ("hs6", "hs4"):
            width = 6 if column == "hs6" else 4
            if row.get(column) and not re.fullmatch(rf"\d{{{width}}}", row[column]):
                raise ValueError(f"Row {number}: {column} must be {width} digits")
        if row.get("year") and not re.fullmatch(r"\d{4}", row["year"]):
            raise ValueError(f"Row {number}: year must be four digits")
    schema(db)
    return _insert(db, table, rows, source, digest, len(rows))


def load_hs_codes(db):
    """Load the bundled HS 2022 code list (every chapter, heading and subheading)."""
    from .hs import load_table
    codes, source = load_table()
    rows = [{"edition": source["edition"], "code": c["code"], "level": c["level"], "description": c["description"],
             "parent": c["parent"], "section": c["section"]} for c in sorted(codes.values(), key=lambda c: c["code"])]
    schema(db)
    return _insert(db, "hs_codes", rows, {
        "id": "hs2022", "title": source["title"], "publisher": "datasets/harmonized-system (data from UN Comtrade)", "url": source["url"],
        "license": source["license"], "license_url": source["license_url"], "attribution": source["attribution"],
        "obtained": "Loaded from reference/hs2022/harmonized-system.csv", "verification_status": "copied from the publisher's file",
        "verification_note": source["limitations"]}, source["sha256"], len(rows))


def load_table_datasets(db, table, folder=None):
    """Load the bundled dataset(s) for one table, or one named folder."""
    if table == "hs_codes":
        if folder:
            raise ValueError("The HS code list is always loaded from reference/hs2022")
        return [load_hs_codes(db)]
    folders = [Path(folder)] if folder else [DATASETS / name for name in BUNDLED[table]]
    return [load_dataset(db, f, table) for f in folders]


def load_all(db):
    return [result for table in TABLES for result in load_table_datasets(db, table)]


def counts(db):
    schema(db)
    return {table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}


def rows(db, table):
    if table not in TABLES and table != "reference_datasets":
        raise ValueError("Unknown reference table")
    schema(db)
    cursor = db.execute(f"SELECT * FROM {table} ORDER BY {'id' if table in TABLES else 'dataset_id'}")
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, r)) for r in cursor]


def frames(db):
    """Sheet name -> DataFrame for every reference table that holds rows, plus the dataset register."""
    import pandas as pd
    out = {}
    for table, (_, _, _, sheet) in TABLES.items():
        data = rows(db, table)
        if data:
            out[sheet] = pd.DataFrame(data)
    register = rows(db, "reference_datasets")
    if register:
        out["Reference datasets"] = pd.DataFrame(register)
    for frame in out.values():
        for column in frame.columns:
            if pd.api.types.is_object_dtype(frame[column]) or pd.api.types.is_string_dtype(frame[column]):
                frame[column] = frame[column].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "@", "\t", "\r")) else v)
    return out
