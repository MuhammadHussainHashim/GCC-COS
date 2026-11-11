import json, re
import pandas as pd

ALIASES = {
    "product_name": ["product_name","product","description","commodity","goods_description","item","name","hs_description"],
    "hs_code": ["hs_code","hscode","hs","commodity_code","cmdcode","code"],
    "sector": ["sector","industry","category","product_category"],
    "country": ["country","reporter","origin","geography","region"],
    "footprint_value": ["footprint_value","carbon_footprint","emission_factor","factor_value","co2e_value","value"],
    "impact_unit": ["impact_unit","emissions_unit","co2e_unit","unit_of_impact"],
    "functional_unit": ["functional_unit","reference_unit","denominator","per_unit","unit_basis"],
    "boundary": ["boundary","system_boundary","lifecycle_boundary","scope"],
    "data_year": ["data_year","year","reference_year","publication_year"],
    "source_name": ["source_name","source","publisher","dataset","reference"],
    "source_url": ["source_url","url","doi","link","citation_url"],
    "evidence_type": ["evidence_type","data_type","factor_type","evidence"],
    "notes": ["notes","comment","comments","methodology","description_notes"]
}

def clean_col(c):
    return re.sub(r"[^a-z0-9]+","_",str(c).strip().lower()).strip("_")

def map_columns(columns):
    clean = {clean_col(c): c for c in columns}
    mapping = {}
    for target, aliases in ALIASES.items():
        for alias in aliases:
            if alias in clean:
                mapping[target] = clean[alias]
                break
    return mapping

def read_tabular(uploaded_file):
    name = uploaded_file.name.lower()
    if name.endswith(".csv") or name.endswith(".txt"):
        return pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, dtype=str).fillna("")
    raise ValueError("Only CSV, TXT, XLSX and XLS files are supported.")

def normalize_hs(value):
    if value is None:
        return ""
    s = re.sub(r"\D", "", str(value))
    return s

def validate_hs(value):
    s = normalize_hs(value)
    if not s:
        return "missing"
    if len(s) in (2,4,6,8,10):
        return "shape_ok_review_edition"
    return "invalid_length"

def parse_float(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",","").strip())
    except (TypeError, ValueError):
        return None

def make_record(raw, mapping, imported_from):
    def val(k):
        col = mapping.get(k)
        if not col:
            return None
        v = raw.get(col, "")
        return str(v).strip() if v is not None else None
    hs = normalize_hs(val("hs_code"))
    raw_json = json.dumps({str(k): (None if pd.isna(v) else str(v)) for k,v in raw.items()},
                          ensure_ascii=False)
    value = parse_float(val("footprint_value"))
    status = "pending"
    notes = val("notes") or ""
    issues = []
    if hs and validate_hs(hs) != "shape_ok_review_edition":
        issues.append("HS code length requires review")
    if value is not None and value < 0:
        issues.append("Negative factor requires review")
    if value is not None and (not val("impact_unit") or not val("functional_unit")):
        issues.append("Factor exists but unit/basis is incomplete")
        status = "needs_unit_review"
    if not val("source_name") and not val("source_url"):
        issues.append("Source provenance missing")
        status = "needs_source"
    if issues:
        notes = (notes + " | " if notes else "") + "; ".join(issues)
    return {
        "record_type":"product_factor",
        "product_name":val("product_name"),
        "hs_code":hs,
        "sector":val("sector"),
        "country":val("country"),
        "footprint_value":value,
        "impact_unit":val("impact_unit"),
        "functional_unit":val("functional_unit"),
        "boundary":val("boundary"),
        "data_year":val("data_year"),
        "source_name":val("source_name"),
        "source_url":val("source_url"),
        "evidence_type":val("evidence_type") or "unknown",
        "review_status":status,
        "notes":notes,
        "raw_json":raw_json,
        "imported_from":imported_from
    }

def frame_for_export(records):
    return pd.DataFrame(records)
