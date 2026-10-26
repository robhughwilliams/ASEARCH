# How to change what gets pushed to Notion

Change how many companies `src/score_and_push.py` sends, which ones it picks, or which Notion properties it fills in.

## Prerequisites

- A working local setup and a feature table at `data/features/all_features.parquet`. The [tutorial](tutorial-first-run.md) gets you there.
- A **test** Notion database with the same schema as your real one. Every run creates new pages and nothing deduplicates them, so test against a throwaway database by pointing `NOTION_DB_ID` at it.

## Change how many companies are pushed

Edit the `head(20)` call in `src/score_and_push.py`:

```python
top20 = df_sorted.head(20)
```

Change `20` to the count you want, for example `head(50)`.

## Change which companies are picked

The script currently sorts by name and takes the first rows:

```python
df_sorted = df.sort_values('company_name', ascending=True, na_position='last')
```

Replace that line with a different filter or sort over the [feature columns](reference.md#feature-columns). Examples:

Oldest companies first:

```python
df_sorted = df.sort_values('age', ascending=False, na_position='last')
```

Only companies registered in London, oldest first:

```python
df_sorted = df[df['location'] == 'London'].sort_values('age', ascending=False)
```

Don't filter on `industry_code` yet. It is `00000` for every row until the [SIC code bug](explanation.md#known-issues) is fixed.

## Add or change a Notion property

1. Add the property to your Notion database first (for example a Text property called `Created`).
2. Add a matching entry to the `properties` dict in the loop:

   ```python
   "Created": {"rich_text": [{"text": {"content": str(row['date_of_creation'])}}]},
   ```

   The key must match the Notion property name exactly, and the value shape must match its type: `title` for the title property, `rich_text` for Text, `number` for Number, `status` for Status.

To change the fixed status, edit:

```python
"Status": {"status": {"name": "Gold"}},
```

The new name must be an existing option on the `Status` property.

## Verification

```bash
export NOTION_DB_ID=your-test-database-id
```

```bash
python src/score_and_push.py
```

Every company should print `Successfully pushed ...`, and the test database should show the expected number of new pages with the new values filled in.

## Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `Failed to push ... <property> is not a property that exists` | Property name in the dict doesn't match Notion. | Fix the spelling or capitalisation in either place. |
| `Failed to push ...` with a validation error naming a property | Value shape doesn't match the property type (for example `rich_text` for a Number property). | Use the shape for that type, as listed in step 2. |
| `Failed to push ...` with a validation error naming `Status` | The status name isn't an option on the `Status` property. | Add the option in Notion, or use an existing one. |
| `KeyError: '<column>'` | You referenced a column that isn't in `all_features.parquet`. | Pick from the [feature columns](reference.md#feature-columns), or add it in `build_features_for_df`. |
| `No companies found to push to Notion.` | Your filter matched nothing. | Loosen the filter. Check values with `python -c "import pandas as pd; print(pd.read_parquet('data/features/all_features.parquet')['location'].value_counts().head())"`. |

## Related

- [Reference: `score_and_push.py`](reference.md#srcscore_and_pushpy)
- [Explanation: alphabetical "score"](explanation.md#trade-offs)
