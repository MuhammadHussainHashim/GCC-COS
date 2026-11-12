"""Reference tables, loaders, commands and exports. Bundled datasets are real; rows written in tests are SYNTHETIC."""
import csv
import hashlib
import json
import sqlite3
from decimal import Decimal

import pandas as pd
import pytest

from gcc_cos import refdata
from gcc_cos.cli import main
from gcc_cos.export import export
from gcc_cos.storage import connect, records

EXPECTED = {"reference_values": 570, "activity_factors": 63 + 2622, "country_data": 1184, "hs_codes": 6939, "product_averages": 2451, "spend_factors": 1016,
            "hs_industry_links": 6322, "benchmarks": 25, "airports": 3245}


@pytest.fixture(scope="module")
def loaded(tmp_path_factory):
    path = tmp_path_factory.mktemp("ref") / "ref.sqlite"
    db = connect(path)
    first = refdata.load_all(db)
    second = refdata.load_all(db)
    yield db, first, second, path
    db.close()


def one(db, sql, *args):
    cursor = db.execute(sql, args)
    names = [d[0] for d in cursor.description]
    return dict(zip(names, cursor.fetchone()))


def test_every_table_loads_once_and_reloading_adds_nothing(loaded):
    db, first, second, _ = loaded
    assert refdata.counts(db) == EXPECTED
    inserted = {}
    for r in first:
        inserted[r["table"]] = inserted.get(r["table"], 0) + r["inserted"]
    assert inserted == EXPECTED
    assert all(r["inserted"] == 0 and r["already_present"] == r["rows_in_file"] for r in second)
    assert records(db) == []                                  # product records are a separate table and untouched


def test_every_bundled_dataset_matches_its_checksum_and_names_source_and_licence():
    folders = sorted(p for p in refdata.DATASETS.iterdir() if p.is_dir())
    assert {p.name for p in folders} == {name for names in refdata.BUNDLED.values() for name in names}
    for folder in folders:
        source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
        assert hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest() == source["sha256"]
        for field in ("title", "publisher", "url", "license", "license_url", "attribution", "verification_status"):
            assert source[field].strip()


@pytest.mark.parametrize("table", ["reference_values", "activity_factors", "country_data", "benchmarks"])
def test_every_value_row_has_unit_year_place_licence_and_source(loaded, table):
    db = loaded[0]
    place = "iso3" if table == "country_data" else "geography"
    for row in refdata.rows(db, table):
        for column in ("value_original", "unit_original", "value_kind", "year", place, "license", "source_url", "source_title", "verification_status"):
            assert str(row[column] or "").strip(), (table, row["id"], column)
        Decimal(row["value_original"])


def test_kinds_of_numbers_are_labelled_and_kept_apart(loaded):
    db = loaded[0]
    kinds = {table: {r[0] for r in db.execute(f"SELECT DISTINCT value_kind FROM {table}")} for table in ("reference_values", "activity_factors", "country_data", "benchmarks")}
    assert kinds == {"reference_values": {"regulatory default value"}, "activity_factors": {"activity emission factor"},
                     "country_data": {"per-person country average", "country electricity factor"}, "benchmarks": {"published benchmark or assumption"}}


def test_cbam_values_keep_original_and_metric_and_are_marked_checked(loaded):
    db = loaded[0]
    cement = one(db, "SELECT * FROM reference_values WHERE code='25232900'")
    assert (cement["value_original"], cement["unit_original"], cement["value_metric"], cement["unit_metric"]) == ("1.375", "t CO2e per tonne of product", "1.375", "kg CO2e per kg of product")
    assert (cement["hs6"], cement["hs4"], cement["geography"], cement["year"], cement["verification_status"]) == ("252329", "2523", "United Kingdom (imports)", "2026", "checked against the publisher's pages")
    assert "Open Government Licence" in cement["license"]
    flagged = one(db, "SELECT * FROM reference_values WHERE code='73065029'")
    assert flagged["value_original"] == "2.811" and flagged["description"].startswith("Precision steel tubes, welded")
    assert db.execute("SELECT count(*) FROM reference_values WHERE substr(code,1,6)<>hs6 OR verification_status='unverified'").fetchone()[0] == 0
    source = json.loads((refdata.DATASETS / "uk-cbam-defaults/SOURCE.json").read_text(encoding="utf-8"))
    assert source["corrections_to_workbook"] == [] and len(source["page_sha256"]) == 5
    assert db.execute("SELECT count(DISTINCT hs6) FROM reference_values").fetchone()[0] == 283
    assert db.execute("SELECT count(*) FROM reference_values r WHERE NOT EXISTS (SELECT 1 FROM hs_codes h WHERE h.code=r.hs6)").fetchone()[0] == 0


def test_activity_factors_are_french_keep_the_french_name_and_equal_the_publisher_file(loaded):
    db = loaded[0]
    upstream = json.loads((refdata.ROOT / "examples/phase5/ademe-upstream/values.json").read_text(encoding="utf-8"))
    rows = [r for r in refdata.rows(db, "activity_factors") if r["dataset_id"] == "ademe-activity-factors"]
    assert len(rows) == 63 and {r["geography"] for r in rows} == {"France"} and {r["language_original"] for r in rows} == {"fr"}
    assert {r["area"]: 0 for r in rows}.keys() == {"Transport", "Home heating", "Digital use"}
    for row in rows:
        grams = Decimal(str(upstream[row["activity_id"]]["value"]))
        assert Decimal(row["value_original"]) == grams and Decimal(row["value_metric"]) == grams / 1000 and row["name_original"]
    coach = one(db, "SELECT * FROM activity_factors WHERE activity_id='autocar'")
    assert (coach["name_en"], coach["name_original"], coach["unit_original"], coach["unit_metric"]) == ("Coach (combustion)", "Autocar thermique", "g CO2e per km", "kg CO2e per km")
    assert one(db, "SELECT * FROM activity_factors WHERE activity_id='streamingvideo'")["unit_metric"] == "kg CO2e per hour of video streaming"


def test_country_data_for_pakistan(loaded):
    db = loaded[0]
    rows = {r["indicator"]: r for r in refdata.rows(db, "country_data") if r["iso3"] == "PAK"}
    assert set(rows) == {"co2_per_person", "consumption_co2_per_person", "ghg_per_person", "electricity_carbon_intensity",
                         "electricity_demand_per_person", "electricity_generation_per_person"}
    grid = rows["electricity_carbon_intensity"]
    assert (grid["value_original"], grid["unit_original"], grid["value_metric"], grid["unit_metric"], grid["year"]) == ("346.56", "g CO2e per kWh", "0.34656", "kg CO2e per kWh", "2025")
    assert "Ember" in grid["original_source"] and "CC BY 4.0" in grid["license"]
    assert (rows["co2_per_person"]["value_original"], rows["co2_per_person"]["year"]) == ("0.83", "2025")
    assert db.execute("SELECT count(DISTINCT iso3) FROM country_data").fetchone()[0] >= 218


def test_hs_codes_links_benchmarks_and_airports(loaded):
    db = loaded[0]
    assert one(db, "SELECT * FROM hs_codes WHERE code='851713'")["description"] == "Telephone sets; smartphones for cellular or other wireless networks"
    assert db.execute("SELECT count(*) FROM hs_codes WHERE level='6'").fetchone()[0] == 5613
    link = one(db, "SELECT * FROM hs_industry_links WHERE hs6='010121'")
    assert (link["industry_code"], link["import_lines"], link["share_of_lines"], link["year"], link["geography"]) == ("112920", "2", "1", "2017", "United States")
    gas = one(db, "SELECT * FROM benchmarks WHERE item='Natural gas carbon coefficient'")
    assert (gas["value_original"], gas["unit_original"], gas["unit_metric"], gas["year"], gas["verification_status"]) == ("117", "lb CO2 per MMBtu", "kg CO2 per GJ", "2024", "checked against the publisher's pages")
    assert abs(Decimal(gas["value_metric"]) - Decimal(gas["value_original"]) * Decimal(gas["factor_to_metric"])) < Decimal("0.000001")
    assert {r[0] for r in db.execute("SELECT DISTINCT publisher FROM benchmarks")} == {"US EPA Household Carbon Footprint Calculator"}
    karachi = one(db, "SELECT * FROM airports WHERE iata_code='KHI'")
    assert karachi["iso_country"] == "PK" and 24 < float(karachi["latitude_deg"]) < 26 and "Public domain" in karachi["license"]


def test_register_lists_every_dataset_with_its_verification_state(loaded):
    register = {r["dataset_id"]: r for r in refdata.rows(loaded[0], "reference_datasets")}
    assert len(register) == 10 and all(int(r["rows_loaded"]) == int(r["rows_in_file"]) for r in register.values())
    assert register["uk-cbam-defaults"]["verification_status"] == "checked against the publisher's pages" and "73065029" in register["uk-cbam-defaults"]["verification_note"]
    assert register["owid-country-data"]["verification_status"] == "checked against the publisher's file"


def dataset(folder, table="benchmarks", rows=None, **changes):
    folder.mkdir(parents=True, exist_ok=True)
    rows = rows if rows is not None else [{"publisher": "SYNTHETIC", "item": "SYNTHETIC item", "value_original": "1", "unit_original": "kg", "value_kind": "published benchmark or assumption",
                                           "geography": "Nowhere", "year": "2020"}]
    with open(folder / "data.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    source = {"id": "synthetic", "table": table, "title": "SYNTHETIC", "publisher": "SYNTHETIC", "url": "https://example.invalid", "license": "SYNTHETIC licence",
              "license_url": "https://example.invalid/licence", "attribution": "SYNTHETIC", "verification_status": "unverified", "file": "data.csv",
              "sha256": hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest(), **changes}
    (folder / "SOURCE.json").write_text(json.dumps({k: v for k, v in source.items() if v is not None}), encoding="utf-8")
    return folder


def test_a_good_custom_dataset_loads(tmp_path):
    db = connect(tmp_path / "c.sqlite")
    try:
        assert refdata.load_dataset(db, dataset(tmp_path / "d"))["inserted"] == 1
        assert refdata.rows(db, "benchmarks")[0]["license"] == "SYNTHETIC licence"
    finally:
        db.close()


BASE = {"publisher": "SYNTHETIC", "item": "x", "value_original": "1", "unit_original": "kg", "value_kind": "k", "geography": "Nowhere", "year": "2020"}


@pytest.mark.parametrize("kwargs, message", [
    ({"license": None}, "must state license"),
    ({"url": " "}, "must state url"),
    ({"sha256": "0" * 64}, "checksum"),
    ({"table": "records"}, "Unknown table"),
    ({"table": "hs_codes"}, "Unknown table"),
    ({"rows": [{**BASE, "unit_original": ""}]}, "has no unit_original"),
    ({"rows": [{**BASE, "year": ""}]}, "has no year"),
    ({"rows": [{**BASE, "geography": ""}]}, "has no geography"),
    ({"rows": [{**BASE, "year": "20x0"}]}, "year must be four digits"),
    ({"rows": [{**BASE, "invented_column": "1"}]}, "Unknown columns"),
])
def test_incomplete_or_altered_datasets_are_refused_whole(tmp_path, kwargs, message):
    db = connect(tmp_path / "bad.sqlite")
    try:
        with pytest.raises(ValueError, match=message):
            refdata.load_dataset(db, dataset(tmp_path / "d", **kwargs))
        assert refdata.counts(db)["benchmarks"] == 0
    finally:
        db.close()


def test_bad_hs_code_and_wrong_table_are_refused(tmp_path):
    db = connect(tmp_path / "bad.sqlite")
    try:
        row = {"scheme": "S", "code": "12345678", "hs6": "12345", "value_original": "1", "unit_original": "u", "value_kind": "k", "geography": "g", "year": "2020"}
        with pytest.raises(ValueError, match="hs6 must be 6 digits"):
            refdata.load_dataset(db, dataset(tmp_path / "d", table="reference_values", rows=[row]))
        with pytest.raises(ValueError, match="belongs to the benchmarks table"):
            refdata.load_dataset(db, dataset(tmp_path / "e"), "airports")
        with pytest.raises(ValueError, match="No SOURCE.json"):
            refdata.load_dataset(db, tmp_path / "missing")
    finally:
        db.close()


COMMANDS = [("load-reference-values", "reference_values"), ("load-activity-factors", "activity_factors"), ("load-country-data", "country_data"),
            ("load-hs-codes", "hs_codes"), ("load-hs-industry-links", "hs_industry_links"), ("load-benchmarks", "benchmarks"), ("load-product-averages", "product_averages"), ("load-spend-factors", "spend_factors"), ("load-airports", "airports")]


@pytest.mark.parametrize("command, table", COMMANDS)
def test_each_load_command(tmp_path, capsys, command, table):
    path = str(tmp_path / "cli.sqlite")
    assert main(["--db", path, command]) == 0
    results = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert {r["table"] for r in results} == {table} and sum(r["inserted"] for r in results) == EXPECTED[table]
    assert main(["--db", path, "reference-tables"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown[table] == EXPECTED[table] and sum(shown.values()) == EXPECTED[table]


def test_load_all_command_dataset_option_and_errors(tmp_path, capsys):
    path = str(tmp_path / "cli.sqlite")
    assert main(["--db", path, "load-reference-data"]) == 0
    assert len(capsys.readouterr().out.strip().splitlines()) == 10
    assert main(["--db", path, "load-benchmarks", "--dataset", str(dataset(tmp_path / "d"))]) == 0
    assert json.loads(capsys.readouterr().out)["inserted"] == 1
    with pytest.raises(SystemExit):
        main(["--db", path, "load-airports", "--dataset", str(tmp_path / "d")])
    with pytest.raises(SystemExit):
        main(["--db", path, "load-hs-codes", "--dataset", "x"])


def test_excel_and_sqlite_exports_carry_every_reference_table(loaded, tmp_path):
    db = loaded[0]
    export(db, tmp_path / "all.xlsx")
    sheets = pd.read_excel(tmp_path / "all.xlsx", sheet_name=None, dtype=str)
    for table, (_, _, _, sheet) in refdata.TABLES.items():
        assert len(sheets[sheet]) == EXPECTED[table], sheet
    assert len(sheets["Reference datasets"]) == 10 and "Records" in sheets and "License notices" in sheets
    assert sheets["Reference values by code"].loc[sheets["Reference values by code"]["code"] == "25232900", "hs6"].item() == "252329"
    export(db, tmp_path / "all.sqlite")
    with sqlite3.connect(tmp_path / "all.sqlite") as copy:
        for table, expected in EXPECTED.items():
            assert copy.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == expected
        assert copy.execute("SELECT count(*) FROM reference_datasets").fetchone()[0] == 10


def test_export_without_reference_data_has_no_extra_sheets(tmp_path):
    db = connect(tmp_path / "empty.sqlite")
    try:
        export(db, tmp_path / "empty.xlsx")
        assert not set(pd.ExcelFile(tmp_path / "empty.xlsx").sheet_names) & ({t[3] for t in refdata.TABLES.values()} | {"Reference datasets"})
    finally:
        db.close()


def test_dashboard_shows_reference_tab(loaded, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import gcc_cos.storage
    original = gcc_cos.storage.connect
    monkeypatch.setattr(gcc_cos.storage, "connect", lambda _: original(loaded[3]))
    monkeypatch.chdir(refdata.ROOT)
    app = AppTest.from_file(str(refdata.ROOT / "dashboard.py")).run(timeout=90)
    assert not app.exception
    assert any(s.value == "Reference data" for s in app.subheader)


def test_a_changed_dataset_file_replaces_its_older_rows(tmp_path):
    db = connect(tmp_path / "replace.sqlite")
    try:
        first = dict(BASE, item="old item")
        assert refdata.load_dataset(db, dataset(tmp_path / "d", rows=[first]))["replaced_older_version"] is False
        assert refdata.load_dataset(db, dataset(tmp_path / "d", rows=[first]))["inserted"] == 0
        result = refdata.load_dataset(db, dataset(tmp_path / "d", rows=[dict(BASE, item="new item"), dict(BASE, item="second new item")]))
        assert result["replaced_older_version"] is True and result["inserted"] == 2
        assert [r["item"] for r in refdata.rows(db, "benchmarks")] == ["new item", "second new item"]
        assert refdata.rows(db, "reference_datasets")[0]["rows_loaded"] == "2"
    finally:
        db.close()


def test_spend_factors_are_per_dollar_us_and_copied_from_the_epa_file(loaded):
    db = loaded[0]
    soy = one(db, "SELECT * FROM spend_factors WHERE industry_code='111110'")
    assert (soy["industry_title"], soy["value_original"], soy["value_without_margins"], soy["value_of_margins"]) == ("Soybean Farming", "0.532", "0.488", "0.044")
    assert (soy["unit_original"], soy["value_kind"], soy["geography"], soy["year"]) == ("kg CO2e/2022 USD, purchaser price", "spend-based factor (per US dollar)", "United States", "2022")
    assert "public domain" in soy["license"] and soy["verification_status"] == "copied from the publisher's file"
    for row in refdata.rows(db, "spend_factors"):
        assert abs(Decimal(row["value_without_margins"]) + Decimal(row["value_of_margins"]) - Decimal(row["value_original"])) <= Decimal("0.0011"), row["industry_code"]
    linked = db.execute("SELECT count(DISTINCT l.hs6) FROM hs_industry_links l JOIN spend_factors s ON s.industry_code=l.industry_code").fetchone()[0]
    assert linked > 4000          # most HS codes reach a factor through the industry link; codes ending in X do not


def test_uk_conversion_factors_keep_original_units_and_scope(loaded):
    db = loaded[0]
    assert db.execute("SELECT count(*) FROM activity_factors WHERE dataset_id='uk-desnz-conversion-factors-2026'").fetchone()[0] == 2622
    flight = one(db, "SELECT * FROM activity_factors WHERE activity_id='desnz2026:21_316_3160_11_1'")
    assert (flight["area"], flight["value_original"], flight["unit_original"], flight["geography"], flight["year"], flight["note"]) == \
        ("Business travel- air", "0.22928", "kg CO2e per passenger.km", "United Kingdom", "2026", "Scope 3")
    assert flight["name_en"].endswith("With RF") and "Open Government Licence" in flight["license"]
    butane = one(db, "SELECT * FROM activity_factors WHERE activity_id='desnz2026:1_100_1000_15_1'")
    assert (butane["value_original"], butane["unit_original"], butane["value_metric"], butane["unit_metric"]) == ("3033.38067", "kg CO2e per tonnes", "3.03338067", "kg CO2e per kg")
    miles = one(db, "SELECT * FROM activity_factors WHERE dataset_id='uk-desnz-conversion-factors-2026' AND unit_original='kg CO2e per miles' LIMIT 1")
    assert miles["unit_metric"] == "kg CO2e per km" and abs(Decimal(miles["value_metric"]) * Decimal("1.609344") - Decimal(miles["value_original"])) < Decimal("0.000001")
    assert {r[0] for r in db.execute("SELECT DISTINCT geography FROM activity_factors")} == {"France", "United Kingdom"}


def test_agribalyse_foods_keep_french_name_parts_and_quality_rating(loaded):
    db = loaded[0]
    stock = one(db, "SELECT * FROM product_averages WHERE product_code='11172'")
    assert (stock["name_en"], stock["name_original"], stock["value_original"], stock["unit_metric"]) == \
        ("Aromatic stock cube, for fish, dehydrated", "Court-bouillon pour poissons, déshydraté", "7.58", "kg CO2e per kg of product")
    assert (stock["fossil_part"], stock["biogenic_part"], stock["land_use_change_part"], stock["data_quality_rating"]) == ("7.46", "0.104", "0.0212", "2.24")
    assert (stock["geography"], stock["year"], stock["value_kind"], stock["language_original"]) == ("France", "2025", "product average footprint (per kg)", "fr")
    assert "Licence Ouverte" in stock["license"]
    assert db.execute("SELECT count(*) FROM product_averages WHERE name_en IS NULL OR name_original IS NULL OR value_original IS NULL").fetchone()[0] == 0
