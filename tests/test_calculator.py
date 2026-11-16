"""Calculator tests. Rows built by product() are SYNTHETIC TEST DATA; the last tests use the real bundled data."""
import json
from decimal import Decimal

import pytest

from gcc_cos import calculator, hs
from gcc_cos.cli import main

TABLE = hs.load_table()[0]
ROOT = hs.ROOT


def product(id, value, subcategory="Laptop", unit="kg CO2e/item", **extra):
    return {"id": id, "entity_type": "product", "data_kind": "published_product_footprint", "category": "electronics",
            "subcategory": subcategory, "manufacturer": "SYNTHETIC", "product_name": f"SYNTHETIC {id}",
            "normalized_value": value, "normalized_unit": unit, "document_title": "SYNTHETIC dataset",
            "source_url": "https://example.invalid/data", "license": "SYNTHETIC license", "attribution": "SYNTHETIC",
            "verification_status": "manufacturer_reported_not_independently_crosschecked", "issues": [], **extra}


ROWS = calculator.prepare([
    product(1, "100"), product(2, "200"), product(3, "600"),
    product(4, "50", "Smartphone"), product(5, "400", "Desktop"),
    product(6, "10", "ready-mix concrete", "kg CO2e/m3", category="construction", lifecycle_module="A1-A3"),
    product(7, "2", "ready-mix concrete", "kg CO2e/m3", category="construction", lifecycle_module="A2"),
    product(8, "30", "Hard drive"),
    {"id": 9, "entity_type": "industrial_inventory", "data_kind": "published_inventory", "normalized_value": "5", "normalized_unit": "kg CO2"},
])


def test_specific_record_times_quantity():
    r = calculator.estimate(ROWS, "record", "2", "3", TABLE)
    assert r["status"] == "ok" and r["basis"] == "one source record"
    assert Decimal(r["total_kg_co2e"]) == Decimal(r["total_lowest"]) == Decimal(r["total_highest"]) == 600
    assert r["quantity_unit"] == "items" and r["sources"][0]["license"] == "SYNTHETIC license"
    assert "footprint_not_verified" in r["flags"] and "median_of_several_records" not in r["flags"]


def test_hs_code_uses_median_and_shows_range_and_flags():
    r = calculator.estimate(ROWS, "hs", "8471.30", "2", TABLE)
    assert r["query"] == "847130" and r["records_used"] == 3
    assert (Decimal(r["per_unit"]), Decimal(r["per_unit_lowest"]), Decimal(r["per_unit_highest"])) == (200, 100, 600)
    assert (Decimal(r["total_kg_co2e"]), Decimal(r["total_lowest"]), Decimal(r["total_highest"])) == (400, 200, 1200)
    assert {"footprint_not_verified", "hs_code_not_verified", "median_of_several_records"} <= set(r["flags"])
    assert r["hs_description"] == TABLE["847130"]["description"]


def test_heading_query_covers_several_types():
    r = calculator.estimate(ROWS, "hs", "8471", "1", TABLE)
    assert r["records_used"] == 4 and "covers_several_product_types" in r["flags"]
    assert Decimal(r["per_unit"]) == 300  # median of 100, 200, 400, 600


def test_product_type_is_case_insensitive():
    assert calculator.estimate(ROWS, "type", "smartphone", "4", TABLE)["total_kg_co2e"] == "200"


@pytest.mark.parametrize("kind, value, quantity, status", [
    ("hs", "847141", "1", "heading_only"),      # desktops are mapped to heading 8471 only
    ("hs", "010121", "1", "no_data"),           # real code, no footprint data
    ("hs", "123456", "1", "unknown_hs_code"),   # not an HS 2022 code
    ("hs", "84713", "1", "unknown_hs_code"),
    ("type", "Bicycle", "1", "no_data"),
    ("type", "Hard drive", "1", "ok"),          # unmapped HS, but its footprint is still usable by type
    ("record", "999", "1", "unknown_record"),
    ("record", "9", "1", "unknown_record"),     # inventory totals are never products
    ("record", "1", "0", "invalid_quantity"),
    ("record", "1", "-2", "invalid_quantity"),
    ("record", "1", "abc", "invalid_quantity"),
    ("record", "1", "nan", "invalid_quantity"),
    ("sku", "1", "1", "unknown_kind"),
    ("type", "ready-mix concrete", "1", "mixed_units_or_scopes"),
])
def test_lines_without_a_value_are_reported_not_guessed(kind, value, quantity, status):
    r = calculator.estimate(ROWS, kind, value, quantity, TABLE)
    assert r["status"] == status
    if status != "ok":
        assert r["total_kg_co2e"] is None and r["message"]


def test_mixed_scope_lists_record_choices():
    r = calculator.estimate(ROWS, "type", "ready-mix concrete", "1", TABLE)
    assert {c["id"] for c in r["record_choices"]} == {6, 7}


def test_totals_keep_lifecycle_scopes_apart_and_exclude_missing_lines():
    result = calculator.calculate(ROWS, [
        {"kind": "record", "value": "1", "quantity": "2"}, {"kind": "type", "value": "Smartphone", "quantity": "1"},
        {"kind": "record", "value": "6", "quantity": "5"}, {"kind": "hs", "value": "010121", "quantity": "1"}], TABLE)
    totals = {t["scope"]: Decimal(t["total_kg_co2e"]) for t in result["totals"]}
    assert totals == {calculator.FULL_LIFECYCLE: 250, "EPD module A1-A3": 50}
    assert result["grand_total_kg_co2e"] is None and not result["complete"] and result["missing_lines"] == [4]
    text = " ".join(result["warnings"])
    assert "NOT VERIFIED" in text and "INCOMPLETE" in text and "must not be added together" in text and "Transport" in text
    assert "production_stage_only_not_full_lifecycle" in result["lines"][2]["flags"]
    assert result["lines"][2]["quantity_unit"] == "m3"


def test_single_scope_gives_grand_total():
    result = calculator.calculate(ROWS, [{"kind": "record", "value": "1", "quantity": "1.5"}], TABLE)
    assert result["grand_total_kg_co2e"] == "150.0" and result["complete"]


def test_verified_record_is_not_flagged():
    rows = calculator.prepare([product(1, "100", verification_status="independently_crosschecked")])
    assert "footprint_not_verified" not in calculator.estimate(rows, "record", "1", "1", TABLE)["flags"]


def test_expired_declaration_is_flagged():
    rows = calculator.prepare([product(1, "100", issues=["declaration_expired"])])
    assert "declaration_expired" in calculator.estimate(rows, "record", "1", "1", TABLE)["flags"]


def test_read_basket(tmp_path):
    path = tmp_path / "basket.csv"
    path.write_text("HS_Code,product_type,Quantity,note\n847130,,3,laptops\n,Smartphone,2,\n,,,\n", encoding="utf-8")
    assert calculator.read_basket(path) == [
        {"kind": "hs", "value": "847130", "quantity": "3", "note": "laptops"},
        {"kind": "type", "value": "Smartphone", "quantity": "2", "note": ""}]


@pytest.mark.parametrize("text, message", [
    ("hs_code,amount\n847130,1\n", "quantity column"),
    ("quantity,name\n1,x\n", "at least one of"),
    ("hs_code,product_type,quantity\n847130,Laptop,1\n", "exactly one"),
    ("hs_code,product_type,quantity\n,,1\n", "exactly one"),
    ("hs_code,quantity\n", "no rows"),
])
def test_bad_baskets_are_refused(tmp_path, text, message):
    path = tmp_path / "basket.csv"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        calculator.read_basket(path)


def test_write_result_formats(tmp_path):
    import pandas as pd
    result = calculator.calculate(ROWS, [{"kind": "hs", "value": "847130", "quantity": "2", "note": "=SUM(A1)"}], TABLE)
    assert json.loads(calculator.write_result(result, tmp_path / "r.json").read_text(encoding="utf-8"))["totals"]
    frame = pd.read_csv(calculator.write_result(result, tmp_path / "r.csv"))
    assert frame.loc[0, "total_kg_co2e"] == 400 and frame.loc[0, "note"] == "'=SUM(A1)"
    sheets = pd.read_excel(calculator.write_result(result, tmp_path / "r.xlsx"), sheet_name=None)
    assert set(sheets) == {"Lines", "Totals", "Warnings"}
    with pytest.raises(ValueError):
        calculator.write_result(result, tmp_path / "r.txt")


@pytest.fixture(scope="module")
def real_db(tmp_path_factory):
    from gcc_cos.ingest import ingest, load_registry
    from gcc_cos.storage import connect
    folder = tmp_path_factory.mktemp("calc")
    db = connect(folder / "real.sqlite")
    for phase in ("phase2", "phase3"):
        manifest = json.loads((ROOT / f"examples/{phase}/local-files.json").read_text(encoding="utf-8"))
        for source in load_registry(ROOT / f"examples/{phase}/sources.json"):
            if source["id"] in manifest:
                ingest(db, source, folder / "raw", str(ROOT / manifest[source["id"]]), [])
    db.close()
    return folder / "real.sqlite"


def test_real_data_example_basket(real_db, capsys):
    from gcc_cos.storage import connect, records
    db = connect(real_db)
    try:
        rows = records(db)
    finally:
        db.close()
    assert len(rows) == 1241
    result = calculator.calculate(rows, calculator.read_basket(ROOT / "examples/calculator/company-basket.csv"))
    assert [r["status"] for r in result["lines"]] == ["ok", "ok", "ok", "ok", "heading_only", "no_data"]
    laptops = result["lines"][0]
    values = sorted(Decimal(str(r["normalized_value"])) for r in rows if r.get("subcategory") == "Laptop")
    assert laptops["records_used"] == len(values) == 452
    assert Decimal(laptops["per_unit"]) == (values[225] + values[226]) / 2
    assert Decimal(laptops["total_kg_co2e"]) == Decimal(laptops["per_unit"]) * 120
    assert "ODbL" in laptops["sources"][0]["license"]
    assert sum(Decimal(r["total_kg_co2e"]) for r in result["lines"] if r["status"] == "ok") == Decimal(result["grand_total_kg_co2e"])
    personal = calculator.calculate(rows, calculator.read_basket(ROOT / "examples/calculator/personal-basket.csv"))
    assert personal["complete"] and len(personal["totals"]) == 1


def test_command_line(real_db, tmp_path, capsys):
    code = main(["--db", str(real_db), "calculate", "--item", "type=Smartphone:2", "--item", "record=1:1", "--output", str(tmp_path / "out.json")])
    out = capsys.readouterr().out
    assert code == 0 and "TOTAL Full lifecycle" in out and "NOT VERIFIED" in out
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))["complete"] is True
    assert main(["--db", str(real_db), "calculate", "--item", "hs=010121:1"]) == 2
    with pytest.raises(SystemExit):
        main(["--db", str(real_db), "calculate", "--item", "nonsense"])


def test_dashboard_calculator_tab(real_db, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import gcc_cos.storage
    original = gcc_cos.storage.connect
    monkeypatch.setattr(gcc_cos.storage, "connect", lambda _: original(real_db))
    monkeypatch.chdir(ROOT)
    app = AppTest.from_file(str(ROOT / "dashboard.py")).run(timeout=60)
    assert not app.exception
    assert any("Footprint calculator" in s.value for s in app.subheader)
    app.session_state["calculator_basket"] = [{"kind": "type", "value": "Laptop", "quantity": "2"}]
    app.run(timeout=60)
    assert not app.exception
    assert any("Total, Full lifecycle" in m.label for m in app.metric)


def staged(id, value, share, years, maker="SYNTHETIC", subcategory="Laptop"):
    return product(id, value, subcategory, manufacturer=maker, lifetime_years=years, evidence={"raw": {"gwp_use_ratio": share}})


STAGED = calculator.prepare([staged(1, "100", "0.2", "4"), staged(2, "200", "0.4", "4"), staged(3, "300", "", "5"),
                             staged(4, "50", "7.5", None, subcategory="Smartphone"), staged(5, "1000", "0.9", "5", maker="OTHER")])


def test_use_phase_split_and_per_year_for_one_record():
    r = calculator.estimate(STAGED, "record", "2", "3", TABLE)
    assert (Decimal(r["use_phase_kg_co2e"]), Decimal(r["making_and_other_kg_co2e"])) == (240, 360)
    assert Decimal(r["per_year_kg_co2e"]) == 150 and r["lifetime_years"] == "4"


def test_median_line_uses_median_share_from_records_that_report_one():
    r = calculator.estimate(STAGED, "type", "Laptop", "1", TABLE)
    assert Decimal(r["per_unit"]) == 250 and r["use_phase_share_records"] == 3   # record 3 reports no share
    assert Decimal(r["use_phase_share"]) == Decimal("0.4") and Decimal(r["use_phase_kg_co2e"]) == 100
    assert "wide_range" in r["flags"]                                            # 1000 / 100 > 3


def test_out_of_range_share_and_missing_lifetime_are_not_used():
    r = calculator.estimate(STAGED, "record", "4", "1", TABLE)
    assert r["use_phase_share"] is None and r["use_phase_kg_co2e"] is None and r["per_year_kg_co2e"] is None


def test_same_maker_comparison_needs_three_records():
    r = calculator.estimate(STAGED, "record", "1", "1", TABLE)
    assert (r["same_maker_records"], Decimal(r["same_maker_median"]), r["versus_same_maker_percent"]) == (3, 200, "-50.0")
    assert calculator.estimate(STAGED, "record", "5", "1", TABLE)["same_maker_median"] is None
    assert calculator.estimate(STAGED, "type", "Laptop", "1", TABLE)["same_maker_median"] is None


def test_hotspot_stage_totals_and_per_person():
    result = calculator.calculate(STAGED, [{"kind": "record", "value": "1", "quantity": "1"}, {"kind": "record", "value": "2", "quantity": "2"}], TABLE, people="4")
    total = result["totals"][0]
    assert (total["biggest_line"], total["biggest_line_share_percent"]) == (2, "80.0")
    assert [r["share_of_total_percent"] for r in result["lines"]] == ["20.0", "80.0"]
    assert (Decimal(total["use_phase_kg_co2e"]), Decimal(total["making_and_other_kg_co2e"])) == (180, 320)
    assert Decimal(total["per_year_kg_co2e"]) == 125 and Decimal(total["per_person_kg_co2e"]) == 125


def test_stage_total_is_withheld_when_a_line_has_no_share():
    result = calculator.calculate(STAGED, [{"kind": "record", "value": "1", "quantity": "1"}, {"kind": "record", "value": "4", "quantity": "1"}], TABLE)
    assert result["totals"][0]["use_phase_kg_co2e"] is None and result["totals"][0]["per_person_kg_co2e"] is None


@pytest.mark.parametrize("people", ["0", "-1", "abc"])
def test_bad_people_number_is_refused(people):
    with pytest.raises(ValueError, match="People"):
        calculator.calculate(STAGED, [{"kind": "record", "value": "1", "quantity": "1"}], TABLE, people=people)


def test_real_data_reports_stage_split(real_db):
    from gcc_cos.storage import connect, records
    db = connect(real_db)
    try:
        rows = records(db)
    finally:
        db.close()
    r = calculator.estimate(calculator.prepare(rows), "record", "1", "1", TABLE)   # Apple 13-inch MacBook Air: 161 kg, 15% use
    assert Decimal(r["use_phase_kg_co2e"]) == Decimal("24.15") and r["lifetime_years"] == "3"
    assert r["same_maker_records"] >= 3


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    from gcc_cos import refdata
    from gcc_cos.storage import connect
    db = connect(tmp_path_factory.mktemp("calcref") / "ref.sqlite")
    refdata.load_table_datasets(db, "activity_factors")
    refdata.load_table_datasets(db, "country_data")
    refdata.load_table_datasets(db, "product_averages")
    refdata.load_table_datasets(db, "reference_values")
    book = calculator.reference_from(db)
    db.close()
    return book


def test_activity_line_uses_the_published_factor_and_says_it_is_french(reference):
    r = calculator.estimate(ROWS, "activity", "busthermique", "120", TABLE, reference)
    assert r["status"] == "ok" and r["quantity_unit"] == "km" and r["unit"] == "kg CO2e per km"
    assert Decimal(r["per_unit"]) == Decimal("0.12242") and Decimal(r["total_kg_co2e"]) == Decimal("14.6904")
    assert r["scope"] == calculator.ACTIVITY_SCOPE and "average_for_france_not_local" in r["flags"]
    assert "MIT" in r["sources"][0]["license"] and r["label"] == "Bus (combustion) (Transport)"
    assert calculator.estimate(ROWS, "activity", "streamingvideo", "2", TABLE, reference)["quantity_unit"] == "hour of video streaming"


def test_electricity_line_uses_the_country_figure(reference):
    r = calculator.estimate(ROWS, "electricity", "pak", "300", TABLE, reference)
    assert r["status"] == "ok" and r["query"] == "PAK" and r["quantity_unit"] == "kWh"
    assert Decimal(r["per_unit"]) == Decimal("0.34656") and Decimal(r["total_kg_co2e"]) == Decimal("103.968")
    assert r["label"] == "Electricity in Pakistan (2025)" and "CC BY 4.0" in r["sources"][0]["license"]
    assert "country_average_generation_not_your_supplier" in r["flags"]


@pytest.mark.parametrize("kind, value, status", [("activity", "teleport", "unknown_activity"), ("electricity", "XXX", "unknown_country")])
def test_unknown_activity_or_country_gets_no_value(reference, kind, value, status):
    assert calculator.estimate(ROWS, kind, value, "1", TABLE, reference)["status"] == status


def test_activity_lines_need_reference_data():
    assert calculator.estimate(ROWS, "activity", "busthermique", "1", TABLE)["status"] == "reference_data_missing"
    assert calculator.estimate(ROWS, "electricity", "PAK", "1", TABLE, {"activity": {}, "electricity": {}})["status"] == "reference_data_missing"


def test_mixed_basket_keeps_parts_apart_and_gives_a_labelled_indication(reference, tmp_path):
    path = tmp_path / "mixed.csv"
    path.write_text("product_type,activity_id,electricity_country,quantity\nSmartphone,,,1\n,busthermique,,100\n,chauffagegaz,,80\n,,PAK,300\n", encoding="utf-8")
    result = calculator.calculate(ROWS, calculator.read_basket(path), TABLE, reference=reference)
    totals = {t["scope"]: Decimal(t["total_kg_co2e"]) for t in result["totals"]}
    assert set(totals) == {calculator.FULL_LIFECYCLE, calculator.ACTIVITY_SCOPE, calculator.ELECTRICITY_SCOPE}
    assert totals[calculator.ACTIVITY_SCOPE] == Decimal("12.242") + Decimal("80") * Decimal(reference["activity"]["chauffagegaz"]["value_metric"])
    assert result["grand_total_kg_co2e"] is None and Decimal(result["all_parts_together_kg_co2e"]) == sum(totals.values())
    text = " ".join(result["warnings"])
    assert "averages for France" in text and "average for electricity generation" in text and "must not be added together" in text


def test_command_line_activity_and_electricity(real_db, capsys):
    assert main(["--db", str(real_db), "calculate", "--item", "activity=busthermique:10"]) == 2      # reference data not loaded yet
    assert "Reference data is not loaded" in capsys.readouterr().out
    assert main(["--db", str(real_db), "load-reference-data"]) == 0
    capsys.readouterr()
    assert main(["--db", str(real_db), "calculate", "--item", "activity=busthermique:10", "--item", "electricity=PAK:100", "--item", "type=Laptop:1"]) == 0
    out = capsys.readouterr().out
    assert "Electricity in Pakistan" in out and "ALL PARTS TOGETHER" in out and "averages for France" in out


def test_food_line_uses_agribalyse(reference):
    r = calculator.estimate(ROWS, "food", "11172", "2", TABLE, reference)
    assert r["status"] == "ok" and r["quantity_unit"] == "kg" and r["scope"] == calculator.FOOD_SCOPE
    assert Decimal(r["per_unit"]) == Decimal("7.58") and Decimal(r["total_kg_co2e"]) == Decimal("15.16")
    assert "Licence Ouverte" in r["sources"][0]["license"] and "average_for_france_not_local" in r["flags"]
    assert calculator.estimate(ROWS, "food", "99999999", "1", TABLE, reference)["status"] == "unknown_food"


def test_uk_conversion_factor_line_is_labelled_as_uk(reference):
    r = calculator.estimate(ROWS, "activity", "desnz2026:21_316_3160_11_1", "1000", TABLE, reference)
    assert r["status"] == "ok" and Decimal(r["total_kg_co2e"]) == Decimal("229.28") and r["quantity_unit"] == "passenger.km"
    assert "average_for_another_country_not_local" in r["flags"] and "United Kingdom" in r["scope"]


def test_transcribed_cbam_record_counts_as_checked_when_gov_uk_agrees(reference):
    rows = calculator.prepare([product(1, "1.375", "Cement", "kg CO2e/kg", data_kind="published_generic_factor", product_name="CN 25232900: Portland cement",
                                       original_value="1.375", verification_status="transcribed_from_source_page_not_digit_checked"),
                               product(2, "9.999", "Cement", "kg CO2e/kg", data_kind="published_generic_factor", product_name="CN 25232100: White cement",
                                       original_value="9.999", verification_status="transcribed_from_source_page_not_digit_checked")])
    agreed = calculator.estimate(rows, "record", "1", "1", TABLE, reference)
    assert "transcribed_not_checked_against_source" not in agreed["flags"] and "value_checked_against_gov_uk" in agreed["flags"]
    differs = calculator.estimate(rows, "record", "2", "1", TABLE, reference)
    assert "transcribed_not_checked_against_source" in differs["flags"]       # 9.999 is not the GOV.UK value
    assert "transcribed_not_checked_against_source" in calculator.estimate(rows, "record", "1", "1", TABLE)["flags"]   # no reference loaded
