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

    Fetch up to 600 *active* UK companies that are at least five years old.

    Companies House advanced-search filters we apply:
        • incorporated_to = today − 5 years
        • company_status  = active
        • size            = 600  (row cap per call)

    The raw JSON gets normalised and saved to:
        <out>/companies_active_5y_<YYYY-MM-DD>.parquet
    where the date is the five-years-ago cutoff.

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
import os
import datetime
import argparse
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # picks up CH_API_KEY from a local .env when running outside CI


def main(days, out):
    """Fetch up to 600 *active* UK companies that are at least five years old.

    Companies House advanced-search filters we apply:
        • company_status = active
        • size = 600 (row cap per call)
    """
    today = datetime.date.today()
    five_years_ago = (today - datetime.timedelta(days=5 * 365))

    base_url = (
        "https://api.company-information.service.gov.uk/"
        "advanced-search/companies"
    )
    params = {
        "company_status": "active",
        "size": 600,
        "incorporated_from": "1900-01-01",  # Start from beginning
        "incorporated_to": five_years_ago.strftime("%Y-%m-%d")  # Up to 5 years ago
    }

    resp = requests.get(base_url, params=params, auth=(os.getenv("CH_API_KEY", ""), ""))
    resp.raise_for_status()
    items = resp.json().get("items", [])

    if not items:
        print(f"No active companies found with incorporation date ≤ {five_years_ago}")
        return

    df = pd.json_normalize(items)
    os.makedirs(out, exist_ok=True)
    out_path = f"{out}/companies_active_5y_{five_years_ago.strftime('%Y-%m-%d')}.parquet"
    df.to_parquet(out_path)
    print(f"Wrote {len(df)} rows to {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=1)  # kept for CLI symmetry, not used
    parser.add_argument("--out", required=True)
    main(**vars(parser.parse_args()))