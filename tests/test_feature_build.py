"""Offline check for build_features_for_df. Run: python tests/test_feature_build.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from feature_build import build_features_for_df


def _raw(**overrides):
    df = pd.DataFrame({
        "company_number": ["001", "002", "003"],
        "company_name": ["C LTD", "A LTD", "B LTD"],
        "company_status": ["active"] * 3,
        "company_type": ["ltd"] * 3,
        "date_of_creation": ["2001-01-01"] * 3,
        # As pd.read_parquet returns them: numpy arrays, plus a missing value
        "sic_codes": [np.array(["62012", "70100"]), np.array(["7487"]), None],
        "registered_office_address.locality": ["London", None, "Leeds"],
    })
    return df.assign(**overrides)


def test_sic_codes_from_parquet_arrays():
    out = build_features_for_df(_raw()).set_index("company_number")
    assert out.loc["001", "industry_code"] == "62012"
    assert out.loc["002", "industry_code"] == "7487"
    assert out.loc["003", "industry_code"] == "00000"


def test_missing_company_subtype_column():
    out = build_features_for_df(_raw())  # _raw() has no company_subtype
    assert out["company_subtype"].isna().all()
    assert list(out["company_name"]) == ["A LTD", "B LTD", "C LTD"]


if __name__ == "__main__":
    test_sic_codes_from_parquet_arrays()
    test_missing_company_subtype_column()
    print("feature_build checks passed")
