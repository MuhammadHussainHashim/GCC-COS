"""Footprint calculator: products and quantities in, kg CO2e out, with sources.

No value is invented. A line either uses one source record, or the median of
all source records for an HS code or product type (shown with its lowest and
highest record). Lines without data are reported as missing, never filled in.
Different lifecycle scopes are totalled separately and never added together.
"""
import csv
import json
import statistics
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .hs import annotate, load_table
from .model import is_item

KINDS = ("record", "hs", "type", "activity", "electricity")
ACTIVITY_SCOPE = "Activity averages for France (ADEME Impact CO2)"
ELECTRICITY_SCOPE = "Electricity generation, country average (Our World in Data)"
FULL_LIFECYCLE = "Full lifecycle (manufacturer-reported)"
QUANTITY_UNITS = {"kg CO2e/item": "items", "kg CO2e/kg": "kg", "kg CO2e/l": "litres", "kg CO2e/m2": "m2", "kg CO2e/m3": "m3"}
MESSAGES = {
    "invalid_quantity": "Quantity must be a number greater than zero.",
    "unknown_kind": "Use record, hs, type, activity or electricity.",
    "unknown_activity": "No activity factor has this id. Run: python -m gcc_cos load-reference-data, then see the activity_factors table.",
    "unknown_country": "No electricity figure is held for this country code. Use a three-letter code such as PAK.",
    "reference_data_missing": "Reference data is not loaded. Run: python -m gcc_cos load-reference-data",
    "unknown_record": "No product record has this id.",
    "unknown_hs_code": "This is not a 2-, 4- or 6-digit code in the HS 2022 list, or an 8-digit commodity code the system holds.",
    "no_data": "No footprint record is linked to this yet.",
    "heading_only": "Records exist under this 4-digit heading but none is assigned to this 6-digit code. Use the 4-digit heading or pick a product type.",
    "mixed_units_or_scopes": "The matching records use different units or lifecycle stages, so no single value represents them. Pick one record by id.",
    "no_usable_value": "The matching records have no usable numeric value.",
}


def scope_of(row):
    if row.get("lifecycle_module"):
        return "EPD module " + str(row["lifecycle_module"])
    if row.get("data_kind") == "published_generic_factor":
        return str(row.get("lifecycle_scope") or "Scope not stated")
    return FULL_LIFECYCLE


def _value(row):
    try:
        value = Decimal(str(row.get("normalized_value")))
        return value if value.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _decimal(value):
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def use_share(row):
    """Share of the footprint from the use phase, as the source reports it (0 to 1), or None."""
    evidence = row.get("evidence")
    raw = evidence.get("raw") if isinstance(evidence, dict) else None
    share = _decimal(raw.get("gwp_use_ratio")) if isinstance(raw, dict) else None
    return share if share is not None and 0 <= share <= 1 else None


def lifetime(row):
    """Years of use the source assumed, or None."""
    years = _decimal(row.get("lifetime_years"))
    return years if years is not None and years > 0 else None


def prepare(rows):
    """Product and product-factor rows with HS columns; pass storage.records(db)."""
    rows = [r for r in rows if is_item(r)]
    return rows if all("hs_status" in r for r in rows) else annotate(rows)


def _failed(line, status, **extra):
    return {**line, "status": status, "message": MESSAGES[status], "total_kg_co2e": None, **extra}


def reference_from(db):
    """Activity factors and country electricity figures from the reference tables, for activity and electricity lines."""
    from . import refdata
    return {"activity": {r["activity_id"]: r for r in refdata.rows(db, "activity_factors")},
            "electricity": {r["iso3"]: r for r in refdata.rows(db, "country_data") if r["indicator"] == "electricity_carbon_intensity"}}


def _reference_line(line, amount, row, label, quantity_unit, scope, flags):
    per_unit = Decimal(row["value_metric"])
    total = per_unit * amount
    return {**line, "status": "ok", "message": "", "label": label, "quantity_unit": quantity_unit, "unit": row["unit_metric"], "scope": scope,
            "basis": "one published factor", "records_used": 1, "record_ids": [], "product_types": [],
            "per_unit": str(per_unit), "per_unit_lowest": str(per_unit), "per_unit_highest": str(per_unit),
            "total_kg_co2e": str(total), "use_phase_share": None, "use_phase_share_records": 0, "use_phase_kg_co2e": None,
            "making_and_other_kg_co2e": None, "lifetime_years": None, "lifetime_records": 0, "per_year_kg_co2e": None,
            "same_maker_median": None, "same_maker_records": 0, "versus_same_maker_percent": None,
            "total_lowest": str(total), "total_highest": str(total), "hs_code": None, "hs_status": None,
            "report_url": row.get("source_page") or row.get("source_url"), "flags": flags, "year": row.get("year"),
            "sources": [{"dataset": row["source_title"], "dataset_url": row["source_url"], "license": row["license"], "attribution": row["attribution"]}]}


def estimate(rows, kind, value, quantity, table=None, reference=None):
    """Work out one line. rows must come from prepare(); reference from reference_from() for activity and electricity lines."""
    line = {"kind": kind, "query": str(value).strip(), "quantity": str(quantity).strip()}
    try:
        amount = Decimal(line["quantity"])
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return _failed(line, "invalid_quantity")
    query = line["query"]
    if kind in ("activity", "electricity"):
        book = (reference or {}).get(kind)
        if not book:
            return _failed(line, "reference_data_missing")
        if kind == "activity":
            row = book.get(query)
            if row is None:
                return _failed(line, "unknown_activity")
            flags = ["average_for_france_not_local"] + (["footprint_not_verified"] if row["verification_status"] == "unverified" else [])
            return _reference_line(line, amount, row, f"{row['name_en']} ({row['area']})", row["unit_metric"].split(" per ", 1)[-1], ACTIVITY_SCOPE, flags)
        query = line["query"] = query.upper()
        row = book.get(query)
        if row is None:
            return _failed(line, "unknown_country")
        return _reference_line(line, amount, row, f"Electricity in {row['country']} ({row['year']})", "kWh", ELECTRICITY_SCOPE, ["country_average_generation_not_your_supplier"])
    if kind == "record":
        matches = [r for r in rows if str(r["id"]) == query]
        if not matches:
            return _failed(line, "unknown_record")
    elif kind == "hs":
        query = line["query"] = query.replace(".", "").replace(" ", "")
        codes = table if table is not None else load_table()[0]
        if query.isdigit() and len(query) == 8:
            # An 8-digit commodity (CN) code, as used by the CBAM default values.
            matches = [r for r in rows if str(r.get("product_name") or "").startswith(f"CN {query}:")]
            if not matches:
                return _failed(line, "unknown_hs_code")
        elif not query.isdigit() or len(query) not in (2, 4, 6) or query not in codes:
            return _failed(line, "unknown_hs_code")
        else:
            line["hs_description"] = codes[query]["description"]
            matches = [r for r in rows if (r.get("hs_code") or "").startswith(query)]
        if not matches:
            under_heading = any(r.get("hs_level") == 4 and query.startswith(r["hs_code"]) for r in rows)
            return _failed(line, "heading_only" if len(query) == 6 and under_heading else "no_data")
    elif kind == "type":
        matches = [r for r in rows if str(r.get("subcategory") or "").casefold() == query.casefold()]
        if not matches:
            return _failed(line, "no_data")
    else:
        return _failed(line, "unknown_kind")

    usable = [(r, _value(r)) for r in matches if _value(r) is not None and r.get("normalized_unit") in QUANTITY_UNITS]
    if not usable:
        return _failed(line, "no_usable_value", records_used=len(matches))
    groups = {(r["normalized_unit"], scope_of(r)) for r, _ in usable}
    if len(groups) > 1:
        return _failed(line, "mixed_units_or_scopes", records_used=len(usable),
                       record_choices=[{"id": r["id"], "product_name": r.get("product_name"), "unit": r["normalized_unit"], "scope": scope_of(r)} for r, _ in usable[:25]])
    unit, scope = next(iter(groups))
    values = [v for _, v in usable]
    per_unit, low, high = statistics.median(values), min(values), max(values)
    used = [r for r, _ in usable]
    types = sorted({str(r.get("subcategory")) for r in used if r.get("subcategory")})
    flags = []
    if any(r.get("verification_status") != "independently_crosschecked" for r in used):
        flags.append("footprint_not_verified")
    if kind == "hs" and any(r.get("hs_status") == "proposed_not_verified" for r in used):
        flags.append("hs_code_not_verified")
    if len(used) > 1:
        flags.append("median_of_several_records")
    if len(types) > 1:
        flags.append("covers_several_product_types")
    if scope.startswith("EPD module"):
        flags.append("production_stage_only_not_full_lifecycle")
    if any(r.get("data_kind") == "published_generic_factor" for r in used):
        flags.append("average_or_default_value_not_a_specific_product")
    if any(r.get("verification_status") == "transcribed_from_source_page_not_digit_checked" for r in used):
        flags.append("transcribed_not_checked_against_source")
    if any("declaration_expired" in (r.get("issues") or []) for r in used):
        flags.append("declaration_expired")
    if len(used) > 1 and low > 0 and high / low > 3:
        flags.append("wide_range")
    total = per_unit * amount
    shares = [s for s in (use_share(r) for r in used) if s is not None]
    years = [y for y in (lifetime(r) for r in used) if y is not None]
    share = statistics.median(shares) if shares and scope == FULL_LIFECYCLE else None
    life = statistics.median(years) if years and scope == FULL_LIFECYCLE else None
    extras = {"use_phase_share": str(share) if share is not None else None, "use_phase_share_records": len(shares) if share is not None else 0,
              "use_phase_kg_co2e": str(total * share) if share is not None else None,
              "making_and_other_kg_co2e": str(total * (1 - share)) if share is not None else None,
              "lifetime_years": str(life) if life is not None else None, "lifetime_records": len(years) if life is not None else 0,
              "per_year_kg_co2e": str(total / life) if life is not None else None,
              "same_maker_median": None, "same_maker_records": 0, "versus_same_maker_percent": None}
    if kind == "record":
        one = used[0]
        peers = [_value(r) for r in rows if r.get("manufacturer") == one.get("manufacturer") and r.get("subcategory") == one.get("subcategory")
                 and r.get("normalized_unit") == unit and scope_of(r) == scope and _value(r) is not None]
        if len(peers) >= 3:
            peer_median = statistics.median(peers)
            extras.update(same_maker_median=str(peer_median), same_maker_records=len(peers),
                          versus_same_maker_percent=str(((per_unit - peer_median) / peer_median * 100).quantize(Decimal("0.1"))) if peer_median > 0 else None)
    sources = []
    for r in used:
        source = {"dataset": r.get("document_title"), "dataset_url": r.get("source_url"), "license": r.get("license"), "attribution": r.get("attribution")}
        if source not in sources:
            sources.append(source)
    first = used[0]
    return {**line, "status": "ok", "message": "",
            "label": (f"{first.get('manufacturer') or ''} {first.get('product_name') or ''}".strip() if kind == "record" else ", ".join(types)),
            "quantity_unit": QUANTITY_UNITS[unit], "unit": unit, "scope": scope,
            "basis": "one source record" if len(used) == 1 else f"median of {len(used)} source records",
            "records_used": len(used), "record_ids": [r["id"] for r in used], "product_types": types,
            "per_unit": str(per_unit), "per_unit_lowest": str(low), "per_unit_highest": str(high),
            "total_kg_co2e": str(total), **extras, "total_lowest": str(low * amount), "total_highest": str(high * amount),
            "hs_code": first.get("hs_code") if len({r.get("hs_code") for r in used}) == 1 else (query if kind == "hs" else None),
            "hs_status": first.get("hs_status") if len({r.get("hs_status") for r in used}) == 1 else "mixed",
            "report_url": first.get("primary_source_url") if len(used) == 1 else None,
            "flags": flags, "sources": sources}


def calculate(rows, lines, table=None, people=None, reference=None):
    """Work out every line and total them by lifecycle scope. people (optional) adds a per-person figure."""
    rows = prepare(rows)
    codes = table if table is not None else load_table()[0]
    results = []
    for number, line in enumerate(lines, start=1):
        result = estimate(rows, line.get("kind"), line.get("value", ""), line.get("quantity", ""), codes, reference)
        results.append({"line": number, "note": line.get("note") or "", **result})
    totals = {}
    for r in results:
        if r["status"] != "ok":
            continue
        t = totals.setdefault(r["scope"], {"scope": r["scope"], "lines": 0, "total": Decimal(0), "lowest": Decimal(0), "highest": Decimal(0)})
        t["lines"] += 1
        t["total"] += Decimal(r["total_kg_co2e"])
        t["lowest"] += Decimal(r["total_lowest"])
        t["highest"] += Decimal(r["total_highest"])
    head_count = _decimal(people) if people not in (None, "") else None
    if people not in (None, "") and (head_count is None or head_count <= 0):
        raise ValueError("People must be a number greater than zero")
    summaries = []
    for t in totals.values():
        good = [r for r in results if r["status"] == "ok" and r["scope"] == t["scope"]]
        for r in good:
            r["share_of_total_percent"] = str((Decimal(r["total_kg_co2e"]) / t["total"] * 100).quantize(Decimal("0.1"))) if t["total"] > 0 else None
        biggest = max(good, key=lambda r: Decimal(r["total_kg_co2e"]))
        staged = [r for r in good if r["use_phase_kg_co2e"] is not None]
        yearly = [r for r in good if r["per_year_kg_co2e"] is not None]
        summaries.append({
            "scope": t["scope"], "lines": t["lines"], "total_kg_co2e": str(t["total"]),
            "total_lowest": str(t["lowest"]), "total_highest": str(t["highest"]),
            "biggest_line": biggest["line"], "biggest_line_share_percent": biggest["share_of_total_percent"],
            "use_phase_kg_co2e": str(sum(Decimal(r["use_phase_kg_co2e"]) for r in staged)) if len(staged) == len(good) else None,
            "making_and_other_kg_co2e": str(sum(Decimal(r["making_and_other_kg_co2e"]) for r in staged)) if len(staged) == len(good) else None,
            "per_year_kg_co2e": str(sum(Decimal(r["per_year_kg_co2e"]) for r in yearly)) if len(yearly) == len(good) else None,
            "per_person_kg_co2e": str(t["total"] / head_count) if head_count else None})
    totals = summaries
    missing = [r["line"] for r in results if r["status"] != "ok"]
    warnings = []
    if any("footprint_not_verified" in r.get("flags", []) for r in results):
        warnings.append("NOT VERIFIED: the footprints used are source-reported and have not been independently verified.")
    if any("hs_code_not_verified" in r.get("flags", []) for r in results):
        warnings.append("NOT VERIFIED: the HS code links used are proposed mappings that no customs authority has confirmed.")
    if any("median_of_several_records" in r.get("flags", []) for r in results):
        warnings.append("Some lines use the median of several products. The real footprint of a specific product can be anywhere in the lowest-to-highest range shown.")
    if missing:
        warnings.append(f"INCOMPLETE: {len(missing)} of {len(results)} lines have no value and are left out of the totals (lines {', '.join(map(str, missing))}).")
    if any("average_for_france_not_local" in r.get("flags", []) for r in results):
        warnings.append("Travel, heating and digital-use lines use averages for France. French trains and electric heating are low-carbon, so those figures are too low for most other countries.")
    if any("country_average_generation_not_your_supplier" in r.get("flags", []) for r in results):
        warnings.append("Electricity lines use the country's average for electricity generation. Losses in the grid and your own supplier's mix are not included.")
    if len(totals) > 1:
        warnings.append("Lines cover different lifecycle scopes. They are totalled separately and must not be added together.")
    if any("transcribed_not_checked_against_source" in r.get("flags", []) for r in results):
        warnings.append("NOT VERIFIED: some values were typed in from a web page and have not been checked against it digit by digit.")
    if any("average_or_default_value_not_a_specific_product" in r.get("flags", []) for r in results):
        warnings.append("Some lines use a published average or a regulatory default value, not the footprint of a specific product.")
    if any("wide_range" in r.get("flags", []) for r in results):
        warnings.append("WIDE RANGE: for some lines the highest source record is more than three times the lowest. Pick a specific product for a closer figure.")
    warnings.append("Transport of the goods (shipping) is not included.")
    return {"lines": results, "totals": totals,
            "grand_total_kg_co2e": totals[0]["total_kg_co2e"] if len(totals) == 1 else None,
            # A rough indication only: the parts are measured in different ways, which the warnings say.
            "all_parts_together_kg_co2e": str(sum(Decimal(t["total_kg_co2e"]) for t in totals)) if totals else None,
            "complete": not missing, "missing_lines": missing, "warnings": warnings}


def read_basket(path):
    """Read a CSV with a quantity column and one of record_id, hs_code or product_type per row."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {str(name or "").strip().casefold(): name for name in (reader.fieldnames or [])}
        if "quantity" not in columns or not {"record_id", "hs_code", "product_type", "activity_id", "electricity_country"} & set(columns):
            raise ValueError("The basket needs a quantity column and at least one of: record_id, hs_code, product_type, activity_id, electricity_country")
        lines = []
        for number, row in enumerate(reader, start=2):
            cell = lambda name: str(row.get(columns.get(name, ""), "") or "").strip()  # noqa: E731
            if not any(str(v or "").strip() for v in row.values()):
                continue
            filled = [(kind, cell(column)) for kind, column in (("record", "record_id"), ("hs", "hs_code"), ("type", "product_type"),
                                                                 ("activity", "activity_id"), ("electricity", "electricity_country")) if cell(column)]
            if len(filled) != 1:
                raise ValueError(f"Row {number}: fill in exactly one of record_id, hs_code, product_type, activity_id or electricity_country")
            lines.append({"kind": filled[0][0], "value": filled[0][1], "quantity": cell("quantity"), "note": cell("note")})
    if not lines:
        raise ValueError("The basket has no rows")
    return lines


LINE_COLUMNS = ["line", "note", "kind", "query", "label", "quantity", "quantity_unit", "status", "message", "per_unit", "unit",
                "per_unit_lowest", "per_unit_highest", "total_kg_co2e", "total_lowest", "total_highest", "share_of_total_percent",
                "use_phase_share", "use_phase_kg_co2e", "making_and_other_kg_co2e", "lifetime_years", "per_year_kg_co2e",
                "same_maker_median", "versus_same_maker_percent", "scope", "basis",
                "records_used", "hs_code", "hs_status", "flags", "report_url", "source_datasets", "licenses", "record_ids"]


def flat_lines(result):
    """Lines as plain rows for CSV and Excel."""
    rows = []
    for r in result["lines"]:
        row = {c: r.get(c) for c in LINE_COLUMNS}
        row["flags"] = "; ".join(r.get("flags", []))
        row["source_datasets"] = "; ".join(str(s["dataset"]) for s in r.get("sources", []))
        row["licenses"] = "; ".join(sorted({str(s["license"]) for s in r.get("sources", [])}))
        row["record_ids"] = " ".join(map(str, r.get("record_ids", [])))
        rows.append(row)
    return rows


def write_result(result, destination):
    """Save a result as .json, .csv or .xlsx."""
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    suffix = path.suffix.lower()
    if suffix == ".json":
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif suffix in {".csv", ".xlsx"}:
        import pandas as pd
        lines = pd.DataFrame(flat_lines(result), columns=LINE_COLUMNS)
        for column in [c for c in lines.columns if pd.api.types.is_object_dtype(lines[c]) or pd.api.types.is_string_dtype(lines[c])]:
            lines[column] = lines[column].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v)
        if suffix == ".csv":
            lines.to_csv(path, index=False, encoding="utf-8-sig")
        else:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                lines.to_excel(writer, index=False, sheet_name="Lines")
                pd.DataFrame(result["totals"]).to_excel(writer, index=False, sheet_name="Totals")
                pd.DataFrame({"Read this first": result["warnings"]}).to_excel(writer, index=False, sheet_name="Warnings")
    else:
        raise ValueError("Choose .json, .csv or .xlsx")
    return path
