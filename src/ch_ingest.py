"""#!/usr/bin/env python
import os
import datetime
import argparse
import requests
import pandas as pd
import duckdb
from dotenv import load_dotenv

load_dotenv()  # picks up CH_API_KEY from a local .env when running outside CI


def main(days, out):
    """
    Fetch up to 600 *active* UK companies that are at least five years old.

    Companies House advanced-search filters we apply:
        • incorporated_to = today − 5 years
        • company_status  = active
        • size            = 600  (row cap per call)

    The raw JSON gets normalised and saved to:
        <out>/companies_active_5y_<YYYY-MM-DD>.parquet
    where the date is the five-years-ago cutoff.
    """
    today          = datetime.date.today()
    five_years_ago = (today - datetime.timedelta(days=5 * 365)).isoformat()

    base_url = (
        "https://api.company-information.service.gov.uk/"
        "advanced-search/companies"
    )
    params = {
        "incorporated_to": five_years_ago,
        "company_status": "active",
        "size": 600,
    }

    resp = requests.get(base_url, params=params, auth=(os.getenv("CH_API_KEY", ""), ""))
    resp.raise_for_status()
    items = resp.json().get("items", [])

    if not items:
        print(f"No active companies found with incorporation date ≤ {five_years_ago}")
        return

    df = pd.json_normalize(items)
    os.makedirs(out, exist_ok=True)
    out_path = f"{out}/companies_active_5y_{five_years_ago}.parquet"
    df.to_parquet(out_path)
    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)  # kept for CLI symmetry, not used
    parser.add_argument("--out", required=True)
    main(**vars(parser.parse_args()))
    """

#!/usr/bin/env python
"""
feature_build.py

Loads the most recent Parquet file produced by ch_ingest.py,
derives a few simple features, and writes them back out to
data/features/features.parquet  (Parquet, one row per company).

Features right now:
    • company_number
    • company_name
    • incorporation_date  (ISO string)
    • age_years           (integer)
"""
import os
import glob
import datetime
import pandas as pd
import duckdb
from pathlib import Path

RAW_DIR     = Path("data/raw")
FEATURE_DIR = Path("data/features")
FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def latest_raw_file() -> Path:
    files = sorted(RAW_DIR.glob("companies_active_5y_*.parquet"))
    if not files:
        raise FileNotFoundError("No raw Parquet files found in data/raw")
    return files[-1]   # newest by filename


def build_features(raw_path: Path) -> pd.DataFrame:
    df = pd.read_parquet(raw_path)

    # guard for API shape changes
    required = {"company_number", "title", "date_of_creation"}
    missing  = required - set(df.columns)
    if missing:
        raise ValueError(f"Raw frame missing columns: {missing}")

    df_feat = pd.DataFrame({
        "company_number": df["company_number"],
        "company_name":   df["title"],
        "incorporation_date": df["date_of_creation"],
    })
    today = datetime.date.today()
    df_feat["age_years"] = (
        pd.to_datetime(df_feat["incorporation_date"]).dt.date
        .apply(lambda d: (today - d).days // 365)
    )

    return df_feat


def main() -> None:
    raw_path = latest_raw_file()
    features = build_features(raw_path)
    out_path = FEATURE_DIR / "features.parquet"
    features.to_parquet(out_path, index=False)
    print(f"Wrote {len(features)} feature rows → {out_path}")


if __name__ == "__main__":
    main()