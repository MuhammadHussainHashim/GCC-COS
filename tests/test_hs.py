"""HS layer tests. Product rows below are SYNTHETIC; codes and descriptions come from the bundled HS 2022 list."""
import json

import pytest

from gcc_cos import hs
from gcc_cos.query import select

TABLE, SOURCE = hs.load_table()
MAPPINGS = hs.load_mappings(table=TABLE)


def product(**values):
    return {"entity_type": "product", "data_kind": "published_product_footprint", "category": "electronics", **values}


def test_bundled_code_list_is_the_recorded_file():
    assert SOURCE["edition"] == "HS 2022"
    assert sum(c["level"] == 6 for c in TABLE.values()) == SOURCE["counts"]["subheadings_6_digit"] == 5613
    assert sum(c["level"] == 4 for c in TABLE.values()) == SOURCE["counts"]["headings_4_digit"]
    assert "smartphones" in TABLE["851713"]["description"]


def test_changed_code_list_is_refused(tmp_path):
    for name in ("SOURCE.json", "harmonized-system.csv"):
        (tmp_path / name).write_bytes((hs.REFERENCE / name).read_bytes())
    with open(tmp_path / "harmonized-system.csv", "ab") as handle:
        handle.write(b"XX,999999,Invented,9999,6\n")
    with pytest.raises(ValueError, match="checksum"):
        hs.load_table(tmp_path)


def test_every_bundled_mapping_is_flagged_and_uses_a_real_code():
    assert MAPPINGS
    for mapping in MAPPINGS:
        assert mapping["status"] in {"proposed_not_verified", "unmapped"}  # nothing is verified yet
        assert mapping["basis"].strip()
        assert (mapping["hs_code"] in TABLE) if mapping["status"] != "unmapped" else mapping["hs_code"] is None


def test_laptop_gets_proposed_six_digit_code_with_official_description():
    result = hs.classify(product(subcategory="Laptop", product_name="SYNTHETIC laptop"), MAPPINGS, TABLE, SOURCE)
    assert (result["hs_code"], result["hs_level"], result["hs_heading"]) == ("847130", 6, "8471")
    assert result["hs_status"] == "proposed_not_verified"
    assert result["hs_description"] == TABLE["847130"]["description"]
    assert result["hs_reference_source"] == SOURCE["url"]


def test_desktop_is_heading_level_only_and_subcategory_case_is_ignored():
    assert hs.classify(product(subcategory="Desktop"), MAPPINGS, TABLE, SOURCE)["hs_level"] == 4
    assert hs.classify(product(subcategory="thin client"), MAPPINGS, TABLE, SOURCE)["hs_code"] == "8471"


def test_unknown_and_ambiguous_types_stay_without_a_code():
    for subcategory in ("Hard drive", "SYNTHETIC unknown type", None):
        result = hs.classify(product(subcategory=subcategory), MAPPINGS, TABLE, SOURCE)
        assert result["hs_code"] is None and result["hs_status"] == "unmapped" and result["hs_basis"]


def test_inventory_totals_never_get_a_code():
    row = {"entity_type": "industrial_inventory", "data_kind": "published_inventory", "category": "electronics", "subcategory": "Laptop"}
    assert hs.classify(row, MAPPINGS, TABLE, SOURCE)["hs_code"] is None


def test_existing_exact_rule_evidence_takes_priority():
    row = product(subcategory="Laptop", hs6="851713", hs_evidence="SYNTHETIC ruling reference", hs_edition="HS 2022")
    result = hs.classify(row, MAPPINGS, TABLE, SOURCE)
    assert (result["hs_code"], result["hs_status"]) == ("851713", "exact_rule")


def test_product_name_mapping_beats_product_type_mapping():
    extra = MAPPINGS + [{"match": {"product_name": "SYNTHETIC console"}, "hs_code": "950450", "status": "proposed_not_verified", "basis": "SYNTHETIC"}]
    result = hs.classify(product(subcategory="Laptop", product_name="synthetic CONSOLE"), extra, TABLE, SOURCE)
    assert result["hs_code"] == "950450"


@pytest.mark.parametrize("entry, message", [
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "000000", "status": "proposed_not_verified", "basis": "b"}, "not a 4- or 6-digit code"),
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "84", "status": "proposed_not_verified", "basis": "b"}, "not a 4- or 6-digit code"),
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "proposed_not_verified", "basis": " "}, "written basis"),
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "guessed", "basis": "b"}, "known status"),
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "verified", "basis": "b"}, "verified_by"),
    ({"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "unmapped", "basis": "b"}, "cannot carry a code"),
    ({"match": {"category": "electronics"}, "hs_code": "847130", "status": "proposed_not_verified", "basis": "b"}, "must match"),
])
def test_bad_mapping_files_are_refused(tmp_path, entry, message):
    path = tmp_path / "mappings.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        hs.load_mappings(path, TABLE)


def test_duplicate_mappings_are_refused(tmp_path):
    entry = {"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "proposed_not_verified", "basis": "b"}
    path = tmp_path / "mappings.json"
    path.write_text(json.dumps([entry, {**entry, "match": {"category": "Electronics", "subcategory": "x"}}]), encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate"):
        hs.load_mappings(path, TABLE)


def test_verified_mapping_is_accepted_with_evidence(tmp_path):
    entry = {"match": {"category": "electronics", "subcategory": "X"}, "hs_code": "847130", "status": "verified", "basis": "b",
             "verified_by": "SYNTHETIC reviewer", "verification_evidence": "SYNTHETIC ruling"}
    path = tmp_path / "mappings.json"
    path.write_text(json.dumps([entry]), encoding="utf-8")
    assert hs.load_mappings(path, TABLE)[0]["status"] == "verified"


def test_filter_lookup_and_coverage():
    rows = hs.annotate([product(subcategory="Laptop"), product(subcategory="Desktop"), product(subcategory="Smartphone"),
                        product(subcategory="Hard drive")], MAPPINGS, TABLE, SOURCE)
    assert len(select(rows, hs6="847130")) == 1
    assert len(select(rows, hs6="8471")) == 2
    assert len(select(rows, hs6="85")) == 1
    assert [hs.heading_only(r, "847141") for r in rows] == [False, True, False, False]
    assert [c["code"] for c in hs.lookup("8517.13", TABLE)] == ["851713"]
    assert "851713" in [c["code"] for c in hs.lookup("smartphones", TABLE)]
    assert hs.lookup("zzzz-not-a-product", TABLE) == [] and hs.lookup("", TABLE) == []
    summary = hs.coverage(rows)
    assert summary["by_status"] == {"proposed_not_verified": 3, "unmapped": 1}
    assert [c["hs_code"] for c in summary["codes"]] == ["8471", "847130", "851713"]


def test_real_bundled_data_gets_codes_in_exports(tmp_path):
    from gcc_cos.export import export, selected_rows
    from gcc_cos.ingest import ingest, load_registry
    from gcc_cos.storage import connect
    import pandas as pd
    root = hs.ROOT
    db = connect(tmp_path / "hs.sqlite")
    try:
        manifest = json.loads((root / "examples/phase2/local-files.json").read_text(encoding="utf-8"))
        for source in load_registry(root / "examples/phase2/sources.json"):
            ingest(db, source, tmp_path / "raw", str(root / manifest[source["id"]]), [])
        rows = selected_rows(db, products_only=True)
        assert len(rows) == 1236 and all(r["hs6"] is None for r in rows)  # stored records are untouched
        assert len(selected_rows(db, hs6="851713")) == 50
        export(db, tmp_path / "phones.csv", hs6="851713")
        frame = pd.read_csv(tmp_path / "phones.csv", dtype=str)
        assert set(frame["hs_code"]) == {"851713"} and set(frame["hs_status"]) == {"proposed_not_verified"}
    finally:
        db.close()
