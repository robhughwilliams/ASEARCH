# How to run the pipeline in GitHub Actions

Set up the repository so the three workflows run every night at 00:00 UTC and push 20 companies to Notion.

## Prerequisites

- Push access to the repository on GitHub, and the `gh` CLI signed in (`gh auth status`).
- A Companies House API key, a Notion integration token, and a Notion database ID with the schema from the [reference](reference.md#notion-database-schema). The [tutorial](tutorial-first-run.md#step-5-push-20-companies-to-notion) walks through creating them.
- The workflows on the repository's default branch. Scheduled (`cron`) and `workflow_run` triggers only fire from workflow files on the default branch, which is `main` here.

## Steps

1. Add the three repository secrets:

   ```bash
   gh secret set CH_API_KEY
   ```

   ```bash
   gh secret set NOTION_TOKEN
   ```

   ```bash
   gh secret set NOTION_DB_ID
   ```

   Each command prompts for the value, so it doesn't land in your shell history.

2. Check the secrets are there:

   ```bash
   gh secret list
   ```

   You should see `CH_API_KEY`, `NOTION_DB_ID` and `NOTION_TOKEN`.

3. Start the chain by running the ingest workflow by hand:

   ```bash
   gh workflow run ingest.yml
   ```

   When it succeeds, `Feature build` starts on its own, and when that succeeds, `Score & push to Notion` starts.

   Don't start `feature_build.yml` or `score.yml` by hand. Their jobs only run when triggered by the upstream workflow, so a manual run shows as skipped. Always start from `ingest.yml`.

4. Leave it. From now on `Nightly CH ingest` runs at 00:00 UTC every day and the other two follow.

## Verification

```bash
gh run list --limit 6
```

You should see one run each of `Nightly CH ingest`, `Feature build` and `Score & push to Notion`, all `completed` / `success`. Then check Notion for 20 new pages with status `Gold`.

To read a run's output:

```bash
gh run view --log
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `Feature build` or `Score & push to Notion` shows **skipped** | It was started with `workflow_dispatch`, or the upstream run failed. | Start from `gh workflow run ingest.yml`. If upstream failed, fix that first. |
| Downstream workflow never starts | The `workflows:` name in `feature_build.yml` / `score.yml` no longer matches the upstream `name:`, or the files aren't on `main`. | Keep `name: Nightly CH ingest` and `name: Feature build` in sync with the `workflow_run.workflows` lists. Merge to `main`. |
| Ingest fails with `HTTPError: 401` | `CH_API_KEY` secret missing or wrong. | `gh secret set CH_API_KEY` again. |
| Feature build fails with `FileNotFoundError: No raw files` | The `raw_companies` artifact was not found (expired after 7 days, or ingest uploaded nothing because it found no new companies). | Re-run `ingest.yml`. |
| Score job is green but Notion has no new pages | Notion errors are logged to stderr without failing the job. | Search the run log for `Failed to push`. Usually the integration isn't connected to the database, or a property name doesn't match. |
| Score fails with `EnvironmentError: NOTION_TOKEN or NOTION_DB_ID is not set` | Secret missing. | `gh secret set` the missing one. |
| The same companies show up in Notion night after night | CI keeps no seen log between runs. See [CI has no memory](explanation.md#ci-has-no-memory). | Known limitation; needs a persisted seen log or a Notion lookup before creating pages. |

## Related

- [Reference: workflows](reference.md#github-actions-workflows)
- [Explanation: CI has no memory](explanation.md#ci-has-no-memory)
