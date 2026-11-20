"""IPCC EFDB import (20 November 2026). The bundled dataset is real; nothing here is synthetic."""
import csv
import json
from pathlib import Path

import pytest

from gcc_cos import refdata
from gcc_cos.storage import connect

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "datasets/ipcc-efdb-2026-11"
CONTENT = ["ipcc_1996_category", "ipcc_2006_category", "gas", "fuel_1996", "fuel_2006", "carbon_pool", "parameter_type", "description",
           "technologies", "conditions", "region", "abatement", "other_properties", "value_original", "unit_original", "value_numeric",
           "equation", "ipcc_worksheet", "technical_reference", "source_of_data", "data_provider"]


@pytest.fixture(scope="module")
def rows():
    with open(FOLDER / "data.csv", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    database = connect(tmp_path_factory.mktemp("efdb") / "efdb.sqlite")
    refdata.load_table_datasets(database, "inventory_factors")
    yield database
    database.close()


def test_no_record_is_repeated_and_every_record_has_a_value(rows):
    assert len(rows) == 26494
    assert len({r["ef_id"] for r in rows}) == len(rows)
    assert len({tuple(r[c] for c in CONTENT) for r in rows}) == len(rows)
    folded = [i for r in rows for i in r["also_listed_as"].split()]
    assert len(folded) == 778 and not set(folded) & {r["ef_id"] for r in rows}
    assert all(r["value_original"].strip() for r in rows)


def test_values_and_units_are_kept_as_exported_and_labelled(rows):
    first = next(r for r in rows if r["ef_id"] == "62639")
    assert (first["value_original"], first["unit_original"], first["gas"], first["region"]) == ("2.0", "kg/cap/day", "METHANE", "United States of America")
    assert {r["value_kind"] for r in rows} == {"IPCC EFDB inventory parameter (per gas, not CO2e; not a product footprint)"}
    assert {r["sector_2006"] for r in rows} <= {"Energy", "Industrial processes and product use", "Agriculture, forestry and other land use",
                                                 "Waste", "Other", "Not stated"}


def test_loads_once_and_names_source_licence_and_check(db):
    assert refdata.counts(db)["inventory_factors"] == 26494
    again = refdata.load_table_datasets(db, "inventory_factors")[0]
    assert again["inserted"] == 0 and again["already_present"] == 26494
    register = {r["dataset_id"]: r for r in refdata.rows(db, "reference_datasets")}["ipcc-efdb-2026-11"]
    assert "EFDB" in register["title"] and "No licence is stated" in register["license"]
    assert "not product footprints" in register["verification_note"]


def test_spot_check_against_the_efdb_website_is_recorded():
    report = json.loads((ROOT / "docs/data-verification/2026-11-20/efdb-import-summary.json").read_text(encoding="utf-8"))
    assert (report["records_in_upload"], report["records_loaded"], report["repeats_folded"], report["left_out_no_value"]) == (27566, 26494, 778, 294)
    check = report["spot_check"]
    reached = [r for r in check["records"] if r["status"] != "not reached"]
    assert check["records_checked"] == 300 and len(reached) >= 295
    assert all(r["fields_equal"]["value_and_unit"] for r in reached)                 # every sampled value and unit equals the website
    assert check["equal"] >= 0.95 * len(reached)


def test_text_lost_in_the_export_was_restored_only_where_the_site_matches(rows):
    report = json.loads((ROOT / "docs/data-verification/2026-11-20/efdb-import-summary.json").read_text(encoding="utf-8"))
    fixed = [r for r in rows if r["fixed_from_efdb_site"]]
    assert len(fixed) == report["records_repaired"] > 3000
    allowed = {"description", "technologies", "conditions", "region", "abatement", "other_properties", "ipcc_1996_category",
               "ipcc_2006_category", "equation", "ipcc_worksheet", "technical_reference", "source_of_data", "value_original", "unit_original"}
    assert {f for r in fixed for f in r["fixed_from_efdb_site"].split()} <= allowed
    assert sum(not r["description"] for r in rows) == report["still_blank_description"] < 100
    rice = next(r for r in rows if r["ef_id"] == "424287")                             # "N?O" in the export
    assert rice["unit_original"] == "kg N₂O-N/ha" and "unit_original" in rice["fixed_from_efdb_site"]
