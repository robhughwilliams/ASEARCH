#!/usr/bin/env python
import os, datetime, argparse, requests, pandas as pd, duckdb
from dotenv import load_dotenv

load_dotenv()     # picks up CH_API_KEY if you run locally via .env

def main(days, out):
    since = (datetime.date.today() - datetime.timedelta(days=days)).isoformat()
    url   = f"https://api.company-information.service.gov.uk/filings?since_date={since}"
    r = requests.get(url, auth=(os.getenv("CH_API_KEY", ""), ""))
    r.raise_for_status()
    items = r.json().get("items", [])
    if items:
        df = pd.json_normalize(items)
        os.makedirs(out, exist_ok=True)
        df.to_parquet(f"{out}/filings_{since}.parquet")
        print(f"Wrote {len(df)} rows")
    else:
        print("No new filings.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--out", required=True)
    main(**vars(ap.parse_args()))