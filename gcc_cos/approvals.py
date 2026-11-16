"""Approvals that allow a dataset to be used by a named calculation.

Nothing is approved automatically. An approval is written by a person with the
`calculator-approve` command and names who approved it, when, for which use and why.
A dataset approval means "approved for estimation": the values are still source-reported
and are not independently verified unless a record also passed human evidence review.
"""
import sqlite3

from .storage import now

USES = {"household_calculator": "GCC household carbon footprint calculator"}
LEVEL = "approved_for_estimation"


def schema(db):
    db.execute("""CREATE TABLE IF NOT EXISTS calculation_approvals(
        id INTEGER PRIMARY KEY, dataset_id TEXT NOT NULL, intended_use TEXT NOT NULL, level TEXT NOT NULL,
        approver TEXT NOT NULL, approved_at TEXT NOT NULL, note TEXT NOT NULL,
        revoked_at TEXT, revoked_by TEXT, revoke_note TEXT)""")
    db.commit()


def known_datasets(db):
    """Dataset ids that can be approved: reference datasets and record sources."""
    ids = set()
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "reference_datasets" in tables:
        ids |= {r[0] for r in db.execute("SELECT dataset_id FROM reference_datasets")}
    if "records" in tables:
        ids |= {r[0] for r in db.execute("SELECT DISTINCT json_extract(payload,'$.source_id') FROM records") if r[0]}
    return ids


def approve(db, dataset_id, intended_use, approver, note):
    if intended_use not in USES:
        raise ValueError(f"Unknown use {intended_use!r}; choose one of: {', '.join(USES)}")
    if not str(approver or "").strip() or not str(note or "").strip():
        raise ValueError("An approval needs the approver's name and a note explaining what was checked")
    if dataset_id not in known_datasets(db):
        raise ValueError(f"Unknown dataset {dataset_id!r}. Load it first; see `python -m gcc_cos reference-tables`.")
    schema(db)
    if active(db, intended_use).get(dataset_id):
        raise ValueError(f"{dataset_id} is already approved for {intended_use}")
    with db:
        cursor = db.execute("INSERT INTO calculation_approvals(dataset_id,intended_use,level,approver,approved_at,note) VALUES (?,?,?,?,?,?)",
                            (dataset_id, intended_use, LEVEL, approver.strip(), now(), note.strip()))
    return cursor.lastrowid


def revoke(db, dataset_id, intended_use, revoked_by, note):
    if not str(revoked_by or "").strip() or not str(note or "").strip():
        raise ValueError("Revoking needs a name and a note")
    schema(db)
    with db:
        changed = db.execute("UPDATE calculation_approvals SET revoked_at=?, revoked_by=?, revoke_note=? "
                             "WHERE dataset_id=? AND intended_use=? AND revoked_at IS NULL",
                             (now(), revoked_by.strip(), note.strip(), dataset_id, intended_use)).rowcount
    if not changed:
        raise ValueError(f"{dataset_id} has no active approval for {intended_use}")
    return changed


def active(db, intended_use):
    """dataset_id -> approval, for approvals not revoked. Safe on a read-only connection."""
    try:
        cursor = db.execute("SELECT id,dataset_id,intended_use,level,approver,approved_at,note FROM calculation_approvals "
                            "WHERE intended_use=? AND revoked_at IS NULL ORDER BY id", (intended_use,))
    except sqlite3.OperationalError:
        return {}
    names = [d[0] for d in cursor.description]
    return {row[1]: dict(zip(names, row)) for row in cursor}


def history(db):
    try:
        cursor = db.execute("SELECT * FROM calculation_approvals ORDER BY id")
    except sqlite3.OperationalError:
        return []
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor]
