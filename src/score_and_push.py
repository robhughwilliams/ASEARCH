import os
import sys
import pandas as pd
from notion_client import Client

# Load Notion API credentials from environment
NOTION_TOKEN = os.getenv('NOTION_TOKEN')
NOTION_DB_ID = os.getenv('NOTION_DB_ID')
if not NOTION_TOKEN or not NOTION_DB_ID:
    raise EnvironmentError("NOTION_TOKEN or NOTION_DB_ID is not set in the environment.")

# Initialize the Notion client
notion = Client(auth=NOTION_TOKEN)

# Load the features DataFrame
df = pd.read_parquet('data/features/features.parquet')

# Sort companies alphabetically by name and select the top 20
df_sorted = df.sort_values('company_name', ascending=True, na_position='last')
top20 = df_sorted.head(20)
if top20.empty:
    print("No companies found to push to Notion.")
    sys.exit(0)

# Push each of the top 20 companies to the Notion database
for _, row in top20.iterrows():
    name = str(row['company_name']) if pd.notna(row['company_name']) else ""
    company_no = str(row['company_number']) if pd.notna(row['company_number']) else ""
    age = int(row['age_years']) if pd.notna(row['age_years']) else None
    industry = str(row['industry']) if pd.notna(row['industry']) else ""
    location = str(row['location']) if pd.notna(row['location']) else ""
    # Prepare Notion page properties
    properties = {
        "Name": {"title": [{"text": {"content": name}}]},
        "Company": {"rich_text": [{"text": {"content": company_no}}]},
        "Age": {"number": age},
        "Status": {"select": {"name": "Gold"}},
        "Industry": {"rich_text": [{"text": {"content": industry}}]},
        "Location": {"rich_text": [{"text": {"content": location}}]}
    }
    try:
        print(f"Pushing to Notion: {name} (Company {company_no})...")
        notion.pages.create(parent={"database_id": NOTION_DB_ID}, properties=properties)
        print(f"Successfully pushed {name}.")
    except Exception as e:
        print(f"Failed to push {name} (Company {company_no}): {e}", file=sys.stderr)