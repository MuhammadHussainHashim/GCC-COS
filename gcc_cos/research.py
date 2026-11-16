"""Quarantine a legacy manufacturer research workbook for evidence review.

This is deliberately separate from production ingestion. A number in a research
spreadsheet is NOT an independently verified product carbon footprint.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse

from openpyxl import load_workbook


SOURCE_SHEET = "Footprints"
REQUIRED_COLUMNS = {
    "Record ID", "Brand", "Model / report family", "Footprint (kg CO2e)",
    "Data status", "Value type", "Source / report URL",
}
MAPPING = {
    "Record ID": "record_id",
    "Brand": "brand",
    "Sector": "sector",
    "Category": "category",
    "Model / report family": "product_model",
    "Configuration / source label": "configuration",
    "Footprint (kg CO2e)": "footprint_kg_co2e_unverified",
    "Lower bound (kg CO2e)": "lower_bound_kg_co2e_unverified",
    "Upper bound (kg CO2e)": "upper_bound_kg_co2e_unverified",
    "Original reported footprint": "original_reported_footprint",
    "Original unit": "original_unit",
    "Functional unit": "functional_unit",
    "Lifecycle boundary": "lifecycle_boundary",
    "Reported statistic / basis": "reported_statistic",
    "Value type": "value_type",
    "Data status": "source_data_status",
    "Source record ID": "source_record_id",
    "Source page": "source_page",
    "Source / report URL": "source_report_url",
    "Evidence / notes": "evidence_note",
    "Region": "region",
    "Pasted phase breakdown (Prod / Dist / Use / Disp)": "user_supplied_phase_breakdown",
}
NUMERIC_COLUMNS = {
    "footprint_kg_co2e_unverified", "lower_bound_kg_co2e_unverified",
    "upper_bound_kg_co2e_unverified",
}
OUTPUT_COLUMNS = list(MAPPING.values()) + [
    "review_status", "review_flags", "source_workbook_sha256",
]


def _string(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return format(value, ".15g")
    return str(value).strip()


def _csv_cell(value):
    """Prevent an untrusted source cell from executing as an Excel formula."""
    if isinstance(value, str) and value and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _valid_number(value):
    if not value:
        return False
    try:
        return math.isfinite(float(value)) and float(value) >= 0
    except (ValueError, OverflowError):
        return False


def _flags(row):
    flags = []
    value = row["footprint_kg_co2e_unverified"]
    if not value:
        flags.append("NO_TOTAL_KG_CO2E")
    elif not _valid_number(value):
        flags.append("INVALID_TOTAL_KG_CO2E")
    elif float(value) == 0:
        flags.append("ZERO_VALUE_REVIEW")
    for field in NUMERIC_COLUMNS - {"footprint_kg_co2e_unverified"}:
        if row[field] and not _valid_number(row[field]):
            flags.append("INVALID_" + field.upper())
    if not row["source_report_url"]:
        flags.append("MISSING_REPORT_URL")
    else:
        parsed = urlparse(row["source_report_url"])
        if parsed.scheme != "https" or not parsed.netloc:
            flags.append("NON_HTTPS_REPORT_URL")
    if not row["lifecycle_boundary"]:
        flags.append("MISSING_LIFECYCLE_BOUNDARY")
    if not row["functional_unit"]:
        flags.append("MISSING_FUNCTIONAL_UNIT")
    context = " ".join((row["source_data_status"], row["value_type"], row["evidence_note"])).lower()
    if "estimate" in context or "approximate" in context:
        flags.append("ESTIMATE_NOT_VERIFIED")
    if "user supplied" in context or row["record_id"].startswith("CHAT"):
        flags.append("USER_SUPPLIED_NOT_VERIFIED")
    if "unverified" in context or "not independently verified" in context:
        flags.append("INDEPENDENT_VERIFICATION_MISSING")
    if not row["original_unit"]:
        flags.append("MISSING_ORIGINAL_UNIT")
    return sorted(set(flags))


def prepare_research(workbook: str | Path, output_dir: str | Path) -> dict:
    """Preserve each row, flag duplicates/conflicts, and mark ALL rows pending review.

    No research row is inserted into the audited GCC-COS observations database.
    """
    workbook = Path(workbook)
    output_dir = Path(output_dir)
    if not workbook.is_file():
        raise FileNotFoundError(workbook)
    digest = _sha256(workbook)
    book = load_workbook(workbook, read_only=True, data_only=True)
    try:
        if SOURCE_SHEET not in book:
            raise ValueError(f"Workbook needs sheet {SOURCE_SHEET!r}")
        sheet_rows = iter(book[SOURCE_SHEET].values)
        headers = next(sheet_rows, None)
        if headers is None:
            raise ValueError("Empty research sheet")
        missing = REQUIRED_COLUMNS - set(headers)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        if len(headers) != len(set(headers)):
            raise ValueError("Duplicate header names are not supported")
        records = []
        ids = set()
        for number, values in enumerate(sheet_rows, start=2):
            if not any(v is not None for v in values):
                continue
            raw = dict(zip(headers, values))
            record = {output: _string(raw.get(source)) for source, output in MAPPING.items()}
            if not record["record_id"]:
                raise ValueError(f"Missing record ID at sheet row {number}")
            if record["record_id"] in ids:
                raise ValueError(f"Repeated record ID: {record['record_id']}")
            ids.add(record["record_id"])
            record["review_status"] = "pending_original_report_review"
            record["source_workbook_sha256"] = digest
            record["review_flags"] = _flags(record)
            records.append(record)
    finally:
        book.close()

    # Exact candidate duplicates are flagged; none are silently removed.
    duplicate_groups = defaultdict(list)
    conflict_groups = defaultdict(list)
    for row in records:
        exact = tuple(row[k].casefold() for k in (
            "brand", "product_model", "configuration", "footprint_kg_co2e_unverified",
            "source_report_url", "lifecycle_boundary", "value_type"))
        duplicate_groups[exact].append(row)
        if row["source_report_url"] and row["footprint_kg_co2e_unverified"]:
            group = tuple(row[k].casefold() for k in (
                "brand", "product_model", "configuration", "source_report_url",
                "lifecycle_boundary"))
            conflict_groups[group].append(row)
    exact_candidates = [r for group in duplicate_groups.values() if len(group) > 1 for r in group]
    conflicts = []
    for group in conflict_groups.values():
        if len({r["footprint_kg_co2e_unverified"] for r in group}) > 1:
            conflicts.extend(group)
    for row in exact_candidates:
        row["review_flags"].append("POSSIBLE_EXACT_DUPLICATE")
    for row in conflicts:
        row["review_flags"].append("POSSIBLE_CONFLICT_SAME_REPORT")

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, selection in (("records_review.csv", records), ("duplicate_candidates.csv", exact_candidates),
                                ("conflicting_report_values.csv", conflicts)):
        with (output_dir / filename).open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for row in selection:
                safe_row = {**row, "review_flags": "|".join(sorted(set(row["review_flags"]))) }
                writer.writerow({key: _csv_cell(value) for key, value in safe_row.items()})
    summary = {
        "input_filename": workbook.name,
        "input_sha256": digest,
        "total_rows_preserved": len(records),
        "independently_verified_rows": 0,
        "pending_review_rows": len(records),
        "rows_with_total_kg_co2e": sum(_valid_number(r["footprint_kg_co2e_unverified"]) for r in records),
        "exact_duplicate_candidate_rows": len(exact_candidates),
        "same_report_value_conflict_rows": len(conflicts),
        "brand_counts": dict(sorted(Counter(r["brand"] for r in records).items())),
        "flag_counts": dict(sorted(Counter(flag for r in records for flag in set(r["review_flags"])).items())),
        "warning": "Research extracts only; not approved, verified or safe for regulatory/credit claims.",
    }
    (output_dir / "audit_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary
