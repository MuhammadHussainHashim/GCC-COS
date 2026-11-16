"""Cross-check the bundled data against a SECOND platform (not the file it was copied from).

    python scripts/cross_check.py --downloads FOLDER [--report docs/data-verification/second-platform.json]

FOLDER holds: hs_h6.json (UN Comtrade HS2022 reference), desnz_full.xlsx (GOV.UK full set), agb_api.json (data.ademe.fr
lines API), cbam_api_<sector>.json (GOV.UK content API), wb_EN.GHG.CO2.PC.CE.AR5.json and wb_EN.GHG.ALL.PC.CE.AR5.json
(World Bank API), openflights.dat (OpenFlights), ic_transport.json, ic_transport_<km>.json and ic_chauffage.json (ADEME Impact CO2 API).
Some second platforms publish the same publisher's data through another service, others are independent; each result says which.
"""
import argparse
import csv
import html
import json
import math
import re
import statistics
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def data(name):
    return rows(ROOT / "datasets" / name / "data.csv")


def dec(v):
    try:
        return Decimal(str(v).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def result(name, platform, kind, compared, agree, differ, notes, examples=()):
    return {"data": name, "second_platform": platform, "independence": kind, "compared": compared, "agree": agree, "differ": differ,
            "notes": notes, "examples": list(examples)[:12]}


def norm(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def hs(dl):
    ours = {r["hscode"]: r for r in rows(ROOT / "reference/hs2022/harmonized-system.csv")}
    theirs = {r["id"]: r["text"].split(" - ", 1)[-1] for r in json.loads((dl / "hs_h6.json").read_text(encoding="utf-8"))["results"] if r["id"].isdigit()}
    only_ours, only_theirs = sorted(set(ours) - set(theirs)), sorted(set(theirs) - set(ours))
    same_text = sum(1 for c in ours if c in theirs and norm(ours[c]["description"]) == norm(theirs[c]))
    diff = [f"{c}: ours '{ours[c]['description'][:60]}' / Comtrade '{theirs[c][:60]}'" for c in ours if c in theirs and norm(ours[c]["description"]) != norm(theirs[c])]
    return result("HS 2022 code list", "UN Comtrade reference list (comtradeapi.un.org, classification H6 = HS2022)", "the list's original publisher, fetched directly",
                  len(ours), len(set(ours) & set(theirs)), len(only_ours) + len(only_theirs),
                  f"Codes in both: {len(set(ours) & set(theirs))}; only in ours: {len(only_ours)}; only in Comtrade: {len(only_theirs)}. Descriptions identical for {same_text}; worded differently for {len(diff)}.",
                  [f"only in ours: {only_ours[:8]}", f"only in Comtrade: {only_theirs[:8]}"] + diff[:6])


def desnz(dl):
    import openpyxl
    book = openpyxl.load_workbook(dl / "desnz_full.xlsx", read_only=True, data_only=True)
    sheets = {}
    for ws in book.worksheets:
        values = set()
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    values.add(round(float(v), 5))
        sheets[ws.title] = values
    found = missing = no_sheet = 0
    examples = []
    for r in data("uk-desnz-conversion-factors-2026"):
        sheet = sheets.get(r["area"])
        if sheet is None:
            no_sheet += 1
            continue
        if round(float(r["value_original"]), 5) in sheet:
            found += 1
        else:
            missing += 1
            examples.append(f"{r['activity_id']} {r['name_en']} = {r['value_original']} {r['unit_original']} not on sheet '{r['area']}'")
    return result("UK conversion factors 2026 (flat file)", "GOV.UK 'full set' workbook, the same factors laid out as tables for people", "same publisher, separately published file",
                  found + missing, found, missing, f"Each flat-file value was looked for on the full-set sheet with the same name as its category. {no_sheet} rows are in a category with no sheet of that name.", examples)


def agribalyse(dl):
    api = {str(r["Code_AGB"]): r for r in json.loads((dl / "agb_api.json").read_text(encoding="utf-8"))["results"]}
    ours = data("agribalyse-3.2-synthesis")
    bad = [f"{r['product_code']}: ours {r['value_original']} / API {api.get(r['product_code'], {}).get('Changement_climatique')}" for r in ours
           if r["product_code"] not in api or dec(r["value_original"]) != dec(api[r["product_code"]]["Changement_climatique"])]
    return result("AGRIBALYSE 3.2 foods", "data.ademe.fr query API (the dataset served row by row, not the downloaded file)", "same publisher, different service",
                  len(ours), len(ours) - len(bad), len(bad), f"API returned {len(api)} foods.", bad)


def cbam(dl):
    found = {}
    for path in sorted(dl.glob("cbam_api_*.json")):
        body = json.loads(path.read_text(encoding="utf-8"))["details"]["body"]
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S):
            cells = [html.unescape(re.sub(r"<[^>]+>", " ", x)).strip() for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            if len(cells) >= 3 and re.fullmatch(r"\d{8}", cells[0].replace(" ", "")):
                m = re.search(r"-?\d+(?:\.\d+)?", cells[-1].replace(",", ""))
                found.setdefault(cells[0].replace(" ", ""), set()).add(m.group(0) if m else None)
    ours = data("uk-cbam-defaults")
    bad = [f"{r['code']}: ours {r['value_original']} / API {sorted(found.get(r['code'], []))}" for r in ours
           if len(found.get(r["code"], ())) != 1 or dec(r["value_original"]) != dec(next(iter(found[r["code"]])))]
    return result("UK CBAM default values", "GOV.UK content API (the publishing system's data feed, not the web pages)", "same publisher, different service",
                  len(ours), len(ours) - len(bad), len(bad), f"API lists {len(found)} commodity codes.", bad)


def world_bank(dl):
    out = []
    ours = data("owid-country-data")
    for indicator, code, note in (("co2_per_person", "EN.GHG.CO2.PC.CE.AR5", "World Bank: CO2 excluding land use, from EDGAR. Ours: fossil fuels and industry, from the Global Carbon Budget."),
                                  ("ghg_per_person", "EN.GHG.ALL.PC.CE.AR5", "World Bank: all greenhouse gases EXCLUDING land use, from EDGAR. Ours (Jones et al.) INCLUDES land use, so larger differences are expected, especially for forest countries.")):
        wb = {r["countryiso3code"]: r for r in json.loads((dl / f"wb_{code}.json").read_text(encoding="utf-8"))[1] if r["value"] is not None and r["countryiso3code"]}
        pairs = [(r, wb[r["iso3"]]) for r in ours if r["indicator"] == indicator and r["iso3"] in wb and float(r["value_metric"]) > 0]
        ratios = [abs(float(o["value_metric"]) - w["value"]) / max(float(o["value_metric"]), w["value"]) for o, w in pairs]
        within10, within25 = sum(1 for x in ratios if x <= 0.10), sum(1 for x in ratios if x <= 0.25)
        pak = next(((o, w) for o, w in pairs if o["iso3"] == "PAK"), None)
        far = sorted(((x, o["country"], o["value_metric"], round(w["value"], 2)) for x, (o, w) in zip(ratios, pairs)), reverse=True)[:6]
        out.append(result(f"Our World in Data: {indicator}", f"World Bank API indicator {code}", "independent estimate (different research group and method), so close agreement is expected, not equality",
                          len(pairs), within25, len(pairs) - within25,
                          f"{note} Within 10%: {within10} countries; within 25%: {within25} of {len(pairs)}; median gap {statistics.median(ratios) * 100:.1f}%. "
                          + (f"Pakistan: ours {pak[0]['value_metric']} ({pak[0]['year']}), World Bank {pak[1]['value']:.3f} ({pak[1]['date']}) t per person." if pak else ""),
                          [f"{c}: ours {a}, World Bank {b}" for _, c, a, b in far]))
    return out


def airports(dl):
    theirs = {}
    with open(dl / "openflights.dat", encoding="utf-8", newline="") as f:
        for r in csv.reader(f):
            if len(r) > 7 and r[4] not in ("", "\\N"):
                theirs[r[4]] = (float(r[6]), float(r[7]))

    def km(a, b):
        p1, p2 = math.radians(a[0]), math.radians(b[0])
        h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b[1] - a[1]) / 2) ** 2
        return 2 * 6371.0088 * math.asin(math.sqrt(h))
    ours = [r for r in data("ourairports") if r["iata_code"] in theirs]
    far = [(km((float(r["latitude_deg"]), float(r["longitude_deg"])), theirs[r["iata_code"]]), r) for r in ours]
    bad = sorted(((d, r) for d, r in far if d > 5), key=lambda x: -x[0])
    return result("Airports (coordinates)", "OpenFlights airports database (GitHub)", "separate project, though it draws partly on OurAirports, so only partly independent",
                  len(ours), len(ours) - len(bad), len(bad), f"{len(data('ourairports')) - len(ours)} of our airports have no IATA match in OpenFlights. 'Differ' means the two positions are more than 5 km apart, usually an airport that moved or a reused code.",
                  [f"{r['iata_code']} {r['name']}: {d:,.0f} km apart" for d, r in bad])


def ademe(dl):
    api = []  # the API reports the total for the distance asked for, so divide by that distance (file name ic_transport_<km>.json; 1 km if none)
    for path in sorted(dl.glob("ic_transport*.json")):
        distance = float(re.search(r"_(\d+)\.json$", path.name).group(1)) if re.search(r"_(\d+)\.json$", path.name) else 1.0
        api += [float(x["value"]) / distance for x in json.loads(path.read_text(encoding="utf-8"))["data"]]
    heat = [float(x["ecv"]) for x in json.loads((dl / "ic_chauffage.json").read_text(encoding="utf-8"))["data"]]
    out = []
    for area, values, label in (("Transport", api, "transport, kg CO2e per km"), ("Home heating", heat, "heating, kg CO2e per m2 per year")):
        ours = [r for r in data("ademe-activity-factors") if r["area"] == area]
        ok = [r for r in ours if any(abs(float(r["value_metric"]) - v) <= max(abs(v), 1e-9) * 1e-6 for v in values)]
        out.append(result(f"ADEME activity factors: {area}", f"ADEME Impact CO2 live API (impactco2.fr/api/v1, {label})", "same publisher, live service instead of the source-code file",
                          len(ours), len(ok), len(ours) - len(ok), "A row agrees when the live API returns the same value for some mode. The live site may have been updated since the recorded file version.",
                          [f"{r['activity_id']} {r['name_en']}: ours {r['value_metric']}" for r in ours if r not in ok]))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--downloads", required=True)
    parser.add_argument("--report")
    args = parser.parse_args(argv)
    dl = Path(args.downloads)
    out = [hs(dl), desnz(dl), agribalyse(dl), cbam(dl)] + world_bank(dl) + [airports(dl)] + ademe(dl)
    for r in out:
        print(f"{r['data']}  <->  {r['second_platform']}\n    compared {r['compared']:,}; agree {r['agree']:,}; differ {r['differ']:,}. {r['notes']}")
        for e in r["examples"]:
            print("      - " + e)
    if args.report:
        Path(args.report).write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
