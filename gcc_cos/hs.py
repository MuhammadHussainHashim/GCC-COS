"""HS code layer: an official code list plus human-readable, cited product-type mappings.

Nothing here invents a code. A mapping may only use a code that exists in the
bundled HS 2022 list, descriptions are always read from that list, and every
mapping carries a status so unverified ones can be highlighted and replaced.
"""
import csv
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / "reference" / "hs2022"
MAPPINGS = ROOT / "config" / "hs_mappings.json"
STATUSES = {"proposed_not_verified", "verified", "unmapped"}
HS_COLUMNS = ["hs_code", "hs_level", "hs_heading", "hs_description", "hs_status", "hs_basis",
              "hs_reference_edition", "hs_reference_source"]
LABELS = {
    "verified": "Verified",
    "exact_rule": "Code given by the source",
    "proposed_not_verified": "NOT VERIFIED - proposed mapping",
    "unmapped": "No HS code",
}


def load_table(folder=REFERENCE):
    """Return (codes, source). Refuses a code list whose bytes differ from the recorded checksum."""
    folder = Path(folder)
    source = json.loads((folder / "SOURCE.json").read_text(encoding="utf-8"))
    raw = (folder / source["file"]).read_bytes()
    if hashlib.sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError("HS code list does not match its recorded checksum; restore the original file")
    codes = {}
    for row in csv.DictReader(raw.decode("utf-8").splitlines()):
        if row["hscode"].isdigit():
            codes[row["hscode"]] = {"code": row["hscode"], "description": row["description"],
                                    "level": len(row["hscode"]), "parent": row["parent"], "section": row["section"]}
    return codes, source


def load_mappings(path=MAPPINGS, table=None):
    """Read and check the mapping file. A bad entry stops the program instead of being skipped."""
    codes = table if table is not None else load_table()[0]
    entries = json.loads(Path(path).read_text(encoding="utf-8"))
    seen = set()
    for entry in entries:
        match, code, status = entry.get("match") or {}, entry.get("hs_code"), entry.get("status")
        if set(match) not in ({"category", "subcategory"}, {"product_name"}) or not all(isinstance(v, str) and v.strip() for v in match.values()):
            raise ValueError(f"HS mapping must match a category and subcategory, or an exact product name: {entry}")
        key = tuple(sorted((k, v.casefold()) for k, v in match.items()))
        if key in seen:
            raise ValueError(f"Duplicate HS mapping: {match}")
        seen.add(key)
        if status not in STATUSES or not str(entry.get("basis") or "").strip():
            raise ValueError(f"HS mapping needs a known status and a written basis: {match}")
        if status == "unmapped":
            if code is not None:
                raise ValueError(f"An unmapped entry cannot carry a code: {match}")
            continue
        if not isinstance(code, str) or not re.fullmatch(r"\d{4}|\d{6}", code) or code not in codes:
            raise ValueError(f"HS code {code!r} is not a 4- or 6-digit code in the bundled HS 2022 list: {match}")
        if status == "verified" and not (str(entry.get("verified_by") or "").strip() and str(entry.get("verification_evidence") or "").strip()):
            raise ValueError(f"A verified HS mapping needs verified_by and verification_evidence: {match}")
    return entries


def _find(record, mappings):
    name = str(record.get("product_name") or "").casefold()
    pair = (str(record.get("category") or "").casefold(), str(record.get("subcategory") or "").casefold())
    by_name = [m for m in mappings if "product_name" in m["match"] and m["match"]["product_name"].casefold() == name]
    if by_name:
        return by_name[0]
    by_type = [m for m in mappings if "category" in m["match"]
               and (m["match"]["category"].casefold(), m["match"]["subcategory"].casefold()) == pair]
    return by_type[0] if by_type else None


def classify(record, mappings, table, source):
    """HS fields for one record. The stored record is never changed."""
    blank = dict.fromkeys(HS_COLUMNS)
    blank.update(hs_status="unmapped", hs_reference_edition=source["edition"], hs_reference_source=source["url"])
    if record.get("entity_type") == "industrial_inventory" or record.get("data_kind") == "published_inventory":
        return {**blank, "hs_basis": "National inventory total; no product HS code applies."}
    if record.get("hs6") and record.get("hs_evidence") and record.get("hs_edition"):
        code, status, basis = str(record["hs6"]), "exact_rule", str(record["hs_evidence"])
    else:
        mapping = _find(record, mappings)
        if mapping is None:
            return {**blank, "hs_basis": "No mapping has been written for this product type."}
        if mapping["status"] == "unmapped":
            return {**blank, "hs_basis": mapping["basis"]}
        code, status, basis = mapping["hs_code"], mapping["status"], mapping["basis"]
    return {**blank, "hs_code": code, "hs_level": len(code), "hs_heading": code[:4],
            "hs_description": (table.get(code) or {}).get("description"), "hs_status": status, "hs_basis": basis}


def annotate(rows, mappings=None, table=None, source=None):
    """Copy rows and add the HS columns."""
    if table is None or source is None:
        table, source = load_table()
    if mappings is None:
        mappings = load_mappings(table=table)
    return [{**row, **classify(row, mappings, table, source)} for row in rows]


def matches(row, query):
    """True when an annotated row answers an HS query (2, 4 or 6 digits)."""
    code = row.get("hs_code") or ""
    return bool(code) and code.startswith(query)


def heading_only(row, query):
    """True when a 6-digit query falls under a row that is mapped only to its 4-digit heading."""
    return len(query) == 6 and row.get("hs_level") == 4 and query.startswith(row["hs_code"])


def lookup(query, table, limit=50):
    """Find codes by number prefix or by words in the description."""
    text = str(query or "").strip()
    if not text:
        return []
    if text.replace(".", "").isdigit():
        prefix = text.replace(".", "")
        found = [c for c in table.values() if c["code"].startswith(prefix)]
    else:
        words = text.casefold().split()
        found = [c for c in table.values() if all(w in c["description"].casefold() for w in words)]
    return sorted(found, key=lambda c: (c["code"]))[:limit]


def coverage(rows):
    """Count annotated product rows by HS status and by code."""
    by_status, by_code = {}, {}
    for row in rows:
        by_status[row["hs_status"]] = by_status.get(row["hs_status"], 0) + 1
        if row.get("hs_code"):
            item = by_code.setdefault(row["hs_code"], {"hs_code": row["hs_code"], "hs_level": row["hs_level"],
                                                        "hs_description": row["hs_description"],
                                                        "hs_status": row["hs_status"], "records": 0})
            item["records"] += 1
    return {"records": len(rows), "by_status": by_status,
            "codes": sorted(by_code.values(), key=lambda c: c["hs_code"])}
