"""Rebuild the CSV files under datasets/ from the supplied workbook and the upstream downloads.

This script is a record of how each dataset file was made. Run it only when the workbook
or an upstream source changes:

    python scripts/build_reference_datasets.py --workbook GCC-carbon-data.xlsx --downloads DOWNLOADS_FOLDER

DOWNLOADS_FOLDER must hold git clones named co2-data, energy-data, ourairports-data,
concordance and impactco2 (see datasets/*/SOURCE.json for the repository addresses).
No value is changed, estimated or filled in here: rows are copied, and unit conversions
are stored beside the original value.
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "datasets"
TODAY = "2026-11-12"


def commit(folder):
    return subprocess.run(["git", "-C", str(folder), "log", "-1", "--format=%H"], capture_output=True, text=True, check=True).stdout.strip()


def write(dataset_id, columns, rows, source):
    folder = OUT / dataset_id
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / "data.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    source = {"id": dataset_id, **source, "file": "data.csv", "rows": len(rows),
              "sha256": hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest(), "prepared": TODAY}
    (folder / "SOURCE.json").write_text(json.dumps(source, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{dataset_id}: {len(rows)} rows")


def sheet(book, name):
    rows = [r for r in book[name].iter_rows(values_only=True) if any(c is not None for c in r)]
    return rows[0], rows[1:]


def text(value):
    return "" if value is None else str(value).strip()


def number(value):
    """Exact text of a number as stored, without float noise."""
    return format(Decimal(str(value)).normalize(), "f")


def clean_label(label):
    label = label.split(";")[-1] if ";" in label else label
    label = re.sub(r"\[[^\]]*\]", "", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label[:1].upper() + label[1:]


def build_cbam(book):
    header, rows = sheet(book, "CBAM defaults")
    out = []
    for row in rows:
        r = dict(zip(header, row))
        cn = text(r["CN code (8-digit)"])
        assert re.fullmatch(r"\d{8}", cn) and text(r["HS code (6-digit)"]) == cn[:6]
        value = Decimal(str(r["Default value (tCO2e per tonne of product)"]))
        out.append({"scheme": "UK CBAM default value", "code_system": "UK commodity code (8-digit)", "code": cn, "hs6": cn[:6], "hs4": cn[:4],
                    "hs_code_basis": "First six digits of the commodity code in the source table",
                    "sector": text(r["Sector"]), "description": text(r["Description"]), "description_basis": text(r["Description basis"]),
                    "value_original": number(value), "unit_original": "t CO2e per tonne of product",
                    "value_metric": number(value), "unit_metric": "kg CO2e per kg of product", "conversion": "1 t CO2e per tonne = 1 kg CO2e per kg",
                    "value_kind": "regulatory default value", "geography": "United Kingdom (imports)", "year": "2026", "year_basis": "Year of publication (16 October 2026)",
                    "published": text(r["Published"]), "source_page": text(r["Source URL"]), "note": text(r["Note"])})
    assert len({r["code"] for r in out}) == len(out) == 570
    write("uk-cbam-defaults", list(out[0]), out, {
        "table": "reference_values", "title": "UK CBAM default values", "publisher": "HM Revenue & Customs (GOV.UK)",
        "url": "https://www.gov.uk/government/publications/check-the-default-values-for-the-carbon-border-adjustment-mechanism-cbam",
        "license": "Open Government Licence v3.0 (Crown copyright)", "license_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "attribution": "Contains public sector information licensed under the Open Government Licence v3.0. HM Revenue & Customs, 'Check the default values for the Carbon Border Adjustment Mechanism (CBAM)', published 16 October 2026.",
        "obtained": "Typed from the GOV.UK pages into the user's workbook on 11 November 2026; copied here unchanged",
        "verification_status": "unverified",
        "verification_note": "GOV.UK could not be reached on 11 or 12 November 2026, so no value was re-checked against the source pages, including commodity code 73065029, whose row was split across two page sections when read. No corrections were made."})


def build_activity(book, downloads):
    values = json.loads((ROOT / "examples/phase5/ademe-upstream/values.json").read_text(encoding="utf-8"))
    french = {r["ID"]: r["Nom de l'objet ou du geste"] for r in csv.DictReader(open(downloads / "impactco2/public/equivalents.csv", encoding="utf-8"))}
    header, rows = sheet(book, "Activity factors")
    areas = {4: ("Transport", "km", "The supplied workbook describes these as per passenger; the source file says only 'km'"),
             8: ("Home heating", "m2 of home per year", ""), 10: ("Digital use", None, "")}
    out = []
    for row in rows:
        r = dict(zip(header, row))
        source = values[text(r["ID"])]
        grams = Decimal(str(source["value"]))
        assert abs(grams / 1000 - Decimal(str(r["kg CO2e per unit"]))) < Decimal("0.0000001"), r["ID"]
        area, per, note = areas[source["category"]]
        # Digital use: the whole upstream label is the unit, for example "Hour[s] of ;video streaming" -> "hour of video streaming".
        per = per or re.sub(r"\s+", " ", re.sub(r"\[[^\]]*\]", "", source["en"].replace(";", ""))).strip().lower()
        out.append({"activity_id": text(r["ID"]), "area": area, "name_en": text(r["Activity (English, translated)"]),
                    "name_original": french.get(text(r["ID"]), text(r["Activity (French, as published)"])), "language_original": "fr",
                    "upstream_label_en": source["en"], "value_original": number(grams), "unit_original": f"g CO2e per {per}",
                    "value_metric": number(grams / 1000), "unit_metric": f"kg CO2e per {per}", "conversion": "divided by 1000",
                    "value_kind": "activity emission factor", "geography": "France", "year": "2026",
                    "year_basis": "Year of the source file version (9 November 2026); the source states no reference year",
                    "source_page": text(r["Source page"]), "note": note})
    write("ademe-activity-factors", list(out[0]), out, {
        "table": "activity_factors", "title": "ADEME Impact CO2 activity factors (transport, home heating, digital use)", "publisher": "ADEME Impact CO2 (incubateur-ademe/impactco2)",
        "url": f"https://raw.githubusercontent.com/incubateur-ademe/impactco2/{commit(downloads / 'impactco2')}/src/utils/Equivalent/values.json",
        "license": "MIT (incubateur-ademe/impactco2 repository), Copyright (c) 2022 Datagir", "license_url": f"https://raw.githubusercontent.com/incubateur-ademe/impactco2/{commit(downloads / 'impactco2')}/license",
        "attribution": "ADEME Impact CO2 (incubateur-ademe/impactco2), Copyright (c) 2022 Datagir, MIT License.",
        "upstream_commit": commit(downloads / "impactco2"), "obtained": "Rebuilt from the unmodified upstream values.json kept in examples/phase5/ademe-upstream; every value equals the workbook's",
        "verification_status": "checked against the publisher's file",
        "verification_note": "French averages. French rail and electric heating run on low-carbon electricity, so those values are too low for most other countries. English names are the workbook's translations; the French name is the publisher's."})


def build_country(book, downloads):
    indicators = [
        ("co2_per_person", "co2-data", "co2_per_capita", "CO2 emissions per person (fossil fuels and industry)", "t CO2 per person per year", None, "CC BY 4.0 (Our World in Data; Global Carbon Budget)"),
        ("consumption_co2_per_person", "co2-data", "consumption_co2_per_capita", "Consumption-based CO2 emissions per person", "t CO2 per person per year", None, "CC BY 4.0 (Our World in Data; Global Carbon Budget)"),
        ("ghg_per_person", "co2-data", "ghg_per_capita", "Greenhouse gas emissions per person, including land use", "t CO2e per person per year", None, "CC BY 4.0 (Our World in Data; Jones et al.)"),
        ("electricity_carbon_intensity", "energy-data", "carbon_intensity_elec", "Lifecycle carbon intensity of electricity generation", "g CO2e per kWh", ("kg CO2e per kWh", Decimal(1000)), "CC BY 4.0 (Our World in Data; Ember)"),
        ("electricity_demand_per_person", "energy-data", "electricity_demand_per_capita", "Total electricity demand per person", "kWh per person per year", None, "CC BY 4.0 (Our World in Data; Ember)"),
        ("electricity_generation_per_person", "energy-data", "per_capita_electricity", "Total electricity generation per person", "kWh per person per year", None, "CC BY 4.0 (Our World in Data; Ember)"),
    ]
    out = []
    for indicator, repo, column, title, unit, metric, licence in indicators:
        codebook = {r["column"]: r for r in csv.DictReader(open(downloads / repo / f"owid-{repo.split('-')[0]}-codebook.csv", encoding="utf-8"))}[column]
        latest = {}
        for r in csv.DictReader(open(downloads / repo / f"owid-{repo.split('-')[0]}-data.csv", encoding="utf-8")):
            iso = r.get("iso_code") or ""
            if r.get(column) in ("", None) or not (re.fullmatch(r"[A-Z]{3}", iso) or r["country"] == "World"):
                continue
            if iso not in latest and r["country"] == "World":
                iso = "WLD"
            if iso not in latest or int(r["year"]) > int(latest[iso]["year"]):
                latest[iso] = {"year": r["year"], "value": r[column], "country": r["country"]}
        for iso in sorted(latest):
            v = latest[iso]
            value = Decimal(v["value"])
            out.append({"iso3": iso, "country": v["country"], "indicator": indicator, "indicator_title": title,
                        "value_original": number(value), "unit_original": unit,
                        "value_metric": number(value / metric[1]) if metric else number(value), "unit_metric": metric[0] if metric else unit,
                        "conversion": "divided by 1000" if metric else "none (already metric)",
                        "value_kind": "per-person country average" if "per_person" in indicator else "country electricity factor",
                        "year": v["year"], "year_basis": "Latest year with a value in the source file",
                        "upstream_file": f"owid/{repo}: owid-{repo.split('-')[0]}-data.csv", "upstream_column": column,
                        "original_source": codebook["source"], "license": licence})
    # every figure in the workbook's Country data sheet must equal the rebuilt one
    header, rows = sheet(book, "Country data")
    built = {(r["iso3"], r["indicator"]): r for r in out}
    for row in rows:
        for position, indicator in ((2, "co2_per_person"), (4, "consumption_co2_per_person"), (6, "ghg_per_person"), (8, "electricity_carbon_intensity")):
            if row[position] is not None:
                found = built[(row[1], indicator)]
                assert abs(Decimal(found["value_original"]) - Decimal(str(row[position]))) < Decimal("0.0006") and int(found["year"]) == row[position + 1], (row[1], indicator)
    write("owid-country-data", list(out[0]), out, {
        "table": "country_data", "title": "Country data: emissions per person and electricity (Our World in Data)", "publisher": "Our World in Data",
        "url": "https://github.com/owid/co2-data ; https://github.com/owid/energy-data",
        "license": "CC BY 4.0 (Our World in Data); the original sources' terms also apply and are named on each row", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Our World in Data (owid/co2-data and owid/energy-data), with data from the Global Carbon Budget, Jones et al. and Ember. Each row names its original source.",
        "upstream_commit": {"owid/co2-data": commit(downloads / "co2-data"), "owid/energy-data": commit(downloads / "energy-data")},
        "upstream_sha256": {f"owid/{repo}": hashlib.sha256((downloads / repo / f"owid-{repo.split('-')[0]}-data.csv").read_bytes()).hexdigest() for repo in ("co2-data", "energy-data")},
        "obtained": "Latest year per country taken from the upstream CSV files; all four indicators in the workbook's 'Country data' sheet equal these values",
        "verification_status": "checked against the publisher's file",
        "verification_note": "Two electricity-per-person indicators were added from the same upstream file. Primary energy per person was left out because one of its sources (Energy Institute) has unclear reuse terms. 'World' is stored with the code WLD."})


def build_links(book, downloads):
    import warnings
    import rdata
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        table = rdata.read_rda(str(downloads / "concordance/data/hs_naics.RData"))["hs_naics"]
    package_pairs = set(zip(table["HS_6d"], table["NAICS_6d"]))
    header, rows = sheet(book, "HS6 to NAICS")
    out = []
    for row in rows:
        r = dict(zip(header, row))
        pair = (text(r["HS code (6-digit)"]), text(r["NAICS code"]))
        assert pair in package_pairs, pair
        out.append({"hs6": pair[0], "hs_edition": "US import codes for 2017 (HS 2017 at six digits)", "industry_system": "NAICS (US, as coded by the US Census Bureau for 2017 imports)",
                    "industry_code": pair[1], "import_lines": text(r["Number of US 10-digit import lines"]), "share_of_lines": number(r["Share of this HS code's lines"]),
                    "geography": "United States", "year": "2017", "year_basis": "Year of the import code list"})
    write("hs6-naics-2017", list(out[0]), out, {
        "table": "hs_industry_links", "title": "HS 6-digit to NAICS industry link (Pierce and Schott concordance, 2017)", "publisher": "Pierce and Schott; redistributed in the insongkim/concordance R package",
        "url": "https://github.com/insongkim/concordance", "license": "MIT (concordance package, Copyright 2022 concordance authors)",
        "license_url": f"https://raw.githubusercontent.com/insongkim/concordance/{commit(downloads / 'concordance')}/LICENSE",
        "attribution": "Pierce, J. R. and Schott, P. K. (2012), 'Concording U.S. Harmonized System Codes over Time'; (2009) NBER Working Paper 15548. Redistributed in the concordance R package (Liao, Kim, Miyano, Zhang), MIT License.",
        "upstream_commit": commit(downloads / "concordance"), "obtained": "Copied from the workbook's 'HS6 to NAICS' sheet",
        "verification_status": "pairs checked against the package",
        "verification_note": "All 6,322 code pairs exist in the package's hs_naics table. The counts of 10-digit import lines and the shares come from the workbook and could not be re-derived, because the package does not carry the 10-digit lines. The codes are 2017 codes: 5,376 six-digit codes, which is not the same list as HS 2022. Some NAICS codes end in X, as in the source."})


def build_benchmarks(book):
    header, rows = sheet(book, "Calculator reference data")
    out, skipped = [], []
    for row in rows:
        r = dict(zip(header, row))
        if text(r["Calculator"]) != "US EPA":
            skipped.append({"calculator": text(r["Calculator"]), "item": text(r["Item"]), "url": text(r["URL"])})
            continue
        stated = text(r["Stated source"])
        years = re.findall(r"\b(?:19|20)\d{2}\b", stated)
        out.append({"publisher": "US EPA Household Carbon Footprint Calculator", "item": text(r["Item"]),
                    "value_original": number(r["Value"]), "unit_original": text(r["Unit"]),
                    "factor_to_metric": number(r["Factor to metric"]) if r["Factor to metric"] is not None else "",
                    "value_metric": number(r["Metric value"]) if r["Metric value"] is not None else "", "unit_metric": text(r["Metric unit"]),
                    "value_kind": "published benchmark or assumption", "stated_source": stated, "geography": "United States",
                    "year": years[-1] if years else "2026",
                    "year_basis": "Year named in the stated source" if years else "Year the page was read (November 2026); the page states no year",
                    "source_page": text(r["URL"]), "note": text(r["Note"])})
    write("epa-calculator-reference", list(out[0]), out, {
        "table": "benchmarks", "title": "US EPA Household Carbon Footprint Calculator: published averages and assumptions", "publisher": "US Environmental Protection Agency",
        "url": "https://www.epa.gov/ghgemissions/carbon-footprint-calculator", "license": "US government work (public domain in the United States)",
        "license_url": "https://www.epa.gov/web-policies-and-procedures/epa-disclaimers#copyright",
        "attribution": "US Environmental Protection Agency, Household Carbon Footprint Calculator and its assumptions page.",
        "obtained": "Typed from the EPA pages into the user's workbook; copied here unchanged",
        "verification_status": "unverified", "verification_note": "epa.gov could not be reached on 12 November 2026, so no value was re-checked against the pages.",
        "left_out": {"reason": "The workbook gives no licence for these calculators' published figures, and their pages could not be opened to read the terms", "rows": skipped}})


def build_airports(downloads):
    out = []
    for r in csv.DictReader(open(downloads / "ourairports-data/airports.csv", encoding="utf-8")):
        if r["iata_code"] and r["type"] in ("large_airport", "medium_airport") and r["scheduled_service"] == "yes":
            out.append({"ident": r["ident"], "iata_code": r["iata_code"], "icao_code": r["icao_code"], "name": r["name"], "type": r["type"],
                        "municipality": r["municipality"], "iso_country": r["iso_country"], "iso_region": r["iso_region"],
                        "latitude_deg": r["latitude_deg"], "longitude_deg": r["longitude_deg"], "elevation_ft": r["elevation_ft"],
                        "elevation_m": number((Decimal(r["elevation_ft"]) * Decimal("0.3048")).quantize(Decimal("0.1"))) if r["elevation_ft"] else ""})
    out.sort(key=lambda r: r["iata_code"])
    write("ourairports", list(out[0]), out, {
        "table": "airports", "title": "Airports with coordinates (OurAirports)", "publisher": "OurAirports (David Megginson and contributors)",
        "url": "https://github.com/davidmegginson/ourairports-data", "license": "Public domain (Unlicense)",
        "license_url": f"https://raw.githubusercontent.com/davidmegginson/ourairports-data/{commit(downloads / 'ourairports-data')}/LICENSE",
        "attribution": "OurAirports (ourairports.com), public domain.", "upstream_commit": commit(downloads / "ourairports-data"),
        "obtained": "Rows of airports.csv that are large or medium airports with scheduled service and an IATA code; values unchanged",
        "verification_status": "copied from the publisher's file",
        "verification_note": "Community-maintained data. Small airfields, heliports and closed airports are left out. Elevation in metres is the source's feet multiplied by 0.3048."})


if __name__ == "__main__":
    import openpyxl
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", required=True)
    parser.add_argument("--downloads", required=True)
    args = parser.parse_args()
    workbook = openpyxl.load_workbook(args.workbook, read_only=True, data_only=True)
    folder = Path(args.downloads)
    build_cbam(workbook)
    build_activity(workbook, folder)
    build_country(workbook, folder)
    build_links(workbook, folder)
    build_benchmarks(workbook)
    build_airports(folder)
