"""Runs the browser test (tests/ui/calculator_flow.js) against a real server. Skipped when Node or Playwright is not installed.

The database holds the real bundled reference data; the approvals and the product are SYNTHETIC TEST DATA.
"""
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from gcc_cos import approvals, refdata
from gcc_cos.storage import connect, insert

ROOT = Path(__file__).resolve().parents[1]


def node_path():
    node, npm = shutil.which("node"), shutil.which("npm")
    if not node or not npm:
        return None
    root = subprocess.run([npm, "root", "-g"], capture_output=True, text=True).stdout.strip()
    return root if root and (Path(root) / "playwright").is_dir() else None


@pytest.mark.skipif(node_path() is None, reason="Node.js with Playwright is not installed")
def test_whole_questionnaire_in_a_browser_on_desktop_and_phone(tmp_path):
    path = tmp_path / "ui.sqlite"
    db = connect(path)
    refdata.load_all(db)
    insert(db, {"entity_type": "product", "data_kind": "published_product_footprint", "category": "electronics", "subcategory": "Laptop",
                "manufacturer": "Apple", "product_name": "SYNTHETIC MacBook Air M1 256GB test row", "declared_unit": "item", "normalized_value": "161",
                "normalized_unit": "kg CO2e/item", "lifecycle_scope": "SYNTHETIC", "source_id": "owid-country-data", "year": 2020,
                "document_title": "SYNTHETIC", "source_url": "https://example.invalid/", "license": "SYNTHETIC", "issues": []})
    for dataset in ("owid-country-data", "uk-desnz-conversion-factors-2026", "agribalyse-3.2-synthesis"):
        approvals.approve(db, dataset, "household_calculator", "SYNTHETIC test approver", "SYNTHETIC approval for tests")
    db.commit()
    db.close()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = subprocess.Popen([sys.executable, "-m", "gcc_cos.web", "--db", str(path), "--port", str(port)], cwd=ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(60):
            try:
                urllib.request.urlopen(url + "/api/v1/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        run = subprocess.run(["node", str(ROOT / "tests" / "ui" / "calculator_flow.js"), url], capture_output=True, text=True, timeout=180,
                             env={**os.environ, "NODE_PATH": node_path()})
        assert run.returncode == 0 and "UI OK" in run.stdout, run.stdout + run.stderr
    finally:
        server.terminate()
        server.wait(timeout=10)
