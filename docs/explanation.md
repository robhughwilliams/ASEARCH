# How the pipeline is put together

ASEARCH exists to put a steady trickle of established UK companies (active, five or more years old) in front of you in Notion, without anyone running a script by hand. This page explains why it is split the way it is, what each choice costs, and where the current design falls short. For exact flags, columns and file names, see the [reference](reference.md).

## The problem

Companies House has millions of company records. Pulling them in one go is slow, hits API limits, and dumps far more rows into Notion than anyone will read. What you want is a small, fresh batch each night, with enough derived detail (age, industry, location) to triage it, landing somewhere you already work.

## The approach

Three scripts, each owning one job and one file boundary:

```
                    GitHub Actions (nightly, 00:00 UTC)
 ┌───────────────────┐  raw_companies  ┌───────────────────┐  features   ┌────────────────────┐
 │ Nightly CH ingest │ ──────────────► │   Feature build   │ ──────────► │ Score & push to    │
 │ src/ch_ingest.py  │    artifact     │ src/feature_build │  artifact   │ Notion             │
 └─────────┬─────────┘                 └─────────┬─────────┘             │ src/score_and_push │
           │                                     │                       └─────────┬──────────┘
           ▼                                     ▼                                 ▼
 data/raw/companies_active_5y_<cutoff>   data/features/all_features        20 new Notion pages
 data/logs/seen_companies                data/features/features_<cutoff>
```

- **Ingest** talks to the outside world and nothing else. It asks the advanced-search endpoint for active companies incorporated before the cutoff, skips any `company_number` already in the seen log, and stops at 600.
- **Feature build** is pure pandas. It reads the newest raw file, computes `age`, `industry_code` and `location`, and folds the batch into a master table de-duplicated on `company_number`.
- **Push** reads the master table and writes 20 rows to Notion.

Parquet sits between every stage. Each stage can be re-run on its own, and you can open any intermediate file in pandas to see exactly what the next stage will get.

In CI, each stage is its own workflow, chained with `workflow_run` and passing files as artifacts. A failure in one stage stops the ones after it, and each stage shows up as a separate run in the Actions tab.

## Trade-offs

**Separate workflows over one job.** You get isolated logs and the option to re-run a single stage. You pay with artifact plumbing: a third-party action (`dawidd6/action-download-artifact`) to fetch files across workflows, `actions: read` permission, and a chain that silently breaks if a workflow's `name:` changes. The git history shows most of the debugging effort went here (several commits fixing triggers and artifact downloads).

**Seen log over date windows.** Ingest de-duplicates by remembering every company number it has written, rather than asking only for companies incorporated on a given day. That makes batch size predictable (always up to 600) at the cost of a state file that has to persist somewhere.

**Calendar-year age.** `age` is `this year - incorporation year`. It is cheap and stable across a year, but it is off by up to a year. Combined with the `age > 5` filter, companies incorporated exactly five calendar years ago are dropped even though ingest selected them.

**First-row-wins merge.** When a company is already in `all_features.parquet`, the stored row is kept and the new one discarded. Old rows never get updated ages or details.

**Alphabetical "score".** The push step takes the first 20 names alphabetically. It is a placeholder for real ranking. In practice it favours names starting with digits (for example `06718888 LIMITED`), because digits sort before letters.

## CI has no memory

`data/` is in `.gitignore`, and no workflow commits files or restores state from a previous run. So in GitHub Actions:

- the seen log starts empty every night, so de-duplication only works across **local** runs;
- `all_features.parquet` is just that night's batch, not a growing master;
- the cutoff date moves by one day each night, but the query starts at `start_index=0` every time, so nothing stops the same companies coming back on consecutive nights;
- push has no check against existing Notion pages.

So the scheduled pipeline can create duplicate Notion pages. Fixing this needs somewhere durable for the seen log, such as committing it back to the repo, caching it with `actions/cache`, or checking Notion for an existing `Company` value before creating a page.

## Known issues

These come from reading the code and running it against the local data in `data/`, checked 2026-10-26.

1. **Manual runs of the downstream workflows are skipped.** `feature_build.yml` and `score.yml` only run when `github.event.workflow_run.conclusion == 'success'`, which is never true for `workflow_dispatch`.
2. **`--out` and `--days` do nothing** in `ch_ingest.py`. Output always goes to `data/raw/`.
3. **Raw file names carry the cutoff date, not the run date.** A file named `..._2020-06-05.parquet` was produced on 2025-06-04.
4. **Notion errors don't fail the job.** Failed pages go to stderr, but `score_and_push.py` still exits 0, so the workflow shows green.

### Fixed

- **`industry_code` was always `00000`** (fixed 2026-10-26). Pandas reads list columns back from Parquet as `numpy.ndarray`, and the code only accepted a Python `list`. It now accepts both. A local `all_features.parquet` built before the fix still holds `00000` for those companies, because the merge keeps the stored row. To rebuild it, delete `data/features/all_features.parquet` and re-run `python src/feature_build.py` once per raw file, touching each file first (`touch data/raw/<file>`) so it becomes the newest. CI rebuilds from scratch every night, so it needs nothing.
- **Feature build crashed when a batch had no `company_subtype`** (fixed 2026-10-26). `json_normalize` only creates columns that appear in the API response, so the column was missing and selection raised `KeyError`. `build_features_for_df` now adds an empty column first.

`tests/test_feature_build.py` covers both.

## Alternatives considered

From the git history:

- Ingest first used a different Companies House endpoint and got 404s; it moved to `advanced-search/companies` (commit `860faad`).
- The pipeline started as one workflow and was split into three (`411cb9d`, "Re-split workflows").
- `actions/download-artifact@v4` could not fetch artifacts from a different workflow run as configured, so it was replaced with `dawidd6/action-download-artifact@v6` (`541f1b0`).
- `python-dotenv` was removed from `score_and_push.py` for GitHub Actions compatibility (`4446dbb`). It is still used in `ch_ingest.py`.

## Related

- [Reference](reference.md)
- [Tutorial: your first local run](tutorial-first-run.md)
- [How to run the pipeline in GitHub Actions](howto-github-actions.md)
