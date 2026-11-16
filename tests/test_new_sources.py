"""UK CBAM default values and ADEME everyday products (examples/phase5). These tests use the real bundled files."""
import csv
import json
from decimal import Decimal

import pytest

from gcc_cos import calculator, hs
from gcc_cos.ingest import ingest, load_registry
from gcc_cos.model import is_item, is_product
from gcc_cos.storage import connect, records

ROOT = hs.ROOT
TABLE = hs.load_table()[0]


def load(db, folder, phase):
    manifest = json.loads((ROOT / f"examples/{phase}/local-files.json").read_text(encoding="utf-8"))
    results = []
    for source in load_registry(ROOT / f"examples/{phase}/sources.json"):
        if source["id"] in manifest:
            results.append(ingest(db, source, folder / "raw", str(ROOT / manifest[source["id"]]), []))
    return results


@pytest.fixture(scope="module")
def everything(tmp_path_factory):
    folder = tmp_path_factory.mktemp("phase5")
    db = connect(folder / "all.sqlite")
    for phase in ("phase2", "phase3"):
        load(db, folder, phase)
    first = load(db, folder, "phase5")
    again = load(db, folder, "phase5")
    rows = records(db)
    db.close()
    return first, again, rows


def test_new_sources_load_once_and_never_repeat(everything):
    first, again, rows = everything
    assert {r["source"]: (r["status"], r["inserted"]) for r in first} == {"uk-cbam-defaults": ("completed", 570), "ademe-impactco2": ("completed", 201)}
    assert all(r["inserted"] == 0 and r["duplicates"] > 0 for r in again)
    assert len(rows) == 1241 + 570 + 201
    assert sum(is_product(r) for r in rows) == 1241          # the original product records are untouched
    assert sum(is_item(r) for r in rows) == 2012


def test_nothing_new_repeats_an_existing_product_type(everything):
    rows = everything[2]
    old_types = {str(r["subcategory"]).casefold() for r in rows if is_product(r)}
    new_types = {str(r["subcategory"]).casefold() for r in rows if r["source_id"] == "ademe-impactco2"}
    assert not old_types & new_types and len(new_types) == 201
    provenance = json.loads((ROOT / "examples/phase5/provenance.json").read_text(encoding="utf-8"))
    assert {x["already_covered_by_product_type"] for x in provenance["ademe"]["left_out_as_repeats"]} == {"Laptop", "Smartphone", "Tablet", "Monitor", "Desktop"}


def test_ademe_values_equal_the_unmodified_upstream_file():
    upstream = json.loads((ROOT / "examples/phase5/ademe-upstream/values.json").read_text(encoding="utf-8"))
    with open(ROOT / "examples/phase5/ademe-common-products.csv", newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 201
    for row in rows:
        source = upstream[row["id"]]
        assert Decimal(row["kg_co2e"]) == Decimal(str(source["value"])) / 1000
        label = source["en"].lower()
        assert row["declared_unit"] == ("kg" if label.startswith("kg") else "l" if label.startswith("liter") else "item")


def test_cbam_records_carry_a_source_given_hs_code_and_are_flagged(everything):
    rows = [r for r in everything[2] if r["source_id"] == "uk-cbam-defaults"]
    cement = next(r for r in rows if r["product_name"].startswith("CN 25232900:"))
    assert (cement["hs6"], cement["hs_edition"], cement["normalized_unit"], Decimal(cement["normalized_value"])) == ("252329", "HS 2022", "kg CO2e/kg", Decimal("1.375"))
    assert cement["verification_status"] == "transcribed_from_source_page_not_digit_checked" and "Open Government Licence" in cement["license"]
    assert all(r["hs6"] in TABLE and r["product_name"][3:9] == r["hs6"] for r in rows) and len({r["hs6"] for r in rows}) == 283
    annotated = hs.annotate([cement])[0]
    assert (annotated["hs_code"], annotated["hs_status"]) == ("252329", "exact_rule")


def test_calculator_uses_the_new_data_and_keeps_scopes_apart(everything):
    rows = everything[2]
    result = calculator.calculate(rows, [
        {"kind": "hs", "value": "25232900", "quantity": "1000"},     # 8-digit commodity code, quantity in kg
        {"kind": "hs", "value": "252329", "quantity": "1000"},
        {"kind": "type", "value": "Beef", "quantity": "2"},
        {"kind": "type", "value": "Beer", "quantity": "3"},
        {"kind": "type", "value": "Laptop", "quantity": "1"},
        {"kind": "hs", "value": "12345678", "quantity": "1"}])
    lines = result["lines"]
    assert [r["status"] for r in lines] == ["ok", "ok", "ok", "ok", "ok", "unknown_hs_code"]
    assert Decimal(lines[0]["total_kg_co2e"]) == Decimal(lines[1]["total_kg_co2e"]) == 1375 and lines[0]["quantity_unit"] == "kg"
    assert {"transcribed_not_checked_against_source", "average_or_default_value_not_a_specific_product", "footprint_not_verified"} <= set(lines[0]["flags"])
    assert "hs_code_not_verified" not in lines[1]["flags"]            # this code comes from the source, not from a proposed mapping
    assert Decimal(lines[2]["total_kg_co2e"]) == Decimal("56.01834") and lines[3]["quantity_unit"] == "litres"
    assert lines[4]["records_used"] == 452 and lines[4]["use_phase_share"] is not None and lines[2]["use_phase_share"] is None
    scopes = {t["scope"] for t in result["totals"]}
    assert scopes == {"Embedded emissions (UK CBAM default value)", "Full lifecycle average (ADEME Impact CO2)", calculator.FULL_LIFECYCLE}
    assert result["grand_total_kg_co2e"] is None and any("typed in from a web page" in w for w in result["warnings"])


def test_hs_coverage_counts_source_given_codes(everything):
    summary = hs.coverage(hs.annotate([r for r in everything[2] if is_item(r)]))
    assert summary["by_status"] == {"proposed_not_verified": 1177, "exact_rule": 570, "unmapped": 64 + 201}
