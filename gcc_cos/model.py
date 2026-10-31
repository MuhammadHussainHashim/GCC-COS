"""Scientific checks are separate from independent verification."""
from decimal import Decimal, InvalidOperation
import re
from datetime import date
from .normalization import normalize_product

KINDS = {"verified_product_footprint", "published_generic_factor", "calculated_value",
         "unverified_estimate", "published_inventory", "published_product_footprint"}
# Only scale the numerator; never change the denominator, gas, GWP, or currency year.
UNITS = {
    "kg CO2e/kg": ("kg CO2e/kg", "1"),
    "kg CO2e/t": ("kg CO2e/kg", "0.001"),
    "t CO2e/t": ("kg CO2e/kg", "1"),
    "g CO2e/kg": ("kg CO2e/kg", "0.001"),
    "kg CO2": ("kg CO2", "1"),
    "t CO2": ("kg CO2", "1000"),
    "Mt CO2": ("kg CO2", "1000000000"),
}
FIELDS = ["product_name", "entity_type", "material", "hs6", "hs_evidence", "hs_edition",
          "original_value", "original_unit", "normalized_value", "normalized_unit",
          "geography", "year", "lifecycle_scope", "methodology", "data_kind",
          "verification_evidence", "source_url", "document_title", "license",
          "license_url", "attribution", "source_id", "document_sha256", "evidence",
          "retrieved_at", "review_status", "issues"]


PRODUCT_FIELDS = ["manufacturer", "category", "subcategory", "publication_date", "primary_source_url", "epd_id",
                  "declared_quantity", "declared_unit", "declared_unit_evidence", "verification_status",
                  "source_limitations", "lifetime_years", "product_mass_kg", "density_kg_m3", "areal_mass_kg_m2",
                  "conversion_evidence", "normalized_factors", "geography_basis", "lifecycle_module",
                  "impact_method_id", "valid_until_year", "representativeness"]
FIELDS += PRODUCT_FIELDS


def is_product(r):
    return r.get("entity_type") == "product" and r.get("data_kind") in {
        "published_product_footprint", "verified_product_footprint", "calculated_value"}


def validate(record):
    r = {k: record.get(k) for k in FIELDS}
    issues = []
    fatal = False
    try:
        value = Decimal(str(r["original_value"]))
        if not value.is_finite():
            raise InvalidOperation
        r["original_value"] = str(value)
    except (InvalidOperation, ValueError):
        value = None
        issues.append("invalid_numeric_value")
        fatal = True
    if value is not None and value < 0:
        issues.append("negative_value_requires_methodology_review")
    for field in ("product_name", "original_unit", "geography", "year", "lifecycle_scope",
                  "methodology", "source_url", "document_title", "license", "license_url", "attribution"):
        if r[field] is None or str(r[field]).strip() == "":
            issues.append("missing_" + field)
    if r["year"] is not None and not re.fullmatch(r"\d{4}", str(r["year"])):
        issues.append("invalid_year")
    if r["data_kind"] not in KINDS:
        issues.append("unknown_data_kind")
    if r["data_kind"] == "verified_product_footprint" and not r["verification_evidence"]:
        issues.append("missing_independent_verification_evidence")
    if r["hs6"] and (not re.fullmatch(r"\d{6}", str(r["hs6"])) or not r["hs_evidence"] or not r["hs_edition"]):
        issues.append("unsupported_hs_assignment")
        r["hs6"] = None
    if not r["hs6"] and r["entity_type"] != "industrial_inventory":
        issues.append("hs_manual_review")
    r["normalized_value"] = r["normalized_unit"] = None
    if value is not None:
        conversion = UNITS.get(r["original_unit"])
        if is_product(r) and r.get("declared_quantity") is not None:
            r["normalized_factors"] = normalize_product(r, value, issues)
        elif conversion:
            r["normalized_unit"], multiplier = conversion
            r["normalized_value"] = str(value * Decimal(multiplier))
        else:
            issues.append("unit_conversion_not_available")
    if r["data_kind"] == "published_inventory":
        issues.append("inventory_total_not_product_factor")
    if r["data_kind"] == "unverified_estimate":
        issues.append("unverified_estimate")
    if is_product(r):
        for field in ("manufacturer", "publication_date", "primary_source_url", "declared_quantity", "declared_unit"):
            if not r.get(field):
                issues.append("missing_" + field)
        if r.get("verification_status") != "independently_crosschecked":
            issues.append("primary_document_not_independently_crosschecked")
        if r.get("source_limitations"):
            issues.append("source_limitations_apply")
        expiry = r.get("valid_until_year")
        if expiry is not None:
            try:
                if int(expiry) < date.today().year:
                    issues.append("declaration_expired")
                elif int(expiry) == date.today().year:
                    issues.append("exact_validity_date_requires_review")
            except (ValueError, TypeError):
                issues.append("invalid_validity_year")
    r["issues"] = issues
    r["review_status"] = "rejected" if fatal else "needs_review" if issues else "checks_passed"
    return r


def classify(name, rules):
    """Only explicit exact-name mappings with a cited HS edition; no fuzzy guessing."""
    matches = [r for r in rules if r.get("name", "").casefold() == name.casefold()
               and re.fullmatch(r"\d{6}", str(r.get("hs6", "")))
               and r.get("evidence") and r.get("edition")]
    if len(matches) == 1:
        return {"hs6": matches[0]["hs6"], "hs_evidence": matches[0]["evidence"],
                "hs_edition": matches[0]["edition"]}
    return {"hs6": None, "hs_evidence": None, "hs_edition": None}
