import csv
import hashlib
import json
from pathlib import Path
import pandas as pd
from pypdf import PdfReader
from .download import download, permitted, failure_info
from .model import validate, classify
from .storage import insert, now
from .products import boavizta, ilcd_records


def load_registry(path):
    sources = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [s["id"] for s in sources]
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate source IDs")
    return sources


def extract(path, source):
    fmt = source["format"]
    if fmt == "csv":
        with open(path, encoding=source.get("encoding", "utf-8-sig"), newline="") as f:
            yield from enumerate(csv.DictReader(f), start=2)
    elif fmt == "xlsx":
        frame = pd.read_excel(path, sheet_name=source.get("sheet", 0), dtype=str).fillna("")
        yield from enumerate(frame.to_dict("records"), start=2)
    elif fmt == "json":
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        for key in source.get("records_path", []):
            obj = obj[key]
        if not isinstance(obj, list):
            raise ValueError("JSON records must be an array; configure records_path")
        yield from enumerate(obj, start=1)
    elif fmt == "ilcd_json":
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
        for i, record in enumerate(ilcd_records(doc, source), 1):
            yield i, record
    else:
        raise ValueError("Unsupported tabular format")


def adapt(row, source):
    if source.get("adapter") == "boavizta":
        return boavizta(row, source)
    if source.get("adapter") == "ilcd_epd":
        return dict(row)
    if source.get("adapter") == "owid_cement":
        if row.get("country") not in source["countries"] or str(row.get("year")) != str(source["year"]) or not row.get("cement_co2"):
            return None
        return dict(product_name="Annual cement-process CO2 emissions", entity_type="industrial_inventory",
                    material="cement", original_value=row["cement_co2"], original_unit="Mt CO2",
                    geography=row["country"], year=str(row["year"]), data_kind="published_inventory",
                    lifecycle_scope="Territorial annual cement-process CO2; not a product lifecycle assessment",
                    methodology="Global Carbon Budget (2025), cement CO2 series; OWID standardized national inventory; excludes product-level allocation")
    if source.get("adapter", "mapped") != "mapped":
        raise ValueError("Unknown adapter")
    result = dict(source.get("defaults", {}))
    for target, column in source.get("columns", {}).items():
        if column not in row:
            raise ValueError(f"Required column missing: {column}")
        result[target] = row[column]
    return result


def ingest(db, source, cache, local_file=None, hs_rules=None):
    started = now()
    added = duplicates = 0
    error = dict(error_code=None, http_status=None, next_action=None)
    try:
        if local_file is None and not source.get("enabled", False):
            return {"source": source["id"], "status": "disabled", "inserted": 0, "duplicates": 0}
        permitted(source)
        path = Path(local_file) if local_file else download(source, cache)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if source.get("sha256") and digest != source["sha256"]:
            raise ValueError("Source checksum mismatch")
        # Retain the exact original even for manually supplied files.
        archived = Path(cache) / (digest + "." + source["format"])
        archived.parent.mkdir(parents=True, exist_ok=True)
        if path.resolve() != archived.resolve():
            archived.write_bytes(path.read_bytes())
        text = None
        if source["format"] == "pdf":
            text = "\n".join(f"[Page {i}]\n{page.extract_text() or ''}" for i, page in enumerate(PdfReader(path).pages, 1))
        with db:
            db.execute("INSERT OR IGNORE INTO documents VALUES (?,?,?,?,?,?,?)",
                       (digest, source["id"], source["url"], source["title"], started, str(archived), text))
            if source["format"] != "pdf":
                for locator, row in extract(path, source):
                    r = adapt(row, source)
                    if r is None:
                        continue
                    adapter_evidence = r.get("evidence")
                    r.update(source_id=source["id"], source_url=source["url"], document_title=source["title"],
                             license=source["license"], license_url=source["license_url"], attribution=source.get("attribution"),
                             document_sha256=digest, retrieved_at=started,
                             evidence={"row": locator, "sheet": source.get("sheet"), "raw":
                                       {k: row[k] for k in ("country", "year", "cement_co2")}
                                       if source.get("adapter") == "owid_cement" else row})
                    if adapter_evidence:
                        r["evidence"] = adapter_evidence
                    if not r.get("hs6"):
                        r.update(classify(r.get("product_name", ""), hs_rules or []))
                    count = insert(db, validate(r))
                    added += count
                    duplicates += 1 - count
        status = "extracted_needs_review" if source["format"] == "pdf" else "completed"
        detail = "PDF text only: human table mapping needed; scanned PDFs require OCR" if text is not None else ""
    except Exception as exc:
        # This source transaction rolls back; continue with other sources.
        added = duplicates = 0
        status, detail = "failed", f"{type(exc).__name__}: {exc}"
        error = failure_info(exc)
    with db:
        db.execute("INSERT INTO runs(source_id,started_at,status,inserted,duplicates,detail,error_code,http_status,next_action) VALUES (?,?,?,?,?,?,?,?,?)",
                   (source["id"], started, status, added, duplicates, detail, error["error_code"], error["http_status"], error["next_action"]))
    return dict(source=source["id"], status=status, inserted=added, duplicates=duplicates, detail=detail, **error)
