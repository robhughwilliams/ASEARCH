"""
Build feature set from Companies House raw parquet output.
"""

from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd
import glob
import os

# Try multiple possible locations for raw data
POSSIBLE_RAW_DIRS = [
    Path("data/raw"),
    Path("."),  # Current directory (where artifact might be downloaded)
    Path("raw_companies"),  # Direct artifact name
]

FEATURE_DIR = Path("data/features")
FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def load_latest_raw() -> pd.DataFrame:
    """Find and load the most recent parquet file from possible locations."""
    all_parquet_files = []
    
    # Search all possible directories
    for raw_dir in POSSIBLE_RAW_DIRS:
        if raw_dir.exists():
            parquet_files = list(raw_dir.glob("*.parquet"))
            all_parquet_files.extend(parquet_files)
            print(f"🔍  Found {len(parquet_files)} parquet files in {raw_dir}")
    
    # Also search current directory and subdirectories
    current_dir_files = glob.glob("**/*.parquet", recursive=True)
    for file_path in current_dir_files:
        all_parquet_files.append(Path(file_path))
    
    if not all_parquet_files:
        # Print debug info
        print("❌ No Parquet files found. Debug info:")
        print(f"Current working directory: {os.getcwd()}")
        print("Directory contents:")
        for item in Path(".").iterdir():
            print(f"  {item}")
        
        # Check if data/raw exists
        data_raw = Path("data/raw")
        if data_raw.exists():
            print(f"Contents of data/raw:")
            for item in data_raw.iterdir():
                print(f"  {item}")
        
        raise FileNotFoundError(
            f"No Parquet files found in any of: {[str(d) for d in POSSIBLE_RAW_DIRS]} "
            "or current directory tree. Did the ingest step run and/or did you download its artifact?"
        )
    
    # Remove duplicates and find the most recent
    unique_files = list(set(all_parquet_files))
    latest = max(unique_files, key=lambda p: p.stat().st_mtime)
    print(f"🔍  Using raw file → {latest}")
    return pd.read_parquet(latest)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    today = date.today().year

    df["age"] = today - pd.to_datetime(df["date_of_creation"], errors="coerce").dt.year
    df["industry_code"] = (
        df["sic_codes"]
        .apply(lambda xs: xs[0] if isinstance(xs, list) and xs else None)
        .str[:5]
        .fillna("00000")
    )
    df["location"] = df["registered_office_address.locality"].fillna("")

    # keep only active cos > 5 yrs old, sort A-Z
    df = (
        df.query("age > 5 and company_status == 'active'")
        .sort_values("company_name")
        .reset_index(drop=True)
    )
    return df


def main() -> None:
    feat = build_features(load_latest_raw())
    out = FEATURE_DIR / "features.parquet"
    feat.to_parquet(out, index=False)
    print(f"✅  Features saved → {out}   ({len(feat):,} rows)")


if __name__ == "__main__":
    main()