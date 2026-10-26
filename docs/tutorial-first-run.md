# Tutorial: your first local run, from Companies House to Notion

In this tutorial you run all three stages of ASEARCH on your own machine. By the end you'll have a Parquet file of up to 600 established UK companies, a feature table built from it, and 20 of those companies sitting as pages in a Notion database. You'll also know where each stage keeps its files, so you can inspect or re-run any one of them.

## What you'll need

- Python 3.12 (the version CI uses).
- A Companies House API key. Register an application at the [Companies House developer hub](https://developer.company-information.service.gov.uk/) and create a REST API key.
- A Notion account where you can create a database and an internal integration (only needed for Step 5).
- A terminal open at the repository root. Every script uses paths relative to the current directory.

## Step 1: Install dependencies

```bash
python3.12 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

You now have pandas, pyarrow, requests, notion-client and python-dotenv in an isolated environment.

## Step 2: Fetch your first batch of companies

Create a `.env` file in the repository root with your Companies House key:

```
CH_API_KEY=your-companies-house-key
```

`ch_ingest.py` loads `.env` automatically. `.env` is git-ignored, so the key stays local.

Run the ingest:

```bash
python src/ch_ingest.py --out data/raw
```

You should see something like:

```
Wrote 600 new rows to data/raw/companies_active_5y_2021-10-27.parquet
```

The date in the file name is the cutoff (today minus 5 × 365 days), not today. The script also wrote `data/logs/seen_companies.parquet`, which lists every company number it has saved. Run it again and you get a *different* 600 companies, because the ones you already have are skipped. A second run on the same day writes to the same file name, so it replaces the first batch's raw file (the seen log still keeps both).

If you see `requests.exceptions.HTTPError: 401`, the key is missing or wrong. Check the `.env` file name and that it sits in the directory you ran the command from.

## Step 3: Look at what came back

```bash
python -c "import pandas as pd, glob; f=sorted(glob.glob('data/raw/*.parquet'))[-1]; df=pd.read_parquet(f); print(f, df.shape); print(df[['company_number','company_name','date_of_creation']].head())"
```

Each row is one company exactly as the API returned it, with nested address fields flattened into columns like `registered_office_address.locality`.

## Step 4: Build the feature table

```bash
python src/feature_build.py
```

Expected output:

```
🔍  Latest raw file: companies_active_5y_2021-10-27.parquet
✅  Wrote today’s features → features_2021-10-27.parquet (600 rows)
📦  Created new master feature log with 600 rows
✅  Saved master feature log → all_features.parquet
Feature build complete.
```

The row count can be lower than 600: companies incorporated exactly five calendar years ago get `age` 5 and are filtered out by `age > 5`.

**If it fails with `KeyError: "['company_subtype'] not in index"`**, no company in your batch had a subtype, and the feature builder expects the column. This is a [known issue](explanation.md#known-issues). Add the empty column to the raw file and re-run:

```bash
python -c "import pandas as pd, glob; f=max(glob.glob('data/raw/*.parquet'), key=__import__('os').path.getmtime); df=pd.read_parquet(f); df['company_subtype']=df.get('company_subtype'); df.to_parquet(f, index=False)"
```

```bash
python src/feature_build.py
```

Take a look at the result:

```bash
python -c "import pandas as pd; print(pd.read_parquet('data/features/all_features.parquet').head())"
```

You'll see `company_number`, `company_name`, `age`, `industry_code`, `location` and a few more. `industry_code` will read `00000` for every row; that is the other [known issue](explanation.md#known-issues).

## Step 5: Push 20 companies to Notion

1. In Notion, create a database with these properties (names and types must match exactly):

   | Property | Type |
   |---|---|
   | `Name` | Title |
   | `Company` | Text |
   | `Age` | Number |
   | `Status` | Status, with an option named `Gold` |
   | `Industry` | Text |
   | `Location` | Text |

2. Create an internal integration at [notion.so/my-integrations](https://www.notion.so/my-integrations) and copy its token.
3. Open the database, choose **⋯ → Connections**, and add your integration.
4. Copy the database ID: the 32-character string in the database URL before `?v=`.

`score_and_push.py` does not read `.env`, so export the values in your shell:

```bash
export NOTION_TOKEN=your-notion-integration-token
```

```bash
export NOTION_DB_ID=your-database-id
```

Then push:

```bash
python src/score_and_push.py
```

After printing the columns and the first few rows, you'll see 20 lines like:

```
Pushing to Notion: 00001234 LIMITED (Company 00001234)...
Successfully pushed 00001234 LIMITED.
```

Open the database in Notion: there are 20 new pages, each with status `Gold`.

If a line says `Failed to push ... Could not find database with ID`, the integration has not been added to the database (sub-step 3). If it says a property `is not a property that exists`, a property name or type doesn't match the table above.

Every run creates 20 new pages, even for companies already in Notion. Delete test pages before running it again.

## What you built

You ran the whole pipeline by hand:

- `data/raw/` holds each batch straight from Companies House, and `data/logs/seen_companies.parquet` remembers which companies you've already fetched.
- `data/features/all_features.parquet` is your growing master table.
- Your Notion database has 20 companies from that table.

Next:

- Run it nightly without your laptop: [How to run the pipeline in GitHub Actions](howto-github-actions.md).
- Change how many companies get pushed, or which ones: [How to change what gets pushed to Notion](howto-change-notion-output.md).
- Every flag, column and file: [Reference](reference.md).
- Why it's built this way, and its limits: [Explanation](explanation.md).
