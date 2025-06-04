#!/usr/bin/env python
"""
Build and maintain a master feature table from daily raw Parquet outputs.
"""

from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd
import glob
import os

# Directories
RAW_DIR = Path("data/raw")
FEATURE_DIR = Path("data/features")
FEATURE_DIR.mkdir(parents=True, exist_ok=True)

# Master feature log path
ALL_FEATURES = FEATURE_DIR / "all_features.parquet"


def find_latest_raw() -> Path:
    """Return the most recently modified Parquet under data/raw/."""
    files = RAW_DIR.glob("companies_active_5y_*.parquet")
    candidates = list(files)
    if not candidates:
        raise FileNotFoundError(f"No raw files in {RAW_DIR.resolve()}")
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    print(f"🔍  Latest raw file: {latest.name}")
    return latest


def build_features_for_df(df: pd.DataFrame) -> pd.DataFrame:
    """Given a raw-companies DataFrame, derive all desired features."""
    today_year = date.today().year

    # Compute age in whole years
    df["age"] = today_year - pd.to_datetime(df["date_of_creation"], errors="coerce").dt.year

    # First SIC‐code as 5-digit string
    df["industry_code"] = (
        df["sic_codes"]
        .apply(lambda xs: xs[0] if isinstance(xs, list) and xs else None)
        .str[:5]
        .fillna("00000")
    )

    # Location from registered office’s locality (or "")
    df["location"] = df["registered_office_address.locality"].fillna("")

    # Keep only active, age > 5 (though ingest already guaranteed that)
    df = df.query("age > 5 and company_status == 'active'")

    # Sort alphabetically by company_name
    df = df.sort_values("company_name").reset_index(drop=True)

    # Select and rename columns
    features = df[[
        "company_number",
        "company_name",
        "company_status",
        "company_type",
        "company_subtype",
        "date_of_creation",
        "age",
        "industry_code",
        "location"
    ]].copy()
    return features


def main() -> None:
    # 1) Load latest raw
    raw_path = find_latest_raw()
    df_raw = pd.read_parquet(raw_path)

    # 2) Build features for the new batch
    df_new = build_features_for_df(df_raw)
    if df_new.empty:
        print("No features to add (empty after filtering).")
        return

    # 3) Write today’s features file (optional debug copy)
    date_suffix = Path(raw_path).stem.split("_")[-1]
    debug_path = FEATURE_DIR / f"features_{date_suffix}.parquet"
    df_new.to_parquet(debug_path, index=False)
    print(f"✅  Wrote today’s features → {debug_path.name} ({len(df_new)} rows)")

    # 4) Load or create master feature log, append new rows, drop duplicates
    if ALL_FEATURES.exists():
        df_master = pd.read_parquet(ALL_FEATURES)
        df_combined = pd.concat([df_master, df_new], ignore_index=True)
        df_combined = df_combined.drop_duplicates(subset="company_number")
        print(f"📦  Merged with master log: {len(df_master)} + {len(df_new)} → {len(df_combined)} unique rows")
    else:
        df_combined = df_new
        print(f"📦  Created new master feature log with {len(df_new)} rows")

    # 5) Save back the master log
    df_combined.to_parquet(ALL_FEATURES, index=False)
    print(f"✅  Saved master feature log → {ALL_FEATURES.name}")

    # Done
    print("Feature build complete.")


if __name__ == "__main__":
    main()