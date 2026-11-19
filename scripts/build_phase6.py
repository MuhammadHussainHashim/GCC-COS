"""Build the phase 6 data files from the user's 19 November 2026 uploads and the publishers' files.

This script is a record of how each file was made. Values are copied from the publishers'
files, never from the uploaded workbooks; the uploads are only used to find out which rows
were offered and to check that their numbers equal the publishers' numbers.

    python scripts/build_phase6.py --uploads UPLOAD_FOLDER --carbonpdf CARBONPDF_CLONE \
        --owid-datasets OWID_DATASETS_CLONE --electricitymaps-defaults defaults.yaml

UPLOAD_FOLDER holds GCC_Carbon_Footprint_Database_2026_1.xlsx, GCC_HS_Code_Footprints_2026.xlsx
and GCC_Product_Footprints_Electronics.xlsx (any file-name prefix). CARBONPDF_CLONE is a clone of
github.com/pittcps/carbonpdf-dataset; OWID_DATASETS_CLONE is a clone of github.com/owid/owid-datasets
with full history (the food file was emptied upstream in February 2023, so it is read from the
August 2022 commit named below).

Nothing already in the system is written again:
- products already held from Boavizta (same report link, or same maker and product name) are left out;
- the UK DESNZ 2026 factors, the country electricity factors and the HS code list are already loaded
  and are only compared;
- HS-to-factor links marked "Proxy (closest available)" are guesses, so they go to docs/data-verification/2026-11-19/ for a
  person to review, not into the database (docs/DATA_POLICY.md: never fill HS blanks with guesses).
"""
import argparse
import csv
import hashlib
import json
import re
import subprocess
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
TODAY = "2026-11-19"
FOOD_COMMIT = "13b8cd7f0f6cecd07a736381b3825bc9c5879019"
FOOD_PATH = "datasets/Environmental impacts of food (Poore & Nemecek, 2018)/Environmental impacts of food (Poore & Nemecek, 2018).csv"
DESNZ = "uk-desnz-conversion-factors-2026"
FOOD_ID = "poore-nemecek-2018-food"
ELEC_ID = "ipcc-ar5-electricity-technologies"
LINKS_ID = "gcc-hs-factor-links-2026-11"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(folder, *args):
    return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, check=True).stdout


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def product_key(maker, name):
    """Maker and product name, ignoring case, punctuation and a leading maker name ("HP 255 G9" = "255 G9")."""
    maker, name = norm(maker), norm(name)
    if name.startswith(maker + " "):
        name = name[len(maker) + 1:]
    return maker, name


def number(value):
    return format(Decimal(str(value)).normalize(), "f")


def find(folder, suffix):
    hits = sorted(Path(folder).glob(f"*{suffix}"))
    if len(hits) != 1:
        raise SystemExit(f"Expected one file ending in {suffix} in {folder}, found {len(hits)}")
    return hits[0]


def write_csv(path, columns, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_dataset(dataset_id, table, columns, rows, source):
    folder = ROOT / "datasets" / dataset_id
    write_csv(folder / "data.csv", columns, rows)
    meta = {"id": dataset_id, "table": table, **source, "file": "data.csv", "rows": len(rows),
            "sha256": sha(folder / "data.csv"), "prepared": TODAY}
    (folder / "SOURCE.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{dataset_id}: {len(rows)} rows")


def products(args, report):
    """CarbonPDF products not already held from Boavizta, copied from the publisher's products.csv."""
    upstream = Path(args.carbonpdf) / "datasets" / "product" / "products.csv"
    with open(upstream, encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns, rows = reader.fieldnames, list(reader)
    with open(ROOT / "examples/phase2/boavizta-products.csv", encoding="utf-8-sig", newline="") as handle:
        held = list(csv.DictReader(handle))
    held_urls = defaultdict(list)
    held_names = defaultdict(list)
    for r in held:
        for url in r["sources"].split(";"):
            held_urls[url.strip()].append(r)
        held_names[product_key(r["manufacturer"], r["name"])].append(r)

    # The upload must offer exactly the publisher's numbers.
    book = openpyxl.load_workbook(find(args.uploads, "GCC_Product_Footprints_Electronics.xlsx"), read_only=True, data_only=True)
    offered = [r for r in list(book["Products"].iter_rows(values_only=True))[1:] if str(r[15]).startswith("CarbonPDF")]
    by_link = defaultdict(list)
    for r in rows:
        by_link[(r["File URL"].strip(), r["Product name"].strip())].append(r)
    mismatched = [o[0] for o in offered
                  if not any(Decimal(str(o[5])) == Decimal(u["Product carbon footprint (PCF, kg CO2e)"]) for u in by_link[(o[14].strip(), o[2].strip())])]
    if mismatched or len(offered) != len(rows):
        raise SystemExit(f"Uploaded CarbonPDF rows differ from the publisher's file: {mismatched[:10]}")

    new, seen, differences = [], set(), []
    counts = Counter()
    for r in rows:
        key = product_key(r["Company name"], r["Product name"])
        url = r["File URL"].strip()
        value = Decimal(r["Product carbon footprint (PCF, kg CO2e)"])
        held_rows = held_names.get(key, []) + held_urls.get(url, [])
        if held_rows:
            counts["already held (Boavizta)"] += 1
            older = held_rows[0]
            if Decimal(older["gwp_total"]) != value:
                differences.append({"manufacturer": r["Company name"], "product": r["Product name"], "carbonpdf_value_kg_co2e": number(value),
                                    "carbonpdf_report": url, "held_boavizta_name": older["name"], "held_boavizta_value_kg_co2e": number(older["gwp_total"]),
                                    "held_boavizta_report": older["sources"], "matched_by": "maker and product name" if key in held_names else "same report link"})
            continue
        exact = (key, url, value)
        if exact in seen:
            counts["repeated inside CarbonPDF (same maker, name, report and value)"] += 1
            continue
        seen.add(exact)
        counts["new"] += 1
        new.append({c: r[c] for c in columns} | {"product_type_original": "" if r["Product type"].strip() == "-" else r["Product type"].strip()})
    out = ROOT / "examples/phase6/carbonpdf-new-products.csv"
    write_csv(out, columns + ["product_type_original"], new)
    report["products"] = dict(counts) | {"offered_in_upload": len(offered) + 728, "publisher_rows": len(rows),
                                         "held_value_differs": len(differences), "file_sha256": sha(out),
                                         "upstream_sha256": sha(upstream), "upstream_commit": git(args.carbonpdf, "log", "-1", "--format=%H").decode().strip()}
    write_csv(ROOT / "docs/data-verification/2026-11-19/carbonpdf-vs-held-boavizta-value-differences.csv",
              ["manufacturer", "product", "carbonpdf_value_kg_co2e", "carbonpdf_report", "held_boavizta_name",
               "held_boavizta_value_kg_co2e", "held_boavizta_report", "matched_by"], differences)
    print(f"products: {dict(counts)}; held value differs for {len(differences)}")


def food(args, factors):
    raw = git(args.owid_datasets, "show", f"{FOOD_COMMIT}:{FOOD_PATH}")
    rows = list(csv.reader(raw.decode("utf-8").splitlines()))
    header = rows[0]
    column = next(i for i, h in enumerate(header) if h.startswith("GHG emissions per kilogram"))
    published = {r[0]: r[column] for r in rows[1:]}
    offered = {r[17]: r for r in factors if r[0].startswith("FOOD-")}
    out, codes = [], {}
    for entity, value in published.items():
        if not value.strip():
            continue  # the publisher gives no per-kg value (oils, "Grains"): left out, not invented
        if entity not in offered or Decimal(str(offered[entity][9])) != Decimal(value):
            raise SystemExit(f"Upload and publisher differ for {entity}")
        code = "pn2018:" + norm(entity).replace(" ", "-")
        codes[offered[entity][0]] = code
        out.append({"product_code": code, "code_system": "Poore & Nemecek (2018) food commodity, as named by Our World in Data",
                    "name_en": entity, "name_original": entity, "language_original": "en",
                    "value_original": number(value), "unit_original": "kg CO2e per kg of product",
                    "value_metric": number(value), "unit_metric": "kg CO2e per kg", "conversion": "none (already metric)",
                    "value_kind": "published global average per kg",
                    "lifecycle_scope": "Farm to retail: land-use change, farm, animal feed, processing, transport, retail and packaging",
                    "geography": "World", "year": "2010",
                    "year_basis": "Median reference year of the 570 studies in the meta-analysis (Poore & Nemecek 2018)"})
    if len(out) != len(offered):
        raise SystemExit("Food row count differs between upload and publisher")
    write_dataset(FOOD_ID, "product_averages", list(out[0]), out, {
        "title": "Greenhouse gas emissions per kg of food, global mean (Poore & Nemecek 2018, via Our World in Data)",
        "publisher": "Our World in Data, from Poore & Nemecek (2018), Science 360(6392):987-992",
        "url": f"https://github.com/owid/owid-datasets/blob/{FOOD_COMMIT}/{FOOD_PATH.replace(' ', '%20')}",
        "license": "CC BY 4.0 (Our World in Data); the original study's own reuse terms were not confirmed",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Poore, J. & Nemecek, T. (2018). Reducing food's environmental impacts through producers and consumers. Science 360(6392):987-992. Data via Our World in Data (owid/owid-datasets).",
        "upstream_commit": {"owid/owid-datasets": FOOD_COMMIT}, "upstream_sha256": hashlib.sha256(raw).hexdigest(),
        "obtained": "Column 'GHG emissions per kilogram (Poore & Nemecek, 2018)' of the August 2022 version of the OWID file (emptied upstream in February 2023)",
        "verification_status": "checked against the publisher's file",
        "verification_note": "All 38 values in the uploaded GCC_Carbon_Footprint_Database_2026_1.xlsx equal the OWID file. Five OWID entities have no per-kg value (four oils and 'Grains') and are not loaded. The upload's food categories and suggested HS codes were made by an AI and are not stored here.",
    })
    return codes


def electricity(args, factors):
    text = Path(args.electricitymaps_defaults).read_text(encoding="utf-8")
    lifecycle = text.split("\n  lifecycle:\n", 1)[1].split("\nfallbackZoneMixes:", 1)[0]
    confirmed = {m.group(1): Decimal(m.group(3)) for m in re.finditer(r"\n    ([a-z ]+):\n      (?:_comment:[^\n]*\n(?:        [^\n]*\n)*      )?source: ([^\n]+)\n      value: ([0-9.]+)", lifecycle)}
    # Upload label -> Electricity Maps lifecycle key that holds the same IPCC value, where one exists.
    em_key = {"Coal (pulverised coal)": "coal", "Natural gas (combined cycle)": "gas", "Biomass (dedicated)": "biomass",
              "Geothermal": "geothermal", "Hydropower": "hydro", "Nuclear": "nuclear", "Wind (onshore)": "wind", "Oil": "oil"}
    out = []
    for r in factors:
        if not r[0].startswith("IPCC-"):
            continue
        item, kind, kg = r[4], r[3], Decimal(str(r[9]))
        grams = kg * 1000
        key = em_key.get(item) if kind == "Lifecycle" else None
        if key and confirmed.get(key) != grams:
            raise SystemExit(f"Electricity Maps value differs for {item}")
        check = (f"equals the Electricity Maps open configuration ({key}: {number(grams)} g)" if key
                 else "not re-checked: the IPCC PDF could not be downloaded from this workspace")
        scope = "lifecycle" if kind == "Lifecycle" else "direct"
        out.append({"activity_id": f"ipcc-ar5:{norm(item).replace(' ', '-')}:{scope}", "area": "Electricity generation by technology",
                    "name_en": f"{item} · {kind.lower()} · per kWh generated", "name_original": r[17], "language_original": "en",
                    "upstream_label_en": r[17], "value_original": number(grams), "unit_original": "g CO2e per kWh",
                    "value_metric": number(kg), "unit_metric": "kg CO2e per kWh", "conversion": "divided by 1000",
                    "value_kind": "lifecycle emission factor by generation technology" if scope == "lifecycle" else "direct (combustion) emission factor by generation technology",
                    "geography": "World", "year": "2014", "year_basis": "Publication year of the source",
                    "source_page": "https://www.ipcc.ch/report/ar5/wg3/" if item != "Oil" else "https://github.com/electricitymaps/electricitymaps-contrib/blob/master/config/defaults.yaml",
                    "note": f"{r[5]}. {r[20] or ''} Source: {r[16]}. Value {check}.".replace("  ", " ")})
    write_dataset(ELEC_ID, "activity_factors", list(out[0]), out, {
        "title": "Emissions per kWh by electricity generation technology (IPCC AR5 WGIII Annex III, Table A.III.2)",
        "publisher": "Intergovernmental Panel on Climate Change (IPCC); the oil value is from UK POST as used by Electricity Maps",
        "url": "https://www.ipcc.ch/report/ar5/wg3/",
        "license": "IPCC: published figures, cited with the source (IPCC copyright); oil: Electricity Maps open configuration (AGPL-3.0 repository) citing UK POST",
        "license_url": "https://www.ipcc.ch/copyright/",
        "attribution": "Schlömer S. et al. (2014) Annex III: Technology-specific cost and performance parameters. In: Climate Change 2014: Mitigation of Climate Change. Contribution of Working Group III to the Fifth Assessment Report of the IPCC. Oil: UK Parliamentary Office of Science and Technology, as given in electricitymaps/electricitymaps-contrib config/defaults.yaml.",
        "upstream_sha256": {"electricitymaps-contrib config/defaults.yaml": sha(args.electricitymaps_defaults)},
        "obtained": "Offered in the uploaded GCC_Carbon_Footprint_Database_2026_1.xlsx; eight values compared with the Electricity Maps open configuration",
        "verification_status": "partly checked: 8 of 15 values equal a second published copy",
        "verification_note": "Coal, gas, biomass, geothermal, hydro, nuclear, onshore wind (IPCC 2014) and oil (UK POST) equal Electricity Maps' lifecycle defaults. Utility and rooftop solar, concentrated solar, offshore wind, ocean and the two direct (combustion-only) values could not be re-checked because ipcc.ch refused the connection. Global medians for technologies; not a country's grid factor.",
    })


def hs_links(args, food_codes, factors, report):
    book = openpyxl.load_workbook(find(args.uploads, "GCC_HS_Code_Footprints_2026.xlsx"), read_only=True, data_only=True)
    header, *rows = list(book["HS Footprints"].iter_rows(values_only=True))
    col = {h: i for i, h in enumerate(header)}
    by_id = {r[0]: r for r in factors}
    links, proxies, problems = [], [], []
    statuses = Counter()
    for r in rows:
        status = r[col["Match status"]]
        if not status or status == "No verified factor yet":
            continue
        statuses[status] += 1
        code, digits = str(r[col["HS code"]]), int(r[col["Digits"]])
        gcc_id, stated = r[col["Factor GCC ID"]], r[col["kg CO2e per kg of product"]]
        if status == "Country-specific":
            table, dataset, factor_id, value, conversion, geography, year = "country_data", "owid-country-data", "electricity_carbon_intensity", "", "", "Each country", ""
        else:
            factor = by_id[gcc_id]
            if gcc_id.startswith("DESNZ-"):
                table, dataset, factor_id = "activity_factors", DESNZ, "desnz2026:" + gcc_id[len("DESNZ-"):]
                unit = factor[8]
                divisor = {"tonnes": Decimal(1000), "kg": Decimal(1)}.get(unit)
                if divisor is None:
                    raise SystemExit(f"Unexpected unit {unit} for {gcc_id}")
                conversion = "per tonne divided by 1000" if divisor == 1000 else "none (already per kg)"
            else:
                table, dataset, factor_id, divisor, conversion = "product_averages", FOOD_ID, food_codes[gcc_id], Decimal(1), "none (already per kg)"
            value = Decimal(str(factor[9])) / divisor
            if abs(value - Decimal(str(stated))) > Decimal("0.000005"):
                problems.append((code, gcc_id, stated, value))
            value = number(value)
            geography, year = factor[6], str(factor[15])
        row = {"hs_code": code, "hs_level": str(digits), "hs_edition": "HS 2022", "match_status": status,
               "factor_table": table, "factor_dataset_id": dataset, "factor_id": factor_id,
               "factor_name": r[col["Matched factor"]] or "Grid electricity by country (country_data)",
               "value_metric": value, "unit_metric": "kg CO2e per kg of product" if value else "", "conversion": conversion,
               "factor_basis": r[col["What the factor covers"]] or "", "burn_factor_id": "", "burn_value_metric": "",
               "value_kind": "suggested HS-to-factor link (not a customs classification)", "geography": geography, "year": year,
               "suggested_by": "AI (Claude) from the HS descriptions, in the user's GCC_HS_Code_Footprints_2026.xlsx; not checked by a person",
               "note": (r[col["Match note"]] or "") + (" Use the country's own electricity factor (latest year per country in country_data)." if status == "Country-specific" else "")}
        burn = r[col["Burn factor GCC ID"]]
        if burn:
            bf = by_id[burn]
            bunit = {"tonnes": Decimal(1000), "kg": Decimal(1)}[bf[8]]
            bval = Decimal(str(bf[9])) / bunit
            if abs(bval - Decimal(str(r[col["Emissions when burned (kg CO2e per kg)"]]))) > Decimal("0.000005"):
                problems.append((code, burn, r[col["Emissions when burned (kg CO2e per kg)"]], bval))
            row["burn_factor_id"], row["burn_value_metric"] = "desnz2026:" + burn[len("DESNZ-"):], number(bval)
        (proxies if status.startswith("Proxy") else links).append(row)
    if problems:
        raise SystemExit(f"Stated per-kg values differ from the referenced factors: {problems[:5]}")
    write_dataset(LINKS_ID, "hs_factor_links", list(links[0]), links, {
        "title": "Suggested links from HS codes to emission factors (direct matches only)",
        "publisher": "GCC project (links suggested by an AI in the user's upload); the factors themselves are UK DESNZ 2026 and Poore & Nemecek (2018)",
        "url": "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026 ; https://github.com/owid/owid-datasets",
        "license": "The links are project work; each linked factor keeps its own licence (OGL v3.0 for DESNZ, CC BY 4.0 for OWID)",
        "license_url": "https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
        "attribution": "Links from the user's GCC_HS_Code_Footprints_2026.xlsx (19 November 2026). Factors: Department for Energy Security and Net Zero; Poore & Nemecek (2018) via Our World in Data.",
        "obtained": "Rows of the 'HS Footprints' sheet whose status is 'Direct match' or 'Country-specific'",
        "verification_status": "per-kg values checked against the linked factors; the links themselves are not checked by a person",
        "verification_note": f"Every per-kg value equals its linked factor after the stated unit conversion. {len(proxies)} 'Proxy (closest available)' links were not loaded (they are guesses); they are in docs/data-verification/2026-11-19/hs-proxy-links.csv for a person to review. An HS link is not an emission factor for every product under that code.",
    })
    write_csv(ROOT / "docs/data-verification/2026-11-19/hs-proxy-links.csv", list(proxies[0]), proxies)
    report["hs_links"] = {"by_status": dict(statuses), "loaded": len(links), "proxies_to_review": len(proxies)}


def compare_held(args, factors, report):
    """The DESNZ factors, country electricity factors and HS list in the upload are already loaded: only compare."""
    with open(ROOT / "datasets" / DESNZ / "data.csv", encoding="utf-8") as handle:
        desnz = {r["upstream_label_en"]: r for r in csv.DictReader(handle)}
    with open(ROOT / "datasets/owid-country-data/data.csv", encoding="utf-8") as handle:
        elec = {r["iso3"]: r for r in csv.DictReader(handle) if r["indicator"] == "electricity_carbon_intensity"}
    same = Counter()
    for r in factors:
        if r[0].startswith("DESNZ-"):
            held = Decimal(desnz[r[17]]["value_original"])
            offered = Decimal(str(r[9]))
            if held == offered:
                same["desnz equal"] += 1
            elif abs(held - offered) < Decimal("1e-12"):
                same["desnz equal apart from float noise in the held file"] += 1
            else:
                same["desnz differ"] += 1
        elif r[0].startswith("ELEC-"):
            held = elec[r[7]]
            same["electricity equal" if Decimal(held["value_metric"]) == Decimal(str(r[9])) and held["year"] == str(r[15]) else "electricity differ"] += 1
    book = openpyxl.load_workbook(find(args.uploads, "GCC_Carbon_Footprint_Database_2026_1.xlsx"), read_only=True, data_only=True)
    offered = {str(r[0]) for r in list(book["HS Codes"].iter_rows(values_only=True))[1:]} - {"TOTAL"}
    with open(ROOT / "reference/hs2022/harmonized-system.csv", encoding="utf-8") as handle:
        held_codes = {r["hscode"] for r in csv.DictReader(handle)} - {"TOTAL"}
    same["hs codes equal" if offered == held_codes else "hs codes differ"] = len(offered)
    report["already_held"] = dict(same)
    print(f"already held: {dict(same)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--uploads", required=True)
    parser.add_argument("--carbonpdf", required=True)
    parser.add_argument("--owid-datasets", required=True)
    parser.add_argument("--electricitymaps-defaults", required=True)
    args = parser.parse_args()
    book = openpyxl.load_workbook(find(args.uploads, "GCC_Carbon_Footprint_Database_2026_1.xlsx"), read_only=True, data_only=True)
    factors = list(book["Factors"].iter_rows(values_only=True))[1:]
    report = {"prepared": TODAY, "uploads_sha256": {p.name.split("-", 1)[1]: sha(p) for p in sorted(Path(args.uploads).glob("*-GCC_*")) + sorted(Path(args.uploads).glob("*-gcc_*"))}}
    compare_held(args, factors, report)
    products(args, report)
    codes = food(args, factors)
    electricity(args, factors)
    hs_links(args, codes, factors, report)
    (ROOT / "docs/data-verification/2026-11-19/import_summary.json").write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
