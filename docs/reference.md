# Reference

ASEARCH is a three-stage batch pipeline. It pulls active UK companies that are at least five years old from the Companies House API, derives a small feature table, and pushes 20 of them into a Notion database. Each stage is a standalone Python script under `src/` and a GitHub Actions workflow under `.github/workflows/`.

```
ch_ingest.py ──► data/raw/*.parquet ──► feature_build.py ──► data/features/all_features.parquet ──► score_and_push.py ──► Notion
```

All paths are relative to the current working directory, so run every script from the repository root.

## Environment variables

| Variable | Used by | Required | Meaning |
|---|---|---|---|
| `CH_API_KEY` | `ch_ingest.py` | Yes (the API rejects the request without it and the script raises `HTTPError`) | Companies House REST API key. Sent as the HTTP Basic auth username with an empty password. |
| `NOTION_TOKEN` | `score_and_push.py` | Yes (script raises `EnvironmentError` at import if unset) | Notion internal integration token. |
| `NOTION_DB_ID` | `score_and_push.py` | Yes (same check as above) | ID of the target Notion database. |

`ch_ingest.py` calls `load_dotenv()`, so it reads a local `.env` file. `score_and_push.py` does **not** (the `dotenv` lines are commented out), so export `NOTION_TOKEN` and `NOTION_DB_ID` in your shell before running it locally. `.env` is listed in `.gitignore`.

## `src/ch_ingest.py`

Fetches up to 600 active companies incorporated on or before a cutoff date (today minus 5 × 365 days) that are not already in the seen log.

### CLI

```bash
python src/ch_ingest.py --out data/raw [--days N]
```

| Flag | Type | Default | Effect |
|---|---|---|---|
| `--out` | string | none, **required** | Accepted but ignored. Output always goes to `data/raw/`. |
| `--days` | int | `1` | Accepted but ignored ("kept for CLI symmetry"). |

### API call

`GET https://api.company-information.service.gov.uk/advanced-search/companies` with:

| Param | Value |
|---|---|
| `company_status` | `active` |
| `size` | `600` |
| `incorporated_from` | `1900-01-01` |
| `incorporated_to` | cutoff date, `YYYY-MM-DD` |
| `start_index` | `0`, then `600`, `1200`, ... |

It pages until it has 600 unseen companies or a page comes back with no `items`. Any non-2xx response raises `requests.HTTPError` and the script exits non-zero.

### Functions

| Function | Signature | Behaviour |
|---|---|---|
| `load_seen_companies` | `() -> pd.Series` | Reads `company_number` from `data/logs/seen_companies.parquet`, or returns an empty `Series` if the file does not exist. |
| `save_seen_companies` | `(seen_series: pd.Series) -> None` | De-duplicates and overwrites the seen log. |
| `fetch_new_companies` | `(five_years_ago: str, seen: pd.Series, limit: int = 600) -> pd.DataFrame` | Pages the API and drops rows whose `company_number` is in `seen`. Returns an empty DataFrame if nothing new was found. |
| `main` | `(days, out)` | Runs the above and writes output. Both arguments are unused. |

### Outputs

| File | Contents |
|---|---|
| `data/raw/companies_active_5y_<cutoff>.parquet` | The new batch, flattened with `pd.json_normalize`. `<cutoff>` is the incorporation cutoff date, **not** the run date. Two runs on the same day overwrite the same file. |
| `data/logs/seen_companies.parquet` | One column, `company_number`, holding every company ever written. |

If no new companies are found it prints `No new active companies found up to <cutoff>`, writes nothing, and exits 0.

Raw columns come straight from the API response, so they vary by batch. Seen in practice: `company_name`, `company_number`, `company_status`, `company_type`, `company_subtype` (not always present), `kind`, `date_of_creation`, `sic_codes`, `links.company_profile`, `registered_office_address.{address_line_1, address_line_2, locality, region, postal_code, country}`.

## `src/feature_build.py`

Turns the newest raw file into feature rows and merges them into a master table.

### CLI

```bash
python src/feature_build.py
```

No arguments.

### Functions

| Function | Signature | Behaviour |
|---|---|---|
| `find_latest_raw` | `() -> Path` | Returns the `data/raw/companies_active_5y_*.parquet` file with the newest **modification time**. Raises `FileNotFoundError` if there are none. |
| `build_features_for_df` | `(df: pd.DataFrame) -> pd.DataFrame` | Derives features (below), keeps rows where `age > 5 and company_status == 'active'`, sorts by `company_name`. Raises `KeyError` if any selected column, including `company_subtype`, is missing from the raw batch. |
| `main` | `() -> None` | Runs the steps below. |

### Feature columns

| Column | Type | Derivation |
|---|---|---|
| `company_number` | str | Copied. |
| `company_name` | str | Copied. |
| `company_status` | str | Copied. |
| `company_type` | str | Copied (for example `ltd`). |
| `company_subtype` | str or null | Copied. |
| `date_of_creation` | str `YYYY-MM-DD` | Copied. |
| `age` | int | `current calendar year - year(date_of_creation)`. A year difference, not exact days, so a company incorporated in 2021 has `age` 5 in 2026 and is dropped by the `age > 5` filter. |
| `industry_code` | str, 5 chars | First SIC code, truncated to 5 characters, or `"00000"`. See [known issues](explanation.md#known-issues): this is currently always `"00000"`. |
| `location` | str | `registered_office_address.locality`, or `""`. |

### Outputs

| File | Contents |
|---|---|
| `data/features/features_<cutoff>.parquet` | This batch's features only (a debug copy). `<cutoff>` comes from the raw filename. |
| `data/features/all_features.parquet` | Master table: previous master + this batch, de-duplicated on `company_number`. The existing row wins, so a company's `age` is never refreshed once stored. |

If the batch is empty after filtering, it prints `No features to add (empty after filtering).` and writes nothing.

## `src/score_and_push.py`

Pushes 20 companies from the master feature table into Notion. Despite the name, it does no scoring: it sorts by `company_name` ascending (nulls last) and takes the first 20.

### CLI

```bash
python src/score_and_push.py
```

No arguments. Reads `data/features/all_features.parquet`. All work happens at import time (there is no `main()`), so importing the module runs the push.

### Notion database schema

The target database must have these properties, with these exact names and types:

| Property | Notion type | Value written |
|---|---|---|
| `Name` | Title | `company_name` |
| `Company` | Text | `company_number` |
| `Age` | Number | `age` (or empty) |
| `Status` | Status | Always `Gold`. The status option `Gold` must exist. |
| `Industry` | Text | `industry_code` |
| `Location` | Text | `location` |

Each company becomes a new page via `notion.pages.create`. There is no check for existing pages, so re-running creates duplicates. A failed page logs `Failed to push <name> (Company <number>): <error>` to stderr and the loop continues; the script still exits 0. If the table is empty it prints `No companies found to push to Notion.` and exits 0.

## GitHub Actions workflows

| File | Workflow name | Trigger | Runs | Inputs | Outputs (artifact, 7-day retention) |
|---|---|---|---|---|---|
| `ingest.yml` | `Nightly CH ingest` | cron `0 0 * * *` (00:00 UTC, 01:00 London in summer), `workflow_dispatch` | `python src/ch_ingest.py --out data/raw` | secret `CH_API_KEY` | `raw_companies` = `data/raw/*.parquet` |
| `feature_build.yml` | `Feature build` | `workflow_run` of `Nightly CH ingest` (completed), `workflow_dispatch` | `python src/feature_build.py` | artifact `raw_companies` from `ingest.yml` | `features` = `data/features/all_features.parquet` |
| `score.yml` | `Score & push to Notion` | `workflow_run` of `Feature build` (completed), `workflow_dispatch` | `python src/score_and_push.py` | artifact `features` from `feature_build.yml`, secrets `NOTION_TOKEN`, `NOTION_DB_ID` | none |

Details that matter:

- `feature_build.yml` and `score.yml` match the upstream workflow by its **name** (`Nightly CH ingest`, `Feature build`). Renaming a workflow breaks the chain.
- Both downstream jobs have `if: github.event.workflow_run.conclusion == 'success'`. On a manual `workflow_dispatch` there is no `workflow_run` event, so the job is **skipped**. Only `ingest.yml` can usefully be run by hand.
- Cross-workflow artifact download uses `dawidd6/action-download-artifact@v6`, which needs `permissions: actions: read`.
- Ingest installs `requirements.txt`. Feature build installs only `pandas pyarrow duckdb`; score installs only `pandas pyarrow notion-client`. All use Python 3.12.
- `data/` is git-ignored, so the seen log and master feature table are **not** carried between CI runs. See [explanation](explanation.md#ci-has-no-memory).

## Tests

`tests/test_workflow.py` has two smoke tests that shell out to the scripts and assert exit code 0:

| Test | Runs | Side effects |
|---|---|---|
| `test_feature_build` | `python src/feature_build.py` | Writes to `data/features/`. |
| `test_score_and_push` | `python src/score_and_push.py` | Creates 20 **real** pages in your Notion database. |

## Related

- [Tutorial: your first local run](tutorial-first-run.md)
- [How to run the pipeline in GitHub Actions](howto-github-actions.md)
- [How to change what gets pushed to Notion](howto-change-notion-output.md)
- [Explanation: how the pipeline is put together](explanation.md)
