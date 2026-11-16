import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

COMTRADE_BASE = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"

def fetch_comtrade_preview(reporter_code="586", period="2023", flow_code="X", max_records=100):
    """
    Fetch a limited preview of UN Comtrade trade statistics.
    It does NOT fetch carbon footprints. Codes/parameters are API-specific.
    Reporter 586 is Pakistan in UN M49 conventions; verify parameter validity for requested query.
    """
    params = {
        "flowCode": flow_code,
        "reporterCode": reporter_code,
        "period": period,
        "maxRecords": min(max(int(max_records), 1), 500)
    }
    key = os.getenv("COMTRADE_API_KEY", "").strip()
    # Public preview endpoint may not require a key. Never print secrets.
    url = COMTRADE_BASE
    response = requests.get(url, params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("data", [])
    return pd.DataFrame(rows), response.url
