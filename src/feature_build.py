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