#!/usr/bin/env python
"""
score_and_push.py

Very simple scorer:
    • Score = age_years  (older is "better" for demo)
Sends the top-N (default 20) records to Notion.

Env vars required (already set in CI):
    NOTION_TOKEN
    NOTION_DB_ID
"""
import os
import pandas as pd
from notion_client import Client

TOP_N = 20
FEATURE_PATH = "data/features/features.parquet"


def push_to_notion(rows, notion, db_id):
    for _, row in rows.iterrows():
        notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "Name": {"title": [{"text": {"content": row['company_name']}}]},
                "Company Number": {"rich_text": [{"text": {"content": row['company_number']}}]},
                "Age (yrs)": {"number": int(row['age_years'])},
                "Status": {"select": {"name": "Gold"}},
            },
        )
    print(f"Pushed {len(rows)} rows to Notion")


def main():
    if not os.path.exists(FEATURE_PATH):
        raise FileNotFoundError("Run feature_build.py first – features file missing.")

    df = pd.read_parquet(FEATURE_PATH)
    df["score"] = df["age_years"]
    top = df.sort_values("score", ascending=False).head(TOP_N)

    notion = Client(auth=os.environ["NOTION_TOKEN"])
    push_to_notion(top, notion, os.environ["NOTION_DB_ID"])


if __name__ == "__main__":
    main()