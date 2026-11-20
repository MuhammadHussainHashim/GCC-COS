"""Build datasets/ipcc-efdb-2026-11 from the user's IPCC EFDB export (uploaded 20 November 2026).

    python scripts/build_efdb.py --upload IPCC_EFDB_All_Emission_Factors_2026.xlsx [--check 300]

The export holds every record of the IPCC Emission Factor Database (EFDB). Values and units are
kept exactly as exported. Nothing is converted, summed or turned into CO2e: most EFDB records are
per-gas inventory parameters (for example kg CH4 per TJ, or a fraction), not product footprints.

Repeats are not added twice: records that are identical in every field except the EF ID are stored
once, under the lowest EF ID, and the other IDs are listed in `also_listed_as`. Records with no
value are left out.

The export lost text in some records: 2,894 have a blank description, 75 a blank unit and 959 a "?"
where a character such as "≤", "₂" or "°" was. With --repair CACHE, those records are fetched from the
EFDB website (cached in the JSON file CACHE so a rerun does not fetch again) and the gaps are filled:
a blank description or unit is taken from the website, and a field with "?" is replaced only when the
website text equals the exported text with each "?" standing for one or more characters. Every field
taken from the website is named in `fixed_from_efdb_site`.

With --check N, N records chosen at random (fixed seed) are fetched from the EFDB website by ID
and compared field by field; the result is written to docs/data-verification/2026-11-20/.
"""
import argparse
import concurrent.futures
import csv
import hashlib
import html
import json
import random
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
DATASET = "ipcc-efdb-2026-11"
TODAY = "2026-11-20"
DETAIL = "https://www.ipcc-nggip.iges.or.jp/EFDB/ef_detail.php"
HEADER = ["EF ID", "IPCC 1996 Source/Sink Category", "IPCC 2006 Source/Sink Category", "Gas", "Fuel 1996", "Fuel 2006", "C pool",
          "Type of parameter", "Description", "Technologies / Practices", "Parameters / Conditions", "Region / Regional Conditions",
          "Abatement / Control Technologies", "Other properties", "Value", "Unit", "Equation", "IPCC Worksheet", "Technical Reference",
          "Source of data", "Data provider", "Numeric value (if applicable)"]
COLUMNS = ["ef_id", "ipcc_1996_category", "ipcc_2006_category", "gas", "fuel_1996", "fuel_2006", "carbon_pool", "parameter_type",
           "description", "technologies", "conditions", "region", "abatement", "other_properties", "value_original", "unit_original",
           "value_numeric", "equation", "ipcc_worksheet", "technical_reference", "source_of_data", "data_provider"]
SECTORS = {"1": "Energy", "2": "Industrial processes and product use", "3": "Agriculture, forestry and other land use", "4": "Waste", "5": "Other"}


def text(value):
    return "" if value is None else str(value).strip()


def read_upload(path):
    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    header, *rows = list(book["EFDB All Records"].iter_rows(values_only=True))
    if [text(h) for h in header] != HEADER:
        raise SystemExit("Unexpected columns in 'EFDB All Records'")
    return [{c: text(v) for c, v in zip(COLUMNS, r)} for r in rows]


def build(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[tuple(r[c] for c in COLUMNS if c != "ef_id")].append(r)
    out, counts = [], {"records_in_upload": len(rows), "left_out_no_value": 0, "repeats_folded": 0}
    for members in groups.values():
        members.sort(key=lambda r: int(r["ef_id"]))
        keep = dict(members[0])
        if not keep["value_original"]:
            counts["left_out_no_value"] += len(members)
            continue
        counts["repeats_folded"] += len(members) - 1
        keep["also_listed_as"] = " ".join(m["ef_id"] for m in members[1:])
        sector = (keep["ipcc_2006_category"] or "")[:1]
        keep["sector_2006"] = SECTORS.get(sector, "Not stated") if keep["ipcc_2006_category"] else "Not stated"
        keep["geography"] = keep["region"] or "Not stated"
        keep["value_kind"] = "IPCC EFDB inventory parameter (per gas, not CO2e; not a product footprint)"
        out.append(keep)
    out.sort(key=lambda r: int(r["ef_id"]))
    counts["records_loaded"] = len(out)
    return out, counts


def cell_text(content):
    """Text of one table cell: list items and line breaks become new lines, other tags are dropped."""
    content = re.sub(r"</li>\s*<li[^>]*>|<br\s*/?>", "\n", content, flags=re.I)
    content = html.unescape(re.sub(r"<[^>]+>", "", content)).replace("\xa0", " ")
    return "\n".join(re.sub(r"[ \t]+", " ", line).strip() for line in content.splitlines() if line.strip())


def fetch(ef_id):
    body = urllib.parse.urlencode({"source": "find_id", "ef_id_view": ef_id}).encode()
    request = urllib.request.Request(DETAIL, data=body, headers={"User-Agent": "gcc-cos data check"})
    with urllib.request.urlopen(request, timeout=60) as response:
        page = response.read().decode("utf-8", errors="replace")
    pairs = re.findall(r'<tr[^>]*>\s*<td[^>]*>\s*([^<>]*?):\s*</td>\s*<td[^>]*>(.*?)</td>\s*</tr>', page, flags=re.S | re.I)
    if not pairs:
        raise OSError(f"No record fields on the EFDB page for {ef_id}")
    fields = {}
    for label, content in pairs:
        fields.setdefault(html.unescape(re.sub(r"<[^>]+>", "", label)).strip(), cell_text(content))
    return fields


SITE_FIELDS = {"description": "Description", "technologies": "Technologies/Practices", "conditions": "Parameters/Conditions",
               "region": "Region/Regional Conditions", "abatement": "Abatement/Control Technologies", "other_properties": "Others",
               "ipcc_1996_category": "IPCC 1996 Source/Sink Category", "ipcc_2006_category": "IPCC 2006 Source/Sink Category",
               "equation": "Equation", "ipcc_worksheet": "IPCC Worksheet", "technical_reference": "Technical Reference",
               "source_of_data": "Source of data"}


def needs_repair(r):
    return not r["description"] or not r["unit_original"] or any("?" in r[c] for c in list(SITE_FIELDS) + ["value_original", "unit_original"])


def same_but_damaged(exported, site):
    """True when the site text equals the exported text with each '?' standing for one or more characters."""
    if "?" not in exported:
        return False
    pattern = "".join(".+?" if ch == "?" else re.escape(ch) for ch in re.sub(r"\s+", " ", exported).strip())
    return re.fullmatch(pattern, re.sub(r"\s+", " ", site).strip(), flags=re.S) is not None


def repair(r, site):
    fixed = []
    for column, label in SITE_FIELDS.items():
        new = site.get(label, "")
        if new and (not r[column] and column == "description" or same_but_damaged(r[column], new)):
            r[column] = new
            fixed.append(column)
    combined = site.get("Value", "")
    value, unit = r["value_original"], r["unit_original"]
    if combined:
        if unit and "?" not in unit and combined.endswith(" " + unit):
            site_value = combined[: -len(unit) - 1]
            if site_value != value and same_but_damaged(value, site_value):
                r["value_original"] = site_value
                fixed.append("value_original")
        elif "?" not in value and combined.startswith(value + " "):
            site_unit = combined[len(value) + 1:]
            if (not unit or same_but_damaged(unit, site_unit)) and site_unit != unit:
                r["unit_original"] = site_unit
                fixed.append("unit_original")
        elif "?" in value or "?" in unit:
            whole = f"{value} {unit}".strip()
            if same_but_damaged(whole, combined):
                parts = combined.rsplit(" ", len(unit.split())) if unit else [combined]
                if unit and len(parts) == len(unit.split()) + 1:
                    r["value_original"], r["unit_original"] = parts[0], " ".join(parts[1:])
                    fixed += ["value_original", "unit_original"]
    r["fixed_from_efdb_site"] = " ".join(fixed)
    return r


def fetch_all(ids, cache_path):
    cache = json.loads(Path(cache_path).read_text(encoding="utf-8")) if Path(cache_path).is_file() else {}
    todo = [i for i in ids if i not in cache]

    def one(ef_id):
        for attempt in range(3):
            try:
                time.sleep(0.3)
                return ef_id, fetch(ef_id)
            except OSError:
                time.sleep(2 * (attempt + 1))
        return ef_id, None

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for n, (ef_id, fields) in enumerate(pool.map(one, todo), 1):
            if fields:
                cache[ef_id] = fields
            if n % 200 == 0:
                Path(cache_path).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
                print(f"fetched {n} of {len(todo)}", flush=True)
    Path(cache_path).write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def gases(value):
    return {g.strip() for g in re.split(r"[\n,]+", value or "") if g.strip()}


def norm(value):
    return re.sub(r"\s+", " ", value or "").strip().casefold()


def check(rows, sample_size):
    picked = random.Random(20261120).sample(rows, sample_size)
    results = []
    for r in picked:
        try:
            site = fetch(r["ef_id"])
        except OSError as exc:
            results.append({"ef_id": r["ef_id"], "status": "not reached", "detail": str(exc)})
            continue
        value_site = site.get("Value", "")
        same = {
            "value_and_unit": norm(value_site) == norm(f"{r['value_original']} {r['unit_original']}") or norm(value_site) == norm(r["value_original"]),
            "gas": {g.casefold() for g in gases(site.get("Gas"))} == {g.casefold() for g in gases(r["gas"])}
                   or norm(site.get("Gas")) == norm(r["gas"]),
            "description": norm(site.get("Description")) == norm(r["description"]),
            "parameter_type": norm(site.get("Type of parameter")) == norm(r["parameter_type"]),
        }
        results.append({"ef_id": r["ef_id"], "status": "equal" if all(same.values()) else "differs", "fields_equal": same,
                        "upload_value": f"{r['value_original']} {r['unit_original']}", "site_value": value_site})
        time.sleep(0.5)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upload", required=True)
    parser.add_argument("--check", type=int, default=0)
    parser.add_argument("--repair", metavar="CACHE", help="JSON cache of records fetched from the EFDB website")
    args = parser.parse_args()
    rows = read_upload(args.upload)
    if len({r["ef_id"] for r in rows}) != len(rows):
        raise SystemExit("EF IDs repeat in the upload")
    out, counts = build(rows)
    for r in out:
        r["fixed_from_efdb_site"] = ""
    if args.repair:
        damaged = [r for r in out if needs_repair(r)]
        cache = fetch_all([r["ef_id"] for r in damaged], args.repair)
        for r in damaged:
            if r["ef_id"] in cache:
                repair(r, cache[r["ef_id"]])
        counts["records_needing_repair"] = len(damaged)
        counts["records_fetched_for_repair"] = sum(r["ef_id"] in cache for r in damaged)
        counts["records_repaired"] = sum(bool(r["fixed_from_efdb_site"]) for r in damaged)
        counts["fields_repaired"] = dict(sorted(Counter(f for r in damaged for f in r["fixed_from_efdb_site"].split()).items()))
        counts["still_blank_description"] = sum(not r["description"] for r in out)
        counts["still_blank_unit"] = sum(not r["unit_original"] for r in out)
        counts["still_with_question_mark_in_value_or_unit"] = sum("?" in r["value_original"] + r["unit_original"] for r in out)
    folder = ROOT / "datasets" / DATASET
    folder.mkdir(parents=True, exist_ok=True)
    columns = COLUMNS + ["also_listed_as", "sector_2006", "geography", "value_kind", "fixed_from_efdb_site"]
    with open(folder / "data.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out)
    report_dir = ROOT / "docs/data-verification/2026-11-20"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "efdb-import-summary.json"
    report = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else {}
    report.update({"prepared": TODAY, "upload_sha256": hashlib.sha256(Path(args.upload).read_bytes()).hexdigest(), **counts})
    if args.check:
        results = check(out, args.check)
        report["spot_check"] = {"records_checked": len(results), "equal": sum(r["status"] == "equal" for r in results),
                                "differs": sum(r["status"] == "differs" for r in results),
                                "not_reached": sum(r["status"] == "not reached" for r in results), "records": results}
    report_path.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    spot = report.get("spot_check", {})
    note = (f"{spot.get('equal', 0)} of {spot.get('records_checked', 0)} records chosen at random equal the EFDB website record by record "
            f"(value and unit, gas, description, type of parameter); see docs/data-verification/2026-11-20/efdb-import-summary.json. "
            if spot else "Not compared with the EFDB website. ")
    source = {
        "id": DATASET, "table": "inventory_factors",
        "title": "IPCC Emission Factor Database (EFDB): all records, as exported on 19 November 2026",
        "publisher": "IPCC Task Force on National Greenhouse Gas Inventories (TFI), Emission Factor Database",
        "url": "https://www.ipcc-nggip.iges.or.jp/EFDB/find_ef.php",
        "license": "No licence is stated on the EFDB site. Published IPCC material (IPCC copyright); cite the EF ID and the technical reference. The EFDB says its content has not been subject to formal IPCC review.",
        "license_url": "https://www.ipcc.ch/copyright/",
        "attribution": "IPCC Emission Factor Database (EFDB), IPCC Task Force on National Greenhouse Gas Inventories, https://www.ipcc-nggip.iges.or.jp/EFDB/. Each record names its own source of data and technical reference.",
        "obtained": "User's export IPCC_EFDB_All_Emission_Factors_2026.xlsx (sheet 'EFDB All Records'), uploaded 20 November 2026; values and units kept as exported",
        "verification_status": "spot-checked against the publisher's website" if spot else "unverified",
        "verification_note": note + f"{counts['repeats_folded']} records identical to another record in every field except the EF ID are stored once (see also_listed_as). "
                             + (f"{counts['records_repaired']} records had text lost in the export (blank description or unit, or '?' for a character such as ≤ or ₂) restored from the EFDB website; the restored fields are named in fixed_from_efdb_site. " if args.repair else "")
                             + f"{counts['left_out_no_value']} records with no value are left out. Per-gas inventory parameters, not CO2e and not product footprints.",
        "file": "data.csv", "rows": len(out), "sha256": hashlib.sha256((folder / "data.csv").read_bytes()).hexdigest(), "prepared": TODAY,
    }
    (folder / "SOURCE.json").write_text(json.dumps(source, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "spot_check"} | ({"spot_check": {k: v for k, v in spot.items() if k != "records"}} if spot else {})))


if __name__ == "__main__":
    main()
