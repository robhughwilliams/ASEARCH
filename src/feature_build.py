"""import os
import glob
import pandas as pd
from datetime import datetime

# Directory containing raw Companies House Parquet files
RAW_DATA_DIR = os.getenv('RAW_DATA_DIR', 'data/raw')

# Find all Parquet files in the raw data directory
parquet_files = glob.glob(os.path.join(RAW_DATA_DIR, '*.parquet'))
if not parquet_files:
    raise FileNotFoundError(f"No Parquet files found in {RAW_DATA_DIR} directory.")

# Identify the most recent Parquet file by modification time
latest_file = max(parquet_files, key=os.path.getmtime)
print(f"Using latest raw data file: {os.path.basename(latest_file)}")

# Load the latest Parquet file into a DataFrame
df = pd.read_parquet(latest_file)

# Determine the company name field (either 'title' or 'company_name')
if 'company_name' in df.columns:
    df['company_name_feature'] = df['company_name']
elif 'title' in df.columns:
    df['company_name_feature'] = df['title']
else:
    raise KeyError("No company name field found (expected 'company_name' or 'title').")

# Determine the incorporation date field (either 'incorporation_date' or 'date_of_creation')
if 'incorporation_date' in df.columns:
    df['inc_date'] = pd.to_datetime(df['incorporation_date'], errors='coerce')
elif 'date_of_creation' in df.columns:
    df['inc_date'] = pd.to_datetime(df['date_of_creation'], errors='coerce')
else:
    raise KeyError("No incorporation date field found (expected 'incorporation_date' or 'date_of_creation').")

# Compute company age in full years (integer)
today = datetime.now()
# Determine if the anniversary has occurred this year; subtract 1 if not
not_anniversary_yet = (today.month < df['inc_date'].dt.month) | (
    (today.month == df['inc_date'].dt.month) & (today.day < df['inc_date'].dt.day)
)
df['age_years'] = (today.year - df['inc_date'].dt.year) - not_anniversary_yet.astype(int)
df['age_years'] = df['age_years'].fillna(0).astype(int)
# Prevent negative ages (for any data issues with future dates)
df.loc[df['age_years'] < 0, 'age_years'] = 0

# Extract industry (use the first SIC code from the sic_codes list/array)
if 'sic_codes' in df.columns:
    def get_first_sic(x):
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return None
        if isinstance(x, (list, tuple)):
            return x[0] if len(x) > 0 else None
        if isinstance(x, str):
            # If string looks like a list (e.g. "['12345','67890']"), evaluate it safely
            if x.startswith('[') and x.endswith(']'):
                try:
                    import ast
                    parsed = ast.literal_eval(x)
                    if isinstance(parsed, (list, tuple)) and parsed:
                        return parsed[0]
                except Exception:
                    pass
            # If comma-separated or single code in string form
            return x.split(',')[0] if ',' in x else x
        return x  # If already a single value (int/float), return as-is
    df['industry'] = df['sic_codes'].apply(get_first_sic)
else:
    # If SIC codes are in separate columns (e.g., 'SICCode1', etc.), take the first available
    sic_cols = [col for col in df.columns if col.lower().startswith('sic') and col.lower() != 'sic_codes']
    if sic_cols:
        sic_cols.sort()
        df['industry'] = df[sic_cols[0]]
    else:
        df['industry'] = None

# Extract location (prefer 'locality' from registered office address, otherwise use 'postal_code')
location_series = None
if 'registered_office_address' in df.columns:
    # If address is stored as a dict or JSON string
    def extract_location(addr):
        if addr is None or (isinstance(addr, float) and pd.isna(addr)):
            return None
        if isinstance(addr, dict):
            return addr.get('locality') or addr.get('postal_code')
        if isinstance(addr, str):
            try:
                import json
                addr_dict = json.loads(addr)
            except Exception:
                addr_dict = None
            if isinstance(addr_dict, dict):
                return addr_dict.get('locality') or addr_dict.get('postal_code')
            return None
        return None
    location_series = df['registered_office_address'].apply(extract_location)
else:
    # Check for flattened address fields
    possible_loc_cols = [
        'registered_office_address.locality',
        'registered_office_address_locality',
        'registered_office_address.postal_code',
        'registered_office_address_postal_code',
        'postal_code', 'PostCode', 'PostTown', 'City', 'Locality'
    ]
    for col in possible_loc_cols:
        if col in df.columns:
            location_series = df[col]
            break
if location_series is None:
    location_series = pd.Series([None] * len(df))
df['location'] = location_series

# Create the final DataFrame with required columns
final_df = df[['company_number', 'company_name_feature', 'inc_date', 'age_years', 'industry', 'location']].copy()
final_df.rename(columns={
    'company_name_feature': 'company_name',
    'inc_date': 'incorporation_date'
}, inplace=True)

# Ensure output directory exists and save the features DataFrame to Parquet
os.makedirs('data/features', exist_ok=True)
final_df.to_parquet('data/features/features.parquet', index=False)
print(f"Features file created: data/features/features.parquet (rows: {len(final_df)})")


Build feature set from Companies House raw parquet output.
"""

from __future__ import annotations
from datetime import date
from pathlib import Path
import pandas as pd

RAW_DATA_DIR = Path("data/raw")
FEATURE_DIR = Path("data/features")
FEATURE_DIR.mkdir(parents=True, exist_ok=True)


def load_latest_raw() -> pd.DataFrame:
    # pick the most-recent parquet dropped by ingest
    parquet_files = sorted(RAW_DATA_DIR.glob("*.parquet"))
    if not parquet_files:
        raise FileNotFoundError(
            f"No Parquet files found in {RAW_DATA_DIR.resolve()}. "
            "Did the ingest step run and/or did you download its artifact?"
        )
    latest = max(parquet_files, key=lambda p: p.stat().st_mtime)
    print(f"🔍  Using raw file → {latest.name}")
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