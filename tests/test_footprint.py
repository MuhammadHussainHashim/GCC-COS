"""Household calculator: approvals, read-only repository, calculation rules and the versioned API.

The reference data is the real bundled data. Product records, approvals and the extra rows
added for the duplicate and same-country cases are SYNTHETIC TEST DATA and say so.
"""
import json
import shutil
import sqlite3
from decimal import Decimal

import pytest

from gcc_cos import approvals, refdata
from gcc_cos.cli import main
from gcc_cos.footprint import catalog, report
from gcc_cos.footprint.engine import calculate
from gcc_cos.footprint.repository import Repository, connect_read_only, great_circle_km
from gcc_cos.storage import connect, insert

DESNZ, OWID, FOODS, SYN = "uk-desnz-conversion-factors-2026", "owid-country-data", "agribalyse-3.2-synthesis", "synthetic-products"
USE = "household_calculator"


def product(name, value="100", unit="item", **extra):
    return {"entity_type": "product", "data_kind": "published_product_footprint", "category": "electronics", "subcategory": "Laptop",
            "manufacturer": "SYNTHETIC Maker", "product_name": name, "declared_unit": unit, "normalized_value": value,
            "normalized_unit": f"kg CO2e/{unit}", "original_value": value, "original_unit": f"kg CO2e/{unit}",
            "lifecycle_scope": "SYNTHETIC cradle to grave", "geography": "SYNTHETIC", "year": 2024, "source_id": SYN,
            "document_title": "SYNTHETIC dataset", "source_url": "https://example.invalid/data", "license": "SYNTHETIC license",
            "attribution": "SYNTHETIC", "verification_status": "manufacturer_reported_not_independently_crosschecked", "issues": [], **extra}


@pytest.fixture(scope="module")
def base(tmp_path_factory):
    """Real reference data plus three SYNTHETIC products. No approvals yet."""
    path = tmp_path_factory.mktemp("fp") / "base.sqlite"
    db = connect(path)
    refdata.load_all(db)
    for record in (product("SYNTHETIC Laptop 14 256GB"), product("SYNTHETIC Board", "5", "kg"),
                   product("SYNTHETIC Concrete", "300", "m3", lifecycle_module="A1-A3")):
        insert(db, record)
    db.commit()
    db.close()
    return path


@pytest.fixture(scope="module")
def approved(base, tmp_path_factory):
    path = tmp_path_factory.mktemp("fp") / "approved.sqlite"
    shutil.copy(base, path)
    db = connect(path)
    for dataset in (DESNZ, OWID, FOODS):
        approvals.approve(db, dataset, USE, "SYNTHETIC test approver", "SYNTHETIC approval for tests")
    db.execute("INSERT INTO reference_datasets(dataset_id,title) VALUES (?,?)", (SYN, "SYNTHETIC products")) if not db.execute(
        "SELECT 1 FROM reference_datasets WHERE dataset_id=?", (SYN,)).fetchone() else None
    approvals.approve(db, SYN, USE, "SYNTHETIC test approver", "SYNTHETIC approval for tests")
    db.commit()
    db.close()
    return path


@pytest.fixture()
def repo(approved):
    db = connect_read_only(approved)
    yield Repository(db)
    db.close()


def ask(repo, lines, country="GBR", year=2026, people=None, geo=False, other_year=False, skipped=()):
    return calculate(repo, {"household": {"country": country, "year": year, "people": people},
                            "proxies": {"other_geography": geo, "other_year": other_year}, "skipped": list(skipped), "lines": lines})


GAS = {"activity": "natural_gas", "quantity": 1000, "unit": "cubic metres", "period": "year"}
CAR = {"activity": "car", "quantity": 100, "unit": "km", "period": "week", "options": {"size": "Medium", "fuel": "Petrol"}}
POWER = {"activity": "electricity", "quantity": 250, "unit": "kWh", "period": "month"}


def product_id(repo, word):
    return repo.search_products(word)[0]["id"]


# ---------- approvals ----------
def test_nothing_is_approved_by_default_and_unapproved_data_is_not_used(base):
    db = connect_read_only(base)
    result = ask(Repository(db), [GAS])
    db.close()
    assert result["lines"][0]["status"] == "not_approved"
    assert "calculator-approve" in result["lines"][0]["message"]
    assert result["totals"]["covered_kg_co2e"] == 0


def test_approve_needs_a_known_dataset_a_person_and_a_note_and_revoke_keeps_history(base, tmp_path):
    path = tmp_path / "a.sqlite"
    shutil.copy(base, path)
    db = connect(path)
    with pytest.raises(ValueError):
        approvals.approve(db, "no-such-dataset", USE, "SYNTHETIC person", "note")
    with pytest.raises(ValueError):
        approvals.approve(db, DESNZ, USE, "", "note")
    with pytest.raises(ValueError):
        approvals.approve(db, DESNZ, USE, "SYNTHETIC person", "")
    approvals.approve(db, DESNZ, USE, "SYNTHETIC person", "SYNTHETIC note")
    assert set(approvals.active(db, USE)) == {DESNZ}
    approvals.revoke(db, DESNZ, USE, "SYNTHETIC person", "SYNTHETIC withdrawn")
    assert approvals.active(db, USE) == {}
    assert len(approvals.history(db)) == 1 and approvals.history(db)[0]["revoked_at"]
    db.close()


def test_cli_approval_commands(base, tmp_path, capsys):
    path = tmp_path / "c.sqlite"
    shutil.copy(base, path)
    assert main(["--db", str(path), "calculator-approve", OWID, "--approver", "SYNTHETIC person", "--note", "SYNTHETIC note"]) in (0, None)
    assert main(["--db", str(path), "calculator-approvals"]) in (0, None)
    assert OWID in capsys.readouterr().out
    assert main(["--db", str(path), "calculator-revoke", OWID, "--by", "SYNTHETIC person", "--note", "SYNTHETIC"]) in (0, None)
    db = connect(path)
    assert approvals.active(db, USE) == {}
    db.close()


# ---------- repository ----------
def test_the_calculator_connection_cannot_write(approved):
    db = connect_read_only(approved)
    with pytest.raises(sqlite3.OperationalError):
        db.execute("DELETE FROM activity_factors")
    with pytest.raises(sqlite3.OperationalError):
        db.execute("INSERT INTO calculation_approvals(dataset_id) VALUES ('x')")
    db.close()
    with pytest.raises(FileNotFoundError):
        connect_read_only(approved.parent / "missing.sqlite")


def test_great_circle_distance_between_two_airports(repo):
    a, b = repo.airport("KHI")[0], repo.airport("LHR")[0]
    assert 6300 < great_circle_km(a, b) < 6380
    assert great_circle_km(a, a) == 0


# ---------- calculation rules ----------
def test_exact_match_uses_the_published_value_and_turns_periods_into_a_year(repo):
    result = ask(repo, [GAS, CAR], people=2)
    gas, car = result["lines"]
    assert gas["status"] == car["status"] == "calculated"
    assert gas["proxy"] == {"geography": False, "year": False}
    row = repo.activity_factors(DESNZ, "Fuels", "Gaseous fuels · Natural gas", "kg CO2e per cubic metres", "Scope 1")[0]
    assert gas["factor"]["value"] == row["value_original"] and gas["factor"]["factor_id"] == row["activity_id"]
    assert Decimal(str(gas["kg_co2e"])) == round(Decimal(row["value_original"]) * 1000, 3)
    assert car["annual_quantity"] == 5200
    total = result["totals"]
    assert total["covered_kg_co2e"] == pytest.approx(gas["kg_co2e"] + car["kg_co2e"], abs=0.002)
    assert total["per_person_kg_co2e"] == pytest.approx(total["covered_kg_co2e"] / 2, abs=0.002)
    assert total["covered_t_co2e"] == pytest.approx(total["covered_kg_co2e"] / 1000, abs=0.0001)


def test_missing_factor(repo):
    line = ask(repo, [{**CAR, "options": {"size": "Small", "fuel": "LPG"}}])["lines"][0]
    assert line["status"] == "missing_factor" and line["kg_co2e"] is None


def test_unit_mismatch(repo):
    bus = {"activity": "bus", "quantity": 10, "unit": "km", "options": {"type": "Coach"}}
    board = {"activity": "product", "quantity": 1, "unit": "items", "record_id": product_id(repo, "board")}
    lines = ask(repo, [bus, board, {**GAS, "unit": "litres"}])["lines"]
    assert [l["status"] for l in lines] == ["unit_mismatch"] * 3
    assert "per kg" in lines[1]["message"]


def test_geography_mismatch_and_labelled_stand_in(repo):
    strict = ask(repo, [GAS], country="PAK")["lines"][0]
    assert strict["status"] == "geography_mismatch" and strict["kg_co2e"] is None
    assert strict["factor"]["geography"] == "United Kingdom"
    allowed = ask(repo, [GAS], country="PAK", geo=True)
    line = allowed["lines"][0]
    assert line["status"] == "calculated" and line["proxy"]["geography"] and "other_country_factor" in line["flags"]
    assert allowed["coverage"]["stand_ins"] == 1 and any("stand-in" in n for n in allowed["notices"])


def test_year_mismatch_and_labelled_stand_in(repo):
    strict = ask(repo, [GAS], year=2024)["lines"][0]
    assert strict["status"] == "year_mismatch" and "2026" in strict["message"]
    line = ask(repo, [GAS], year=2024, other_year=True)["lines"][0]
    assert line["status"] == "calculated" and line["proxy"] == {"geography": False, "year": True}


def test_country_electricity_matches_only_its_own_country_and_year(repo):
    row = repo.electricity("PAK")[0]
    good = ask(repo, [POWER], country="PAK", year=int(row["year"]))["lines"][0]
    assert good["status"] == "calculated" and good["proxy"] == {"geography": False, "year": False}
    assert Decimal(str(good["kg_co2e"])) == round(Decimal(row["value_metric"]) * 3000, 3)
    assert ask(repo, [POWER], country="PAK", year=int(row["year"]) - 1)["lines"][0]["status"] == "year_mismatch"
    assert ask(repo, [POWER], country="ZZZ")["lines"][0]["status"] == "missing_factor"


def test_duplicate_factor_is_reported_and_not_used(approved, tmp_path):
    path = tmp_path / "dup.sqlite"
    shutil.copy(approved, path)
    db = sqlite3.connect(path)
    names = [r[1] for r in db.execute("PRAGMA table_info(activity_factors)") if r[1] != "id"]
    row = db.execute(f"SELECT {','.join(names)} FROM activity_factors WHERE dataset_id=? AND name_en=? AND unit_original=? AND note=?",
                     (DESNZ, "Gaseous fuels · Natural gas", "kg CO2e per cubic metres", "Scope 1")).fetchone()
    copy = dict(zip(names, row), activity_id="SYNTHETIC-duplicate", value_original="999")
    db.execute(f"INSERT INTO activity_factors({','.join(names)}) VALUES ({','.join('?' * len(names))})", [copy[n] for n in names])
    db.commit()
    db.close()
    ro = connect_read_only(path)
    line = ask(Repository(ro), [GAS])["lines"][0]
    ro.close()
    assert line["status"] == "duplicate_factor" and line["kg_co2e"] is None and "SYNTHETIC-duplicate" in line["message"]


def test_boundary_mismatch_for_a_production_stage_only_record(repo):
    line = ask(repo, [{"activity": "product", "quantity": 2, "unit": "m3", "record_id": product_id(repo, "concrete")}])["lines"][0]
    assert line["status"] == "boundary_mismatch" and "A1-A3" in line["message"]


def test_products_match_the_exact_record_and_say_they_are_not_independently_verified(repo):
    rid = product_id(repo, "laptop 14 256gb")
    line = ask(repo, [{"activity": "product", "quantity": 2, "unit": "items", "record_id": rid}])["lines"][0]
    assert line["status"] == "calculated" and line["kg_co2e"] == 200
    assert line["factor"]["record_id"] == rid and line["factor"]["manufacturer"] == "SYNTHETIC Maker"
    assert line["factor"]["approval"]["level"] == "approved_for_estimation"
    assert "not independently verified" in line["factor"]["approval"]["text"]
    assert ask(repo, [{"activity": "product", "quantity": 1, "unit": "items", "record_id": 10 ** 9}])["lines"][0]["status"] == "missing_factor"


def test_invalid_input(repo):
    bad = [{"activity": "teleport", "quantity": 1, "unit": "km"}, {**GAS, "quantity": -1}, {**GAS, "quantity": "abc"},
           {**GAS, "period": "decade"}, {**CAR, "options": {"size": "Huge", "fuel": "Petrol"}},
           {"activity": "flight", "unit": "passenger-km", "from_airport": "KHI", "to_airport": "???",
            "options": {"haul": "Long-haul, to/from UK", "cabin": "Economy class", "rf": "With RF"}}]
    assert [l["status"] for l in ask(repo, bad)["lines"]] == ["invalid_input"] * len(bad)


def test_flight_by_airports_uses_great_circle_distance(repo):
    item = {"activity": "flight", "unit": "passenger-km", "from_airport": "KHI", "to_airport": "LHR", "trips": 1, "return_trip": True,
            "options": {"haul": "Long-haul, to/from UK", "cabin": "Economy class", "rf": "With RF"}}
    line = ask(repo, [item])["lines"][0]
    assert line["status"] == "calculated" and line["distance"]["legs_per_trip"] == 2
    assert line["annual_quantity"] == pytest.approx(2 * line["distance"]["great_circle_km"], abs=0.01)


def test_partial_result_is_never_shown_as_complete(repo):
    result = ask(repo, [GAS, {**CAR, "options": {"size": "Small", "fuel": "LPG"}}], skipped=["food"])
    status = {c["category"]: c["status"] for c in result["categories"]}
    assert status == {"home": "calculated", "transport": "not_calculated", "food": "skipped", "products": "not_answered"}
    assert result["totals"]["covered_kg_co2e"] == result["lines"][0]["kg_co2e"]
    cover = result["coverage"]
    assert cover["is_complete_footprint"] is False and cover["all_entries_calculated"] is False and cover["not_calculated"] == 1
    assert any("could not be calculated" in n for n in result["notices"]) and any("Skipped" in n for n in result["notices"])
    mixed = ask(repo, [GAS, {**GAS, "unit": "litres"}])
    assert mixed["categories"][0]["status"] == "partial"
    full = ask(repo, [GAS], skipped=["transport", "food", "products"])
    assert full["coverage"]["all_entries_calculated"] is True and full["coverage"]["is_complete_footprint"] is False
    assert ask(repo, [])["coverage"]["is_complete_footprint"] is False


def test_recommendations_come_from_published_rows_only(repo):
    tips = ask(repo, [CAR, POWER])["recommendations"]
    assert tips and all(t["saving_kg_co2e"] > 0 for t in tips)
    assert not any("Electric" in t["title"] for t in tips)


def test_every_calculated_line_carries_its_evidence(repo):
    result = ask(repo, [GAS, CAR])
    for line in result["lines"]:
        f = line["factor"]
        assert all(f.get(k) for k in ("dataset_id", "factor_id", "value", "unit", "year", "geography", "boundary", "license", "source_url", "approval"))
    assert {e["dataset_id"] for e in result["evidence"]} == {DESNZ}


def test_catalog_selectors_point_at_rows_that_exist(repo):
    for key in ("natural_gas", "lpg"):
        sel = catalog.ACTIVITIES[key]["selector"]
        for unit in sel["units"].values():
            assert len(repo.activity_factors(DESNZ, sel["area"], sel["name"], f"kg CO2e per {unit.split('>')[0]}", sel["scope"])) == 1


# ---------- reports ----------
def test_reports_keep_the_partial_warning_and_escape_spreadsheet_formulas(repo):
    result = ask(repo, [GAS, {**GAS, "unit": "litres", "id": "=cmd()"}])
    html, csv_text, data = report.to_html(result), report.to_csv(result), json.loads(report.to_json(result))
    assert "Not a complete" in html and "<script" not in html.lower()
    assert "\n=cmd()" not in csv_text and "unit_mismatch" in csv_text
    assert data["coverage"]["is_complete_footprint"] is False


# ---------- API ----------
@pytest.fixture()
def client(approved):
    from fastapi.testclient import TestClient

    from gcc_cos.web.app import create_app
    return TestClient(create_app(approved))


BODY = {"household": {"country": "GBR", "year": 2026, "people": 2}, "lines": [GAS]}


def test_api_health_catalog_and_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and DESNZ in r.json()["approved_datasets"]
    assert "default-src 'self'" in r.headers["content-security-policy"] and r.headers["x-content-type-options"] == "nosniff"
    cat = client.get("/api/v1/catalog").json()
    assert "selector" not in json.dumps(cat)
    assert client.get("/").status_code == 200 and client.get("/static/app.js").status_code == 200


def test_api_calculate_matches_the_engine(client, repo):
    r = client.post("/api/v1/calculate", json=BODY)
    assert r.status_code == 200
    assert r.json()["totals"] == ask(repo, [GAS], people=2)["totals"]


@pytest.mark.parametrize("body", [
    {"household": {"country": "gbr", "year": 2026}, "lines": []},
    {"household": {"country": "GBR", "year": 1800}, "lines": []},
    {"household": {"country": "GBR", "year": 2026, "people": 0}, "lines": []},
    {"household": {"country": "GBR", "year": 2026}, "lines": [], "surprise": 1},
    {"lines": []},
])
def test_api_rejects_bad_requests_with_a_readable_message(client, body):
    r = client.post("/api/v1/calculate", json=body)
    assert r.status_code == 422 and r.json()["error"]


def test_api_search_and_status(client):
    assert any("rice" in f["name_en"].lower() for f in client.get("/api/v1/foods", params={"q": "rice"}).json()["foods"])
    assert client.get("/api/v1/products", params={"q": "synthetic laptop"}).json()["products"][0]["manufacturer"] == "SYNTHETIC Maker"
    assert client.get("/api/v1/airports", params={"q": "KHI"}).json()["airports"][0]["iata_code"] == "KHI"
    assert client.get("/api/v1/data-status", params={"country": "PAK", "year": 2025}).status_code == 200
    assert client.get("/api/v1/data-status", params={"country": "pk", "year": 2025}).status_code == 422
    assert any(c["iso3"] == "PAK" for c in client.get("/api/v1/countries").json()["countries"])


def test_api_reports(client):
    for fmt, kind in (("csv", "text/csv"), ("json", "application/json"), ("html", "text/html")):
        r = client.post(f"/api/v1/reports/{fmt}", json=BODY)
        assert r.status_code == 200 and kind in r.headers["content-type"] and "attachment" in r.headers["content-disposition"]
    assert client.post("/api/v1/reports/pdf", json=BODY).status_code == 422


def test_api_has_no_write_routes_and_reports_a_missing_database(client, tmp_path):
    from fastapi.testclient import TestClient

    from gcc_cos.web.app import create_app
    for path in ("/api/v1/health", "/api/v1/catalog", "/api/v1/foods"):
        assert client.delete(path).status_code == 405 and client.put(path).status_code == 405
    missing = TestClient(create_app(tmp_path / "none.sqlite"))
    assert missing.post("/api/v1/calculate", json=BODY).status_code == 503
    assert not (tmp_path / "none.sqlite").exists()
