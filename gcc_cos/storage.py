import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from .model import PRODUCT_FIELDS, validate


def now():
    return datetime.now(timezone.utc).isoformat()


def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript('''
    CREATE TABLE IF NOT EXISTS records(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS documents(sha256 TEXT, source_id TEXT, url TEXT, title TEXT,
      retrieved_at TEXT, local_path TEXT, extracted_text TEXT, PRIMARY KEY(sha256,source_id));
    CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY, source_id TEXT, started_at TEXT,
      status TEXT, inserted INTEGER, duplicates INTEGER, detail TEXT);
    CREATE TABLE IF NOT EXISTS validation_history(id INTEGER PRIMARY KEY, record_id INTEGER REFERENCES records(id),
      checked_at TEXT, validator_version TEXT, previous_results TEXT, current_results TEXT);
    CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY, record_id INTEGER REFERENCES records(id),
      reviewed_at TEXT, reviewer TEXT, decision TEXT, note TEXT);
    ''')
    columns = {row[1] for row in db.execute('PRAGMA table_info(runs)')}
    for name, kind in [('error_code','TEXT'), ('http_status','INTEGER'), ('next_action','TEXT')]:
        if name not in columns:
            db.execute('ALTER TABLE runs ADD COLUMN ' + name + ' ' + kind)
    db.commit()
    from .verification import schema
    schema(db)
    return db


def insert(db, record):
    identity = {k: v for k, v in record.items() if k not in
                {"retrieved_at", "issues", "review_status", "normalized_value", "normalized_unit", "normalized_factors"}
                and not (k in PRODUCT_FIELDS and v is None)}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    cur = db.execute("INSERT OR IGNORE INTO records(fingerprint,payload) VALUES (?,?)",
                     (fingerprint, json.dumps(record, ensure_ascii=False)))
    return cur.rowcount


def records(db):
    return [{"id": i, **json.loads(p)} for i, p in db.execute("SELECT id,payload FROM records ORDER BY id")]


def review(db, record_id, reviewer, decision, note):
    if decision not in {"accepted", "rejected"} or not reviewer.strip() or not note.strip():
        raise ValueError("Reviewer, decision (accepted/rejected) and evidence note are required")
    row = db.execute("SELECT payload FROM records WHERE id=?", (record_id,)).fetchone()
    if row is None:
        raise ValueError("Record not found")
    r = json.loads(row[0])
    if decision == "accepted" and (r["review_status"] == "rejected" or "invalid_numeric_value" in r.get("issues", [])):
        raise ValueError("Invalid numeric data cannot be accepted; correct and reingest the source")
    r["review_status"] = "manually_" + decision
    with db:
        db.execute("UPDATE records SET payload=? WHERE id=?", (json.dumps(r), record_id))
        db.execute("INSERT INTO reviews(record_id,reviewed_at,reviewer,decision,note) VALUES (?,?,?,?,?)",
                   (record_id, now(), reviewer, decision, note))


def revalidate(db):
    """Refresh derived checks without changing source evidence or losing prior review audit."""
    fields = ('normalized_value', 'normalized_unit', 'normalized_factors', 'issues', 'review_status')
    changed = 0
    rows = records(db)
    with db:
        for old in rows:
            fresh = validate(old)
            before = {k: old.get(k) for k in fields}
            after = {k: fresh.get(k) for k in fields}
            derived_equal = all(before[k] == after[k] for k in fields if k != 'review_status')
            if derived_equal and old['review_status'] in {'manually_accepted', 'manually_rejected'}:
                fresh['review_status'] = old['review_status']
                after['review_status'] = old['review_status']
            if before == after:
                continue
            db.execute('UPDATE records SET payload=? WHERE id=?', (json.dumps(fresh), old['id']))
            db.execute('INSERT INTO validation_history(record_id,checked_at,validator_version,previous_results,current_results) VALUES (?,?,?,?,?)',
                       (old['id'], now(), '0.3', json.dumps(before), json.dumps(after)))
            changed += 1
    return {'checked': len(rows), 'changed': changed}
