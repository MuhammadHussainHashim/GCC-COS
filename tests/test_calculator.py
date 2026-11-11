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
