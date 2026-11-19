"""Phase 6 import (19 November 2026): new CarbonPDF products, Poore & Nemecek foods, IPCC electricity
technologies and suggested HS-to-factor links. Bundled data is real; nothing here is synthetic."""
import csv
import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from gcc_cos import refdata
from gcc_cos.ingest import ingest, load_registry
from gcc_cos.storage import connect, records

ROOT = Path(__file__).resolve().parents[1]
PHASE6 = ROOT / "examples/phase6"


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def key(maker, name):
    maker, name = norm(maker), norm(name)
    return maker, name[len(maker) + 1:] if name.startswith(maker + " ") else name


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    folder = tmp_path_factory.mktemp("phase6")
    database = connect(folder / "p6.sqlite")
    for phase in ("phase2", "phase6"):
        manifest = json.loads((ROOT / f"examples/{phase}/local-files.json").read_text(encoding="utf-8"))
        for source in load_registry(ROOT / f"examples/{phase}/sources.json"):
            if source["id"] in manifest:
                ingest(database, source, folder / "raw", ROOT / manifest[source["id"]])
    refdata.load_all(database)
    yield database
    database.close()


def test_new_products_are_not_already_held_and_not_repeated():
    held = rows(ROOT / "examples/phase2/boavizta-products.csv")
    held_keys = {key(r["manufacturer"], r["name"]) for r in held}
    held_urls = {u.strip() for r in held for u in r["sources"].split(";")}
    new = rows(PHASE6 / "carbonpdf-new-products.csv")
    assert len(new) == 1212
    assert not [r for r in new if key(r["Company name"], r["Product name"]) in held_keys or r["File URL"].strip() in held_urls]
    exact = [(key(r["Company name"], r["Product name"]), r["File URL"], Decimal(r["Product carbon footprint (PCF, kg CO2e)"])) for r in new]
    assert len(set(exact)) == len(exact)


def test_products_load_once_with_their_report_and_licence(db):
    phase6 = [r for r in records(db) if r["source_id"] == "carbonpdf-products"]
    assert len(phase6) == 1212
    source = load_registry(PHASE6 / "sources.json")[0]
    again = ingest(db, source, Path(db.execute("PRAGMA database_list").fetchone()[2]).parent / "raw", PHASE6 / "carbonpdf-new-products.csv")
    assert (again["inserted"], again["duplicates"]) == (0, 1212)
    sample = next(r for r in phase6 if r["product_name"] == "EliteBook 855 G7" or r["primary_source_url"].endswith("c07525117"))
    assert sample["license"] == "CC BY 4.0" and sample["original_unit"] == "kg CO2e/item" and sample["manufacturer"] == "HP"
    assert all(r["primary_source_url"].startswith("http") and r["data_kind"] == "published_product_footprint" for r in phase6)
    assert all(r["year"] is None and r["geography"] is None for r in phase6)            # the dataset gives neither; nothing invented
    assert all(r["hs_evidence"] for r in phase6 if r["hs6"])                              # HS only from the project's own rules, with evidence


def test_food_values_equal_the_owid_file_and_are_world_2010(db):
    food = {r["name_en"]: r for r in refdata.rows(db, "product_averages") if r["dataset_id"] == "poore-nemecek-2018-food"}
    assert len(food) == 38
    assert (food["Beef (beef herd)"]["value_metric"], food["Lamb & Mutton"]["value_metric"], food["Cheese"]["value_metric"]) == ("99.48", "39.72", "23.88")
    assert {(r["geography"], r["year"], r["unit_metric"]) for r in food.values()} == {("World", "2010", "kg CO2e per kg")}
    assert not {"Olive Oil", "Palm Oil", "Rapeseed Oil", "Sunflower Oil", "Grains"} & set(food)     # no per-kg value upstream


def test_electricity_technologies_keep_grams_and_say_which_were_checked(db):
    tech = {r["activity_id"]: r for r in refdata.rows(db, "activity_factors") if r["dataset_id"] == "ipcc-ar5-electricity-technologies"}
    assert len(tech) == 15
    coal = tech["ipcc-ar5:coal-pulverised-coal:lifecycle"]
    assert (coal["value_original"], coal["unit_original"], coal["value_metric"], coal["unit_metric"]) == ("820", "g CO2e per kWh", "0.82", "kg CO2e per kWh")
    assert sum("equals the Electricity Maps" in r["note"] for r in tech.values()) == 8
    assert sum("not re-checked" in r["note"] for r in tech.values()) == 7


def test_hs_links_are_direct_only_resolve_and_carry_the_linked_value(db):
    links = refdata.rows(db, "hs_factor_links")
    assert len(links) == 235 and {r["match_status"] for r in links} == {"Direct match", "Country-specific"}
    codes = {r[0] for r in db.execute("SELECT code FROM hs_codes")}
    for link in links:
        assert link["hs_code"] in codes
        if link["factor_table"] == "activity_factors":
            factor = db.execute("SELECT value_metric, unit_metric FROM activity_factors WHERE activity_id=?", (link["factor_id"],)).fetchone()
            assert factor and factor[1] in ("kg CO2e per kg", "kg CO2e per kg of product") and Decimal(factor[0]) == Decimal(link["value_metric"])
        elif link["factor_table"] == "product_averages":
            factor = db.execute("SELECT value_metric FROM product_averages WHERE product_code=?", (link["factor_id"],)).fetchone()
            assert factor and Decimal(factor[0]) == Decimal(link["value_metric"])
        else:
            assert link["factor_table"] == "country_data" and link["factor_id"] == "electricity_carbon_intensity"
    proxies = rows(ROOT / "docs/data-verification/2026-11-19/hs-proxy-links.csv")
    assert len(proxies) == 558 and {r["match_status"] for r in proxies} == {"Proxy (closest available)"}
    assert not {r["hs_code"] for r in links} & {r["hs_code"] for r in proxies}     # a code is either a direct link or a proxy to review
