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
from .model import is_product

KINDS = ("record", "hs", "type")
FULL_LIFECYCLE = "Full lifecycle (manufacturer-reported)"
QUANTITY_UNITS = {"kg CO2e/item": "items", "kg CO2e/kg": "kg", "kg CO2e/m2": "m2", "kg CO2e/m3": "m3"}
MESSAGES = {
    "invalid_quantity": "Quantity must be a number greater than zero.",
    "unknown_kind": "Use record, hs or type.",
    "unknown_record": "No product record has this id.",
    "unknown_hs_code": "This is not a 2-, 4- or 6-digit code in the HS 2022 list.",
    "no_data": "No footprint record is linked to this yet.",
    "heading_only": "Records exist under this 4-digit heading but none is assigned to this 6-digit code. Use the 4-digit heading or pick a product type.",
    "mixed_units_or_scopes": "The matching records use different units or lifecycle stages, so no single value represents them. Pick one record by id.",
    "no_usable_value": "The matching records have no usable numeric value.",
}


def scope_of(row):
    return ("EPD module " + str(row["lifecycle_module"])) if row.get("lifecycle_module") else FULL_LIFECYCLE


def _value(row):
    try:
        value = Decimal(str(row.get("normalized_value")))
        return value if value.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def prepare(rows):
    """Product rows with HS columns; pass storage.records(db)."""
    rows = [r for r in rows if is_product(r)]
    return rows if all("hs_status" in r for r in rows) else annotate(rows)


def _failed(line, status, **extra):
    return {**line, "status": status, "message": MESSAGES[status], "total_kg_co2e": None, **extra}


def estimate(rows, kind, value, quantity, table=None):
    """Work out one line. rows must come from prepare()."""
    line = {"kind": kind, "query": str(value).strip(), "quantity": str(quantity).strip()}
    try:
        amount = Decimal(line["quantity"])
        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        return _failed(line, "invalid_quantity")
    query = line["query"]
    if kind == "record":
        matches = [r for r in rows if str(r["id"]) == query]
        if not matches:
            return _failed(line, "unknown_record")
    elif kind == "hs":
        query = line["query"] = query.replace(".", "").replace(" ", "")
        codes = table if table is not None else load_table()[0]
        if not query.isdigit() or len(query) not in (2, 4, 6) or query not in codes:
            return _failed(line, "unknown_hs_code")
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
    if scope != FULL_LIFECYCLE:
        flags.append("production_stage_only_not_full_lifecycle")
    if any("declaration_expired" in (r.get("issues") or []) for r in used):
        flags.append("declaration_expired")
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
            "total_kg_co2e": str(per_unit * amount), "total_lowest": str(low * amount), "total_highest": str(high * amount),
            "hs_code": first.get("hs_code") if len({r.get("hs_code") for r in used}) == 1 else (query if kind == "hs" else None),
            "hs_status": first.get("hs_status") if len({r.get("hs_status") for r in used}) == 1 else "mixed",
            "report_url": first.get("primary_source_url") if len(used) == 1 else None,
            "flags": flags, "sources": sources}


def calculate(rows, lines, table=None):
    """Work out every line and total them by lifecycle scope."""
    rows = prepare(rows)
    codes = table if table is not None else load_table()[0]
    results = []
    for number, line in enumerate(lines, start=1):
        result = estimate(rows, line.get("kind"), line.get("value", ""), line.get("quantity", ""), codes)
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
    totals = [{"scope": t["scope"], "lines": t["lines"], "total_kg_co2e": str(t["total"]),
               "total_lowest": str(t["lowest"]), "total_highest": str(t["highest"])} for t in totals.values()]
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
    if len(totals) > 1:
        warnings.append("Lines cover different lifecycle scopes. They are totalled separately and must not be added together.")
    warnings.append("Transport of the goods (shipping) is not included.")
    return {"lines": results, "totals": totals,
            "grand_total_kg_co2e": totals[0]["total_kg_co2e"] if len(totals) == 1 else None,
            "complete": not missing, "missing_lines": missing, "warnings": warnings}


def read_basket(path):
    """Read a CSV with a quantity column and one of record_id, hs_code or product_type per row."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = {str(name or "").strip().casefold(): name for name in (reader.fieldnames or [])}
        if "quantity" not in columns or not {"record_id", "hs_code", "product_type"} & set(columns):
            raise ValueError("The basket needs a quantity column and at least one of: record_id, hs_code, product_type")
        lines = []
        for number, row in enumerate(reader, start=2):
            cell = lambda name: str(row.get(columns.get(name, ""), "") or "").strip()  # noqa: E731
            if not any(str(v or "").strip() for v in row.values()):
                continue
            filled = [(kind, cell(column)) for kind, column in (("record", "record_id"), ("hs", "hs_code"), ("type", "product_type")) if cell(column)]
            if len(filled) != 1:
                raise ValueError(f"Row {number}: fill in exactly one of record_id, hs_code or product_type")
            lines.append({"kind": filled[0][0], "value": filled[0][1], "quantity": cell("quantity"), "note": cell("note")})
    if not lines:
        raise ValueError("The basket has no rows")
    return lines


LINE_COLUMNS = ["line", "note", "kind", "query", "label", "quantity", "quantity_unit", "status", "message", "per_unit", "unit",
                "per_unit_lowest", "per_unit_highest", "total_kg_co2e", "total_lowest", "total_highest", "scope", "basis",
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
