# ASEARCH

ASEARCH finds established UK companies and drops them into Notion. Every night it pulls up to 600 active companies at least five years old from the Companies House API, builds a small feature table (age, industry code, location), and creates Notion pages for 20 of them.

```
ch_ingest.py ──► data/raw/*.parquet ──► feature_build.py ──► data/features/all_features.parquet ──► score_and_push.py ──► Notion
```

| Stage | Script | Workflow |
|---|---|---|
| Fetch companies | `src/ch_ingest.py` | `Nightly CH ingest` (00:00 UTC) |
| Build features | `src/feature_build.py` | `Feature build` (after ingest) |
| Push to Notion | `src/score_and_push.py` | `Score & push to Notion` (after feature build) |

## Quick start

```bash
python3.12 -m venv .venv
```

```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
```

Put `CH_API_KEY=...` in a `.env` file, then:

```bash
python src/ch_ingest.py --out data/raw
```

```bash
python src/feature_build.py
```

Export `NOTION_TOKEN` and `NOTION_DB_ID` in your shell, then:

```bash
python src/score_and_push.py
```

The [tutorial](docs/tutorial-first-run.md) walks through each step, including the Notion database setup.

## Documentation

| Doc | Read it when you want to |
|---|---|
| [Tutorial: your first local run](docs/tutorial-first-run.md) | Run the whole pipeline yourself for the first time. |
| [How to run the pipeline in GitHub Actions](docs/howto-github-actions.md) | Set up secrets and the nightly schedule. |
| [How to change what gets pushed to Notion](docs/howto-change-notion-output.md) | Change the count, the selection, or the Notion properties. |
| [Reference](docs/reference.md) | Look up a flag, env var, column, file or workflow. |
| [Explanation](docs/explanation.md) | Understand the design, its trade-offs, and its known issues. |

## Known issues

- In CI nothing persists between runs, so the same companies can be pushed to Notion repeatedly.
- `Feature build` and `Score & push to Notion` are skipped when started by hand. Start from `Nightly CH ingest`.
- Failed Notion pushes don't fail the job.

Run the offline feature-build check with `python tests/test_feature_build.py`.

Details and causes: [Explanation: known issues](docs/explanation.md#known-issues).
