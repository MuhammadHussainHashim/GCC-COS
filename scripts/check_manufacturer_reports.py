"""Machine check: is each product's footprint printed in the manufacturer's own report?

For every row of examples/phase2/boavizta-products.csv this downloads the report the row links to, reads its text and
looks for the row's total footprint (gwp_total). It is a screening aid for the human evidence review, NOT that review:
"found" means the number is printed in the document near "CO2" or "kg"; it does not prove the number belongs to the
same model and configuration. Nothing in the database is changed.

    python scripts/check_manufacturer_reports.py --cache FOLDER --out report.json [--limit N]
"""
import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import logging

import requests

logging.getLogger("pypdf").setLevel(logging.CRITICAL)

ROOT = Path(__file__).resolve().parents[1]
AGENT = "Mozilla/5.0 (compatible; data-verification)"
MAX_BYTES = 60_000_000


def fetch(url, cache):
    path = cache / hashlib.sha256(url.encode()).hexdigest()
    meta = path.with_suffix(".json")
    if meta.exists():
        return json.loads(meta.read_text()), path
    info = {"url": url, "status": None, "error": None, "type": None, "bytes": 0}
    try:
        with requests.get(url, headers={"User-Agent": AGENT}, timeout=(15, 60), stream=True, allow_redirects=True) as r:
            info["status"], info["type"], info["final_url"] = r.status_code, r.headers.get("content-type", ""), r.url
            if r.status_code == 200:
                body = b""
                for chunk in r.iter_content(1 << 16):
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise ValueError("file too large")
                path.write_bytes(body)
                info["bytes"] = len(body)
    except Exception as e:  # network errors are a result here, not a crash
        info["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    meta.write_text(json.dumps(info))
    return info, path


def text_of(path, info):
    body = path.read_bytes()
    if body[:5] == b"%PDF-":
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(body)).pages), "pdf"
    if body[:2] == b"PK":  # PowerPoint or Word file: read the text inside its slides or pages
        import zipfile
        with zipfile.ZipFile(io.BytesIO(body)) as z:
            parts = [n for n in z.namelist() if re.match(r"(ppt/slides/slide\d+|word/document)\.xml$", n)]
            return " ".join(re.sub(r"<[^>]+>", " ", z.read(n).decode("utf-8", errors="replace")) for n in parts), "office"
    return re.sub(r"<[^>]+>", " ", body.decode("utf-8", errors="replace")), "html"


def find(text, value):
    """Return 'near' if the number is printed within 80 characters of CO2/kg, 'anywhere' if printed elsewhere, else None."""
    number = float(value)
    forms = {f"{number:g}", f"{number:.0f}" if number == int(number) else str(value).strip(), f"{number:,.0f}" if number == int(number) else f"{number:,}"}
    forms |= {f"{number:.1f}", f"{number:.2f}", f"{number:,.1f}", f"{number:,.2f}"}  # the same number printed with trailing zeros
    if number >= 10:  # scientific notation, as some reports print it (1.9E+05, 2.05E+01)
        mantissa, exponent = f"{number:E}".split("E")
        short = mantissa.rstrip("0").rstrip(".")
        forms |= {f"{m}E+{int(exponent):02d}" for m in (short, f"{float(mantissa):.2f}", f"{float(mantissa):.1f}") if float(m) * 10 ** int(exponent) == number or abs(float(m) * 10 ** int(exponent) - number) < 1e-9}
    forms |= {f.replace(",", " ") for f in forms} | {f.replace(".", ",") for f in forms if "." in f}
    best = None
    flat = text.replace(" ", " ").replace(" ", " ")
    for form in forms:
        for m in re.finditer(r"(?<![\d.,])" + re.escape(form) + r"(?![\d]|[.,]\d)", flat):
            around = flat[max(0, m.start() - 80): m.end() + 80].lower().replace("₂", "2")
            if re.search(r"co2|kg|carbon|ghg|footprint", around):
                return "near"
            best = "anywhere"
    return best


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--cache", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args(argv)
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)
    with open(ROOT / "examples/phase2/boavizta-products.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))[: args.limit]
    urls = sorted({r["sources"].strip() for r in rows if r["sources"].strip().startswith("http")})
    with ThreadPoolExecutor(8) as pool:
        fetched = dict(zip(urls, pool.map(lambda u: fetch(u, cache), urls)))
    texts, out = {}, []
    for n, r in enumerate(rows, start=2):
        url = r["sources"].strip()
        item = {"csv_row": n, "manufacturer": r["manufacturer"], "name": r["name"], "gwp_total": r["gwp_total"], "url": url}
        if url not in fetched:
            item["result"] = "no_link"
        else:
            info, path = fetched[url]
            if info["status"] != 200:
                item["result"], item["detail"] = "unreachable", info["error"] or f"HTTP {info['status']}"
            else:
                if url not in texts:
                    try:
                        texts[url] = text_of(path, info)
                    except Exception as e:
                        texts[url] = (None, f"{type(e).__name__}: {str(e)[:80]}")
                text, kind = texts[url]
                if text is None or len(text.strip()) < 200:
                    item["result"], item["detail"] = "unreadable", kind if text is None else f"{kind} with no extractable text"
                else:
                    hit = find(text, r["gwp_total"]) if r["gwp_total"].strip() else None
                    item["result"] = {"near": "found_near_co2", "anywhere": "found_elsewhere_in_document", None: "not_found"}[hit]
                    item["document"] = kind
        out.append(item)
    summary = Counter(i["result"] for i in out)
    by_maker = {}
    for i in out:
        by_maker.setdefault(i["manufacturer"], Counter())[i["result"]] += 1
    Path(args.out).write_text(json.dumps({"rows": len(out), "distinct_documents": len(urls), "summary": dict(summary),
                                          "by_manufacturer": {k: dict(v) for k, v in sorted(by_maker.items())}, "items": out}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(len(out), "rows,", len(urls), "documents:", dict(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
