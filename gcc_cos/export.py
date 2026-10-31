import json
from pathlib import Path
import pandas as pd
from .model import FIELDS
from .storage import records
from .query import select


APPROVAL_COLUMNS = ['human_approval_id','human_reviewer','human_verified_at','approval_explanation','primary_evidence_sha256','human_review_status','primary_evidence_url','primary_document_license','primary_document_license_url','primary_document_title','primary_document_date','primary_declared_expiry','verification_scope']


def selected_rows(db, verified_only=False, **filters):
    if verified_only:
        from .verification import verified_rows
        return select(verified_rows(db), **filters)
    return select(records(db), **filters)


def frame(db, verified_only=False, **filters):
    rows = selected_rows(db, verified_only=verified_only, **filters)
    for row in rows:
        for key, value in row.items():
            if isinstance(value, (dict, list)):
                row[key] = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, str) and value.startswith(("=", "+", "-", "@", "\t", "\r")):
                # Avoid spreadsheet formula injection in text cells.
                row[key] = "'" + value
    return pd.DataFrame(rows, columns=["id"] + FIELDS + (APPROVAL_COLUMNS if verified_only else []))


def export(db, destination, **filters):
    path = Path(destination)
    origin = db.execute('PRAGMA database_list').fetchone()[2]
    if origin and Path(origin).resolve() == path.resolve():
        raise ValueError('Cannot overwrite the active database')
    path.parent.mkdir(parents=True, exist_ok=True)
    df = frame(db, **filters)
    if path.suffix.lower() == ".csv":
        df.to_csv(path, index=False, encoding="utf-8-sig")
    elif path.suffix.lower() == ".xlsx":
        path.write_bytes(excel_bytes(db, **filters))
    elif path.suffix.lower() in {".sqlite", ".db"}:
        sqlite_export(db, path, **filters)
    else:
        raise ValueError("Choose .csv, .xlsx or .sqlite")
    return len(df)


def excel_bytes(db, verified_only=False, **filters):
    import io
    df = frame(db, verified_only=verified_only, **filters)
    if any(isinstance(v, str) and len(v) > 32767 for v in df.to_numpy().flat):
        raise ValueError("Evidence exceeds Excel cell limit; export CSV instead")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Records")
        columns = ["source_id", "source_url", "document_title", "license", "license_url", "attribution"]
        df[columns].drop_duplicates().to_excel(writer, index=False, sheet_name="Sources and licenses")
        pd.DataFrame({"Notice": [
            "Boavizta-derived database contents: ODbL 1.0; individual contents: DbCL 1.0. Attribution and share-alike obligations apply to the derived database.",
            "https://opendatacommons.org/licenses/odbl/1-0/ ; https://opendatacommons.org/licenses/dbcl/1-0/",
            "Independent EPD datasets retain their embedded per-document terms; no manufacturer PDF redistribution permission is asserted.",
            "GCC-COS quality checks are not independent footprint verification. Review issues, scopes and source limitations before use.",
            "Boavizta warns against precise impact assessments and comparisons across manufacturers."]}).to_excel(writer, index=False, sheet_name="License notices")
        for table, sheet in (("runs", "Ingestion runs"), ("reviews", "Review audit"), ("validation_history", "Validation audit")):
            audit = pd.read_sql_query("SELECT * FROM " + table, db)
            if verified_only:
                if table == 'runs': audit = audit[audit['source_id'].isin(set(df['source_id']))]
                else: audit = audit[audit['record_id'].isin(set(df['id']))]
            for column in audit.select_dtypes(include="object"):
                audit[column] = audit[column].map(lambda v: "'" + v if isinstance(v, str) and v.startswith(("=", "+", "-", "@", "\t", "\r")) else v)
            if any(isinstance(v, str) and len(v) > 32767 for v in audit.to_numpy().flat):
                raise ValueError("Audit note exceeds Excel cell limit; inspect SQLite instead")
            audit.to_excel(writer, index=False, sheet_name=sheet)
    return buffer.getvalue()


def sqlite_export(db, path, **filters):
    """A consistent standalone SQLite backup, optionally narrowed to selected records."""
    import os
    import sqlite3
    import tempfile
    origin = db.execute("PRAGMA database_list").fetchone()[2]
    if origin and Path(origin).resolve() == Path(path).resolve():
        raise ValueError("Cannot overwrite the active database")
    keep = {r['id'] for r in selected_rows(db, **filters)}
    handle, temporary = tempfile.mkstemp(suffix='.sqlite', dir=Path(path).parent)
    os.close(handle)
    try:
        target = sqlite3.connect(temporary)
        try:
            db.backup(target)
            target.execute('PRAGMA secure_delete=ON')
            tables={r[0] for r in target.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            with target:
                # Exported databases must never contain login hashes or salts.
                if 'reviewers' in tables: target.execute('DELETE FROM reviewers')
                for (record_id,) in target.execute("SELECT id FROM records").fetchall():
                    if record_id not in keep:
                        target.execute("DELETE FROM reviews WHERE record_id=?", (record_id,))
                        target.execute("DELETE FROM validation_history WHERE record_id=?", (record_id,))
                        for table in ('human_decisions','review_packets','review_batch_members'):
                            if table in tables: target.execute('DELETE FROM '+table+' WHERE record_id=?',(record_id,))
                        target.execute("DELETE FROM records WHERE id=?", (record_id,))
                if filters:
                    retained = records(target)
                    documents = {(r['document_sha256'], r['source_id']) for r in retained}
                    source_ids = {r['source_id'] for r in retained}
                    for sha, sid in target.execute("SELECT sha256,source_id FROM documents").fetchall():
                        if (sha, sid) not in documents:
                            target.execute("DELETE FROM documents WHERE sha256=? AND source_id=?", (sha, sid))
                    for run_id, sid in target.execute("SELECT id,source_id FROM runs").fetchall():
                        if sid not in source_ids:
                            target.execute("DELETE FROM runs WHERE id=?", (run_id,))
                assert target.execute("PRAGMA integrity_check").fetchone()[0] == 'ok'
            target.execute('VACUUM')
        finally:
            target.close()
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
