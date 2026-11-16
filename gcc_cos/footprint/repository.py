"""Read-only access to the GCC SQLite database for the calculator.

The connection is opened with SQLite's read-only mode, so the calculator and its API can
never change records, reviews, validation history or provenance.
"""
import json
import math
import sqlite3
from pathlib import Path

from .. import approvals

PRODUCT_KINDS = {"published_product_footprint", "verified_product_footprint"}


def connect_read_only(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, check_same_thread=False)
    db.row_factory = sqlite3.Row
    return db


class Repository:
    """Look-ups the calculator needs. Every method only reads."""

    def __init__(self, db, use="household_calculator"):
        self.db = db
        self.use = use
        self.tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

    # ---- helpers -------------------------------------------------------------------------
    def _rows(self, sql, *args):
        return [dict(r) for r in self.db.execute(sql, args)]

    def has(self, table):
        return table in self.tables

    def datasets(self):
        return {r["dataset_id"]: r for r in self._rows("SELECT * FROM reference_datasets")} if self.has("reference_datasets") else {}

    def approvals(self):
        return approvals.active(self.db, self.use)

    def dataset_places(self, table, dataset_id):
        """Distinct (geography, year) pairs a factor dataset covers."""
        if table not in ("activity_factors", "product_averages") or not self.has(table):
            return []
        return [(r["geography"], r["year"]) for r in self._rows(f"SELECT DISTINCT geography, year FROM {table} WHERE dataset_id=?", dataset_id)]

    # ---- factors -------------------------------------------------------------------------
    def activity_factors(self, dataset_id, area, name, unit_original, scope):
        """All rows that match the selector exactly. More than one row is a duplicate and is reported, not guessed."""
        if not self.has("activity_factors"):
            return []
        return self._rows("SELECT * FROM activity_factors WHERE dataset_id=? AND area=? AND name_en=? AND unit_original=? AND note=?",
                          dataset_id, area, name, unit_original, scope)

    def activity_candidates(self, area, name):
        """Rows with the same section and name in any unit or scope, to explain a mismatch."""
        if not self.has("activity_factors"):
            return []
        return self._rows("SELECT activity_id,dataset_id,unit_original,note,geography,year FROM activity_factors WHERE area=? AND name_en=?", area, name)

    def electricity(self, iso3):
        if not self.has("country_data"):
            return []
        return self._rows("SELECT * FROM country_data WHERE indicator='electricity_carbon_intensity' AND iso3=?", iso3)

    def countries(self):
        if not self.has("country_data"):
            return []
        rows = self._rows("SELECT iso3,country,indicator,year,value_original,unit_original FROM country_data ORDER BY country")
        out = {}
        for r in rows:
            entry = out.setdefault(r["iso3"], {"iso3": r["iso3"], "name": r["country"], "electricity_year": None, "ghg_per_person": None})
            if r["indicator"] == "electricity_carbon_intensity":
                entry["electricity_year"] = r["year"]
            if r["indicator"] == "ghg_per_person":
                entry["ghg_per_person"] = {"value": r["value_original"], "unit": r["unit_original"], "year": r["year"]}
        return sorted(out.values(), key=lambda c: c["name"])

    def country_ghg(self, iso3):
        if not self.has("country_data"):
            return None
        rows = self._rows("SELECT * FROM country_data WHERE indicator='ghg_per_person' AND iso3=?", iso3)
        return rows[0] if len(rows) == 1 else None

    def food(self, code):
        if not self.has("product_averages"):
            return []
        return self._rows("SELECT * FROM product_averages WHERE product_code=?", code)

    def search_foods(self, query, limit=30):
        if not self.has("product_averages"):
            return []
        words = [w for w in str(query or "").lower().split() if w][:6]
        sql = "SELECT product_code,name_en,name_original,group_original,subgroup_original,value_metric,unit_metric,data_quality_rating,dataset_id FROM product_averages"
        args = []
        if words:
            sql += " WHERE " + " AND ".join("(lower(name_en) LIKE ? OR lower(name_original) LIKE ?)" for _ in words)
            for w in words:
                args += [f"%{w}%", f"%{w}%"]
        sql += " ORDER BY name_en LIMIT ?"
        return self._rows(sql, *args, int(limit))

    def foods_in_subgroup(self, subgroup):
        if not self.has("product_averages") or not subgroup:
            return []
        return self._rows("SELECT product_code,name_en,value_metric FROM product_averages WHERE subgroup_original=?", subgroup)

    # ---- products ------------------------------------------------------------------------
    def _products(self):
        if not self.has("records"):
            return []
        out = []
        for rid, payload in self.db.execute("SELECT id,payload FROM records ORDER BY id"):
            r = json.loads(payload)
            if r.get("entity_type") == "product" and r.get("data_kind") in PRODUCT_KINDS and r.get("manufacturer"):
                out.append({"id": rid, **r})
        return out

    def search_products(self, query, limit=30):
        words = [w for w in str(query or "").lower().split() if w][:6]
        hits = []
        for r in self._products():
            text = " ".join(str(r.get(k) or "") for k in ("manufacturer", "product_name", "subcategory")).lower()
            if all(w in text for w in words):
                hits.append(r)
            if len(hits) >= int(limit):
                break
        return hits

    def product(self, record_id):
        return [r for r in self._products() if r["id"] == record_id]

    def verified_record_ids(self):
        """Records that passed the existing human evidence review and are still eligible."""
        if not {"human_decisions", "review_packets", "reviewers"} <= self.tables:
            return set()
        try:
            from ..verification import verified_rows
            return {r["id"] for r in verified_rows(self.db)}
        except sqlite3.OperationalError:
            return set()

    # ---- airports ------------------------------------------------------------------------
    def airport(self, iata):
        if not self.has("airports"):
            return []
        return self._rows("SELECT ident,iata_code,name,municipality,iso_country,latitude_deg,longitude_deg FROM airports WHERE iata_code=?", str(iata).upper())

    def search_airports(self, query, limit=20):
        if not self.has("airports"):
            return []
        q = f"%{str(query or '').lower()}%"
        return self._rows("SELECT iata_code,name,municipality,iso_country FROM airports WHERE lower(iata_code) LIKE ? OR lower(name) LIKE ? OR lower(municipality) LIKE ? "
                          "ORDER BY CASE WHEN lower(iata_code)=? THEN 0 ELSE 1 END, type, name LIMIT ?", q, q, q, str(query or "").lower(), int(limit))


EARTH_RADIUS_KM = 6371.0088  # mean Earth radius (IUGG); used only to compute a great-circle distance between two airports


def great_circle_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (float(a["latitude_deg"]), float(a["longitude_deg"]), float(b["latitude_deg"]), float(b["longitude_deg"])))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
