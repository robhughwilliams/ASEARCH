#!/usr/bin/env python
import os
import datetime
import argparse
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # picks up CH_API_KEY from a local .env when running outside CI

# Path to store raw Parquet files
RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Path for deduplication log
LOG_DIR = Path("data/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
SEEN_LOG = LOG_DIR / "seen_companies.parquet"

def load_seen_companies() -> pd.Series:
    if SEEN_LOG.exists():
        return pd.read_parquet(SEEN_LOG)["company_number"]
    return pd.Series(dtype=str)

def save_seen_companies(seen_series: pd.Series) -> None:
    seen_df = pd.DataFrame({"company_number": seen_series.drop_duplicates()})
    seen_df.to_parquet(SEEN_LOG, index=False)

def fetch_new_companies(five_years_ago: str, seen: pd.Series, limit: int = 600) -> pd.DataFrame:
    """ 
    Fetch companies via pagination until we collect 'limit' new companies not in 'seen'.
    """
    base_url = "https://api.company-information.service.gov.uk/advanced-search/companies"
    new_companies = []
    collected = 0
    start_index = 0
    while collected < limit:
        params = {
            "company_status": "active",
            "size": limit,
            "incorporated_from": "1900-01-01",
            "incorporated_to": five_years_ago,
            "start_index": start_index
        }
        resp = requests.get(base_url, params=params, auth=(os.getenv("CH_API_KEY", ""), ""))
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            break

        df_page = pd.json_normalize(items)
        # Filter out already seen
        df_page = df_page[~df_page["company_number"].isin(seen)]
        if df_page.empty:
            # Advance to next page
            start_index += limit
            continue

        # Calculate how many more we need
        needed = limit - collected
        df_new_slice = df_page.head(needed)
        new_companies.append(df_new_slice)
        collected += len(df_new_slice)

        if collected >= limit:
            break

        # Advance to next page if still space
        start_index += limit

    if new_companies:
        return pd.concat(new_companies, ignore_index=True)
    return pd.DataFrame(columns=[])

def main(days, out):
    """
    Fetch up to 600 *active* UK companies that are at least five years old,
    skipping any already seen in prior runs.
    """
    today = datetime.date.today()
    five_years_ago = (today - datetime.timedelta(days=5 * 365)).strftime("%Y-%m-%d")

    # Load seen companies log
    seen_series = load_seen_companies()

    # Fetch new, unseen companies
    df_new = fetch_new_companies(five_years_ago, seen_series, limit=600)

    if df_new.empty:
        print(f"No new active companies found up to {five_years_ago}")
        return

    # Save today's raw data file
    out_path = RAW_DIR / f"companies_active_5y_{five_years_ago}.parquet"
    df_new.to_parquet(out_path, index=False)
    print(f"Wrote {len(df_new)} new rows to {out_path}")

    # Update seen log
    updated_seen = pd.concat([seen_series, df_new["company_number"]], ignore_index=True)
    save_seen_companies(updated_seen)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)  # kept for CLI symmetry, not used
    parser.add_argument("--out", required=True)
    main(**vars(parser.parse_args()))