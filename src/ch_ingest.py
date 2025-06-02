#!/usr/bin/env python
import os, datetime, argparse, requests, pandas as pd, duckdb
from dotenv import load_dotenv

load_dotenv()     # picks up CH_API_KEY if you run locally via .env

def main(days, out):
    """
    Fetch up to 600 *active* UK companies that are at least five years old.

    We hit the Companies‑House *advanced search* endpoint with:
        - incorporated_to = today − 5 years
        - company_status  = active
        - size            = 600      (max rows we’ll accept in one call)

    Results are stored as <out>/companies_active_5y_<yyyy‑mm‑dd>.parquet
    where the date is the 'incorporated_to' cutoff.
    """
    today          = datetime.date.today()
    five_years_ago = (today - datetime.timedelta(days=5 * 365)).isoformat()

    base = "https://api.company-information.service.gov.uk/advanced-search/companies"
    params = {
        "incorporated_to": five_years_ago,
        "company_status": "active",
        "size": 600
    }

    r = requests.get(base, params=params, auth=(os.getenv("CH_API_KEY", ""), ""))
    r.raise_for_status()
    items = r.json().get("items", [])

    if not items:
        print(f"No active companies found with incorporation date ≤ {five_years_ago}")
        return

    df = pd.json_normalize(items)
    os.makedirs(out, exist_ok=True)
    out_path = f"{out}/companies_active_5y_{five_years_ago}.parquet"
    df.to_parquet(out_path)
    print(f"Wrote {len(df)} rows to {out_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--out", required=True)
    main(**vars(ap.parse_args()))