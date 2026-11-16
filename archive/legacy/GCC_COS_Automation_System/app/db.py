import sqlite3
from pathlib import Path
from datetime import datetime, timezone
import json

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "cos.db"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_type TEXT NOT NULL DEFAULT 'product_factor',
            product_name TEXT,
            hs_code TEXT,
            sector TEXT,
            country TEXT,
            footprint_value REAL,
            impact_unit TEXT,
            functional_unit TEXT,
            boundary TEXT,
            data_year TEXT,
            source_name TEXT,
            source_url TEXT,
            evidence_type TEXT,
            review_status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            raw_json TEXT,
            imported_from TEXT,
            imported_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_records_hs ON records(hs_code);
        CREATE INDEX IF NOT EXISTS idx_records_status ON records(review_status);
        CREATE INDEX IF NOT EXISTS idx_records_name ON records(product_name);
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source_type TEXT,
            url TEXT,
            licence_notes TEXT,
            coverage_notes TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        );
        """)
        count = con.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        if count == 0:
            defaults = [
                ("UN Comtrade", "API", "https://uncomtrade.org/docs/un-comtrade-api/",
                 "Check current API terms and rate limits", "Trade data by commodity/HS classification; not a carbon factor"),
                ("UK Government GHG Conversion Factors 2026", "download",
                 "https://www.gov.uk/government/publications/greenhouse-gas-reporting-conversion-factors-2026",
                 "Review publication terms and applicability", "Activity-based factors; geography and boundary matter"),
                ("Verra VM0044 v1.2", "methodology",
                 "https://verra.org/methodologies/vm0044-biochar-utilization-in-soil-and-non-soil-applications-v1-2/",
                 "Follow methodology terms", "Biochar project methodology; not a generic product-factor table"),
                ("WCO Harmonized System", "classification",
                 "https://www.wcoomd.org/",
                 "Check access/licensing and edition", "HS nomenclature; verify national tariff extensions")
            ]
            now = datetime.now(timezone.utc).isoformat()
            con.executemany("""INSERT INTO sources
                (name,source_type,url,licence_notes,coverage_notes,created_at)
                VALUES (?,?,?,?,?,?)""", [x + (now,) for x in defaults])

def log_action(record_id, action, details=""):
    with connect() as con:
        con.execute("INSERT INTO audit_log(record_id,action,details,created_at) VALUES(?,?,?,?)",
                    (record_id, action, details, datetime.now(timezone.utc).isoformat()))

def get_sources():
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM sources ORDER BY name").fetchall()]

def add_source(name, source_type, url, licence_notes, coverage_notes):
    with connect() as con:
        con.execute("""INSERT INTO sources(name,source_type,url,licence_notes,coverage_notes,created_at)
                       VALUES(?,?,?,?,?,?)""",
                    (name, source_type, url, licence_notes, coverage_notes,
                     datetime.now(timezone.utc).isoformat()))

def insert_record(row):
    now = datetime.now(timezone.utc).isoformat()
    keys = ["record_type","product_name","hs_code","sector","country","footprint_value",
            "impact_unit","functional_unit","boundary","data_year","source_name","source_url",
            "evidence_type","review_status","notes","raw_json","imported_from"]
    values = [row.get(k) for k in keys]
    with connect() as con:
        cur = con.execute(f"""INSERT INTO records ({','.join(keys)},imported_at,updated_at)
            VALUES ({','.join(['?']*(len(keys)+2))})""",
            values + [now, now])
        rid = cur.lastrowid
        con.execute("INSERT INTO audit_log(record_id,action,details,created_at) VALUES(?,?,?,?)",
                    (rid, "import", "Imported record; default status pending", now))
        return rid

def query_records(search="", status="All", limit=2000):
    sql = "SELECT * FROM records WHERE 1=1"
    params = []
    if search.strip():
        like = f"%{search.strip()}%"
        sql += " AND (product_name LIKE ? OR hs_code LIKE ? OR source_name LIKE ? OR sector LIKE ?)"
        params += [like, like, like, like]
    if status != "All":
        sql += " AND review_status = ?"
        params.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(int(limit))
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]

def update_status(record_id, status, note=""):
    now = datetime.now(timezone.utc).isoformat()
    with connect() as con:
        con.execute("UPDATE records SET review_status=?, notes=COALESCE(notes,'') || ?, updated_at=? WHERE id=?",
                    (status, ("\nReview: " + note if note else ""), now, int(record_id)))
        con.execute("INSERT INTO audit_log(record_id,action,details,created_at) VALUES(?,?,?,?)",
                    (int(record_id), "status_change", f"Status={status}; {note}", now))

def get_stats():
    with connect() as con:
        total = con.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        pending = con.execute("SELECT COUNT(*) FROM records WHERE review_status='pending'").fetchone()[0]
        approved = con.execute("SELECT COUNT(*) FROM records WHERE review_status='approved'").fetchone()[0]
        hs = con.execute("SELECT COUNT(*) FROM records WHERE hs_code IS NOT NULL AND TRIM(hs_code)<>''").fetchone()[0]
        factors = con.execute("SELECT COUNT(*) FROM records WHERE footprint_value IS NOT NULL").fetchone()[0]
        return {"total":total,"pending":pending,"approved":approved,"hs":hs,"factors":factors}

def audit_rows(limit=1000):
    with connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (int(limit),)).fetchall()]
