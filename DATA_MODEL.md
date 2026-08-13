# Data Model

## Observation

Every accepted observation should eventually serialize with fields equivalent to:

```json
{
  "metric_id": "example",
  "status": "measured",
  "value": 0,
  "unit": "percent",
  "population": "exact population label",
  "geography": "United States",
  "reference_period": "2026-07",
  "release_date": "2026-08-01",
  "retrieved_at": "2026-08-13T19:00:00Z",
  "source_id": "publisher_dataset",
  "source_variable": "exact series/variable identifier",
  "source_url": "https://...",
  "seasonal_adjustment": "seasonally adjusted",
  "methodology_version": "0.1.0-draft",
  "notes": []
}
```

## Status enum

Allowed public status values:

- `measured`
- `estimated`
- `experimental`
- `stale`
- `unavailable`
- `prelaunch`

Do not invent ambiguous status words per connector.

## Population anchor

The Bottom-30 population anchor additionally stores:

- survey year;
- income reference year;
- percentile;
- cutoff;
- valid record count;
- excluded record count;
- relative survey weight total;
- source archive hash;
- calculation timestamp.

## Vintages

A published vintage should contain:

```json
{
  "published_at": "...",
  "methodology_version": "...",
  "application_version": "...",
  "observations": {},
  "population_anchor": {},
  "data_health": {},
  "source_vintages": {}
}
```

## Revision

A revision record should identify:

```json
{
  "original_vintage": "...",
  "revised_at": "...",
  "source_id": "...",
  "reason": "...",
  "before": {},
  "after": {},
  "methodology_changed": false
}
```

Never mutate old data in place without enough metadata to reconstruct what happened.
