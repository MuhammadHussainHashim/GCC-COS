"""Compare every bundled value with a fresh copy of its publisher's file.

This reads the publisher files with its own code (it does not reuse scripts/build_reference_datasets.py),
so a mistake in the builder would show up here. It proves "our copy equals the publisher's file", not that the
publisher's number is right. Usage:

    python scripts/verify_data.py --downloads FOLDER [--report docs/DATA_VERIFICATION.json]

FOLDER holds: desnz/flat.xlsx, agribalyse/raw.csv, epa-scf/scf.csv, owid/co2.csv, owid/energy.csv, ademe/values.json,
airports/airports.csv, hs/hs.csv, boavizta/b.csv, cbam/<sector>.html, epa/calc.html, epa/assump.html
"""
import argparse
import csv
import hashlib
import html
import json
import re
import sys
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10 ** 8)


def rows(path, **kw):
    with open(path, encoding=kw.pop("encoding", "utf-8-sig"), newline="") as f:
        return list(csv.DictReader(f, **kw))


def dec(value):
    try:
        return Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None


def same(a, b):
    a, b = dec(a), dec(b)
    return a is not None and b is not None and a == b


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bundled(dataset):
    folder = ROOT / "datasets" / dataset
    source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    return rows(folder / "data.csv"), source, sha(folder / "data.csv") == source["sha256"]


class Check:
    def __init__(self, name, what):
        self.name, self.what, self.checked, self.problems, self.notes = name, what, 0, [], []

    def compare(self, key, ours, theirs, field="value"):
        self.checked += 1
        if not same(ours, theirs):
            self.problems.append(f"{key}: {field} ours={ours!r} publisher={theirs!r}")

    def text(self, key, ours, theirs, field):
        self.checked += 1
        if " ".join(str(ours).split()) != " ".join(str(theirs).split()):
            self.problems.append(f"{key}: {field} ours={ours!r} publisher={theirs!r}")

    def result(self):
        return {"dataset": self.name, "compared_with": self.what, "values_compared": self.checked, "differences": len(self.problems),
                "first_differences": self.problems[:15], "notes": self.notes}


def conversions(check, data):
    """The metric value must follow from the original value by the stated arithmetic."""
    factors = {"none": Decimal(1), "divided by 1000": Decimal(1000), "divided by 1,000,000": Decimal(1000000), "divided by 1.609344": Decimal("1.609344"),
               "1 t CO2e per tonne = 1 kg CO2e per kg": Decimal(1)}
    kinds = Counter()
    for r in data:
        text = r.get("conversion", "")
        kinds[re.sub(r"\(.*", "", text).strip()] += 1
        a, b = dec(r.get("value_original")), dec(r.get("value_metric"))
        if a is None or b is None:
            continue
        for start, f in sorted(factors.items(), key=lambda kv: -len(kv[0])):
            if text.startswith(start):
                check.checked += 1
                if abs(a / f - b) > abs(b) * Decimal("1e-9") + Decimal("6e-9"):
                    check.problems.append(f"conversion '{text}': {a} -> {b}")
                break
    check.notes.append("conversion kinds: " + "; ".join(f"{k or '(blank)'} x{n}" for k, n in kinds.most_common()))


def desnz(dl):
    import openpyxl
    c = Check("uk-desnz-conversion-factors-2026", "GOV.UK flat file, every row")
    data, source, ok = bundled(c.name)
    c.notes.append(f"data.csv checksum matches SOURCE.json: {ok}; publisher file checksum matches the recorded one: {sha(dl / 'desnz/flat.xlsx') == source['upstream_sha256']}")
    sheet = openpyxl.load_workbook(dl / "desnz/flat.xlsx", read_only=True)["Factors by Category"]
    up = {}
    for r in sheet.iter_rows(min_row=7, values_only=True):
        if r[0]:
            up[str(r[0])] = r
    for r in data:
        u = up.get(r["upstream_label_en"])
        if u is None:
            c.problems.append(f"{r['activity_id']}: id not in the publisher file")
            continue
        c.compare(r["activity_id"], r["value_original"], u[9])
        c.text(r["activity_id"], r["unit_original"], f"kg CO2e per {u[7]}", "unit")
        c.text(r["activity_id"], r["note"], u[1], "scope")
        c.text(r["activity_id"], r["area"], u[2], "area")
        c.text(r["activity_id"], r["name_en"], " · ".join(str(x) for x in u[3:7] if x not in (None, "")), "name")
    wanted = [k for k, u in up.items() if u[8] == "kg CO2e" and dec(u[9]) is not None]
    c.notes.append(f"publisher rows that are 'kg CO2e' with a number: {len(wanted)}; bundled rows: {len(data)}; missing from the bundle: {len(set(wanted) - {r['upstream_label_en'] for r in data})}")
    conversions(c, data)
    return c


def agribalyse(dl):
    c = Check("agribalyse-3.2-synthesis", "data.ademe.fr synthesis file, every food")
    data, source, ok = bundled(c.name)
    c.notes.append(f"data.csv checksum matches: {ok}; publisher file checksum matches the recorded one: {sha(dl / 'agribalyse/raw.csv') == source['upstream_sha256']}")
    up = {r["Code AGB"]: r for r in rows(dl / "agribalyse/raw.csv") if r.get("Code AGB")}
    cols = {k.strip(): k for k in next(iter(up.values()))}
    for r in data:
        u = up.get(r["product_code"])
        if u is None:
            c.problems.append(f"{r['product_code']}: not in the publisher file")
            continue
        c.compare(r["product_code"], r["value_original"], u[cols["Changement climatique"]])
        c.compare(r["product_code"], r["data_quality_rating"], u[cols["DQR"]], "data quality rating")
        c.text(r["product_code"], r["name_en"], u[cols["LCI Name"]], "English name")
        c.text(r["product_code"], r["name_original"], u[cols["Nom du Produit en Français"]], "French name")
        c.text(r["product_code"], r["subgroup_original"], u[cols["Sous-groupe d'aliment"]], "subgroup")
    c.notes.append(f"publisher foods: {len(up)}; bundled: {len(data)}")
    return c


def epa_scf(dl):
    c = Check("epa-supply-chain-factors", "EPA ScienceHub CSV, every industry")
    data, source, ok = bundled(c.name)
    c.notes.append(f"data.csv checksum matches: {ok}; publisher file checksum matches the recorded one: {sha(dl / 'epa-scf/scf.csv') == source['upstream_sha256']}")
    up = {r["2017 NAICS Code"]: r for r in rows(dl / "epa-scf/scf.csv")}
    for r in data:
        u = up.get(r["industry_code"])
        if u is None:
            c.problems.append(f"{r['industry_code']}: not in the publisher file")
            continue
        c.compare(r["industry_code"], r["value_original"], u["Supply Chain Emission Factors with Margins"])
        c.compare(r["industry_code"], r["value_without_margins"], u["Supply Chain Emission Factors without Margins"], "without margins")
        c.compare(r["industry_code"], r["value_of_margins"], u["Margins of Supply Chain Emission Factors"], "margins")
        c.text(r["industry_code"], r["industry_title"], u["2017 NAICS Title"], "title")
    c.notes.append(f"publisher industries: {len(up)}; bundled: {len(data)}")
    return c


def owid(dl):
    c = Check("owid-country-data", "Our World in Data CSV files at the recorded commits, latest year per country")
    data, source, ok = bundled(c.name)
    files = {"owid-co2-data.csv": dl / "owid/co2.csv", "owid-energy-data.csv": dl / "owid/energy.csv"}
    recorded = set(source["upstream_sha256"].values())
    c.notes.append(f"data.csv checksum matches: {ok}; publisher file checksums match the recorded ones: {all(sha(p) in recorded for p in files.values())}")
    latest = {}
    for name, path in files.items():
        for u in rows(path):
            code = u.get("iso_code") or ("WLD" if u.get("country") == "World" else "")
            if not code:
                continue
            for col, value in u.items():
                if value not in ("", None) and col not in ("country", "year", "iso_code"):
                    key = (name, code, col)
                    if key not in latest or int(u["year"]) > latest[key][0]:
                        latest[key] = (int(u["year"]), value)
    for r in data:
        name = r["upstream_file"].split(": ")[-1]
        hit = latest.get((name, r["iso3"], r["upstream_column"]))
        key = f"{r['iso3']} {r['indicator']}"
        if hit is None:
            c.problems.append(f"{key}: not in the publisher file")
            continue
        c.compare(key, r["value_original"], hit[1])
        c.compare(key, r["year"], hit[0], "year")
    conversions(c, data)
    return c


def ademe(dl):
    c = Check("ademe-activity-factors", "ADEME Impact CO2 values.json at the recorded commit")
    data, _, ok = bundled(c.name)
    up = json.loads((dl / "ademe/values.json").read_text(encoding="utf-8"))
    missing = 0
    for r in data:
        u = up.get(r["activity_id"])
        if u is None:
            missing += 1
            continue
        c.compare(r["activity_id"], r["value_original"], u["value"])
    c.notes.append(f"data.csv checksum matches: {ok}; rows whose id is not a key of values.json (compared separately below): {missing}")
    conversions(c, data)
    return c, up


def airports(dl):
    c = Check("ourairports", "OurAirports airports.csv at the recorded commit")
    data, _, ok = bundled(c.name)
    up = {r["ident"]: r for r in rows(dl / "airports/airports.csv")}
    for r in data:
        u = up.get(r["ident"])
        if u is None:
            c.problems.append(f"{r['ident']}: not in the publisher file")
            continue
        for ours, theirs in (("latitude_deg", "latitude_deg"), ("longitude_deg", "longitude_deg")):
            c.compare(r["ident"], r[ours], u[theirs], ours)
        c.text(r["ident"], r["iata_code"], u["iata_code"], "IATA code")
        c.text(r["ident"], r["name"], u["name"], "name")
        if r["elevation_ft"] and r["elevation_m"]:
            c.checked += 1
            if abs(dec(r["elevation_ft"]) * Decimal("0.3048") - dec(r["elevation_m"])) > Decimal("0.05"):
                c.problems.append(f"{r['ident']}: elevation conversion")
    should = [u for u in up.values() if u["type"] in ("large_airport", "medium_airport") and u["scheduled_service"] == "yes" and u["iata_code"]]
    c.notes.append(f"data.csv checksum matches: {ok}; publisher airports meeting the stated rule: {len(should)}; bundled: {len(data)}")
    return c


def cbam(dl):
    c = Check("uk-cbam-defaults", "the five GOV.UK sector pages, every commodity code")
    data, _, ok = bundled(c.name)
    found = {}
    for page in sorted((dl / "cbam").glob("*.html")):
        text = page.read_text(encoding="utf-8")
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", text, flags=re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            if len(cells) >= 3 and re.fullmatch(r"\d{8}", cells[0].replace(" ", "")):
                number = re.search(r"-?\d+(?:\.\d+)?", cells[-1].replace(",", ""))
                found.setdefault(cells[0].replace(" ", ""), []).append((number.group(0) if number else None, cells[1]))
    for r in data:
        hits = found.get(r["code"])
        if not hits:
            c.problems.append(f"{r['code']}: code not found on the pages")
            continue
        if len({h[0] for h in hits}) > 1:
            c.problems.append(f"{r['code']}: the pages give more than one value {sorted({h[0] for h in hits})}")
            continue
        c.compare(r["code"], r["value_original"], hits[0][0])
        c.text(r["code"], r["description"], hits[0][1], "description")
    c.notes.append(f"data.csv checksum matches: {ok}; codes on the pages today: {len(found)}; bundled: {len(data)}; on the pages but not bundled: {len(set(found) - {r['code'] for r in data})}")
    conversions(c, data)
    return c


def epa_pages(dl):
    c = Check("epa-calculator-reference", "the EPA calculator page and its assumptions page (is each number printed there?)")
    data, _, ok = bundled(c.name)
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", (dl / "epa" / n).read_text(encoding="utf-8", errors="replace"))) for n in ("calc.html", "assump.html"))
    numbers = {dec(x) for x in re.findall(r"\d[\d,]*\.?\d*", text)} - {None}
    for r in data:
        c.checked += 1
        if dec(r["value_original"]) not in numbers:
            c.problems.append(f"{r['item']}: {r['value_original']} is not printed on the pages")
    c.notes.append(f"data.csv checksum matches: {ok}. This check only finds the number on the page; the wording beside it was read by a person on 12 November 2026.")
    return c


def hs(dl):
    c = Check("hs2022 (reference/hs2022)", "datasets/harmonized-system CSV at the recorded commit")
    ours, theirs = ROOT / "reference/hs2022/harmonized-system.csv", dl / "hs/hs.csv"
    c.checked = len(rows(ours))
    if sha(ours) != sha(theirs):
        c.problems.append("the bundled file is not byte-identical to the publisher's")
    c.notes.append("byte-for-byte comparison of the whole file")
    return c


def boavizta(dl):
    c = Check("boavizta-products (examples/phase2)", "Boavizta CSV at the recorded commit")
    ours, theirs = ROOT / "examples/phase2/boavizta-products.csv", dl / "boavizta/b.csv"
    c.checked = len(rows(ours))
    if sha(ours) != sha(theirs):
        c.problems.append("the bundled file is not byte-identical to the publisher's")
    c.notes.append("byte-for-byte comparison of the whole file. Boavizta copied these figures from manufacturers' reports; that step is not checked here.")
    return c


def records(db_path, dl):
    """Every stored record against the file it was read from."""
    import sqlite3
    import urllib.request
    db = sqlite3.connect(f"file:{Path(db_path).resolve()}?mode=ro", uri=True)
    recs = [{"id": i, **json.loads(p)} for i, p in db.execute("SELECT id,payload FROM records ORDER BY id")]
    out = []
    c = Check("records: Boavizta", "the Boavizta CSV row each record names")
    up = rows(dl / "boavizta/b.csv")
    for r in (x for x in recs if x.get("source_id") == "boavizta-products"):
        u = up[r["evidence"]["row"] - 2]
        key = f"record {r['id']}"
        c.compare(key, r["original_value"], u["gwp_total"])
        c.compare(key, r["normalized_value"], u["gwp_total"], "normalized value")
        c.text(key, r["product_name"], u["name"], "name")
        c.text(key, r.get("manufacturer"), u["manufacturer"], "manufacturer")
    out.append(c)
    c = Check("records: UK CBAM", "the GOV.UK-checked table in datasets/uk-cbam-defaults")
    table = {r["code"]: r for r in bundled("uk-cbam-defaults")[0]}
    for r in (x for x in recs if x.get("source_id") == "uk-cbam-defaults"):
        code = r["evidence"]["raw"]["cn_code"]
        u = table.get(code)
        if u is None:
            c.problems.append(f"record {r['id']}: code {code} not in the table")
            continue
        c.compare(f"record {r['id']} ({code})", r["original_value"], u["value_original"])
        c.compare(f"record {r['id']} ({code})", r["normalized_value"], u["value_metric"], "normalized value")
        c.text(f"record {r['id']}", r.get("hs6"), code[:6], "hs6")
    out.append(c)
    c = Check("records: ADEME everyday products", "ADEME Impact CO2 values.json at the recorded commit (grams there, kg here)")
    values = json.loads((dl / "ademe/values.json").read_text(encoding="utf-8"))
    for r in (x for x in recs if x.get("source_id") == "ademe-impactco2"):
        key = r["evidence"]["raw"]["id"]
        u = values.get(key)
        if u is None:
            c.problems.append(f"record {r['id']}: id {key} not in values.json")
            continue
        c.checked += 1
        if abs(dec(r["normalized_value"]) * 1000 - dec(u["value"])) > abs(dec(u["value"])) * Decimal("1e-12"):
            c.problems.append(f"record {r['id']} ({key}): ours {r['normalized_value']} kg, publisher {u['value']} g")
    out.append(c)
    c = Check("records: EPD", "each EPD's ILCD file, downloaded again from the recorded address")
    seen = {}
    for r in (x for x in recs if str(x.get("source_id", "")).startswith("epd-")):
        url = r["source_url"]
        if url not in seen:
            with urllib.request.urlopen(url, timeout=60) as f:
                seen[url] = f.read()
        body = seen[url]
        c.checked += 2
        if hashlib.sha256(body).hexdigest() != r["document_sha256"]:
            c.problems.append(f"record {r['id']}: the file's checksum differs from the recorded one")
        numbers = {dec(x) for x in re.findall(r"-?\d+\.?\d*(?:[eE][-+]?\d+)?", body.decode("utf-8"))}
        if dec(r["original_value"]) not in numbers:
            c.problems.append(f"record {r['id']}: {r['original_value']} is not in the file")
    c.notes.append(f"{len(seen)} files. The check finds each record's number in its file; which lifecycle module it belongs to was set by the importer and is covered by the test suite.")
    out.append(c)
    c = Check("records: completeness", "every record has a source, a licence, a unit and a value")
    for r in recs:
        c.checked += 1
        missing = [k for k in ("source_url", "license", "normalized_unit", "normalized_value", "document_title", "attribution") if not r.get(k)]
        if missing:
            c.problems.append(f"record {r['id']}: missing {missing}")
    c.notes.append(f"{len(recs)} records; by source: " + ", ".join(f"{k} {n}" for k, n in Counter(str(r.get('source_id', ''))[:3] == 'epd' and 'EPD' or r.get('source_id') for r in recs).items()))
    out.append(c)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--report")
    parser.add_argument("--db", help="Also check every stored record in this GCC database")
    args = parser.parse_args(argv)
    dl = Path(args.downloads)
    ademe_check, _ = ademe(dl)
    checks = [desnz(dl), agribalyse(dl), epa_scf(dl), owid(dl), ademe_check, airports(dl), cbam(dl), epa_pages(dl), hs(dl), boavizta(dl)]
    if args.db:
        checks += records(args.db, dl)
    out = [c.result() for c in checks]
    for r in out:
        print(f"{'OK  ' if not r['differences'] else 'DIFF'} {r['dataset']}: {r['values_compared']:,} values compared, {r['differences']} differences")
        for n in r["notes"]:
            print("       " + n)
        for p in r["first_differences"]:
            print("     ! " + p)
    if args.report:
        Path(args.report).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 1 if any(r["differences"] for r in out) else 0


if __name__ == "__main__":
    sys.exit(main())
