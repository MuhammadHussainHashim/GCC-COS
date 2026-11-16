import csv
import json

import pytest
from openpyxl import Workbook

from gcc_cos.research import _csv_cell, prepare_research


HEADERS = [
    "Record ID", "Brand", "Model / report family", "Configuration / source label",
    "Footprint (kg CO2e)", "Original reported footprint", "Original unit",
    "Data status", "Value type", "Source / report URL", "Lifecycle boundary",
    "Functional unit", "Evidence / notes",
]


def _workbook(path, records):
    book = Workbook()
    sheet = book.active
    sheet.title = "Footprints"
    sheet.append(HEADERS)
    for row in records:
        sheet.append([row.get(header) for header in HEADERS])
    book.save(path)


def test_research_keeps_unverified_estimates_separate(tmp_path):
    workbook = tmp_path / "source.xlsx"
    row = {
        "Record ID": "CHAT0162", "Brand": "Samsung", "Model / report family": "Galaxy S26 Ultra",
        "Footprint (kg CO2e)": 55, "Original unit": "kg CO2e",
        "Data status": "User supplied; unverified", "Value type": "Estimate",
        "Source / report URL": "", "Functional unit": "one phone",
    }
    _workbook(workbook, [row, {**row, "Record ID": "CHAT0163"}])
    summary = prepare_research(workbook, tmp_path / "review")
    assert summary["total_rows_preserved"] == 2
    assert summary["independently_verified_rows"] == 0
    assert summary["exact_duplicate_candidate_rows"] == 2
    with (tmp_path / "review" / "records_review.csv").open(encoding="utf-8-sig") as stream:
        records = list(csv.DictReader(stream))
    assert len(records) == 2
    assert all(r["review_status"] == "pending_original_report_review" for r in records)
    assert all("ESTIMATE_NOT_VERIFIED" in r["review_flags"] for r in records)
    assert all("MISSING_REPORT_URL" in r["review_flags"] for r in records)
    assert all("POSSIBLE_EXACT_DUPLICATE" in r["review_flags"] for r in records)
    assert json.loads((tmp_path / "review" / "audit_summary.json").read_text())["pending_review_rows"] == 2


def test_conflicts_are_flagged_but_not_merged(tmp_path):
    workbook = tmp_path / "input.xlsx"
    base = {
        "Brand": "Example", "Model / report family": "Device 1", "Configuration / source label": "128GB",
        "Original unit": "kg CO2e", "Data status": "Workbook extract; not independently verified",
        "Value type": "Reported absolute footprint", "Source / report URL": "https://example.org/report",
        "Lifecycle boundary": "Cradle-to-grave", "Functional unit": "1 device",
    }
    _workbook(workbook, [{**base, "Record ID": "A", "Footprint (kg CO2e)": 48},
                         {**base, "Record ID": "B", "Footprint (kg CO2e)": 52}])
    summary = prepare_research(workbook, tmp_path / "review")
    assert summary["same_report_value_conflict_rows"] == 2
    assert summary["total_rows_preserved"] == 2
    assert summary["exact_duplicate_candidate_rows"] == 0


def test_rejects_missing_headers_or_repeated_ids(tmp_path):
    workbook = tmp_path / "invalid.xlsx"
    _workbook(workbook, [{"Record ID": "ONE"}, {"Record ID": "ONE"}])
    with pytest.raises(ValueError, match="Repeated record ID"):
        prepare_research(workbook, tmp_path / "out")
    book = Workbook()
    book.active.title = "Unknown"
    book.save(workbook)
    with pytest.raises(ValueError, match="needs sheet"):
        prepare_research(workbook, tmp_path / "out")


def test_research_csv_cells_are_safe_to_open_in_spreadsheets():
    assert _csv_cell('=HYPERLINK("https://example.org")').startswith("'=")
    assert _csv_cell(" @SUM(1,2)").startswith("' ")
    assert _csv_cell("Ordinary device") == "Ordinary device"
