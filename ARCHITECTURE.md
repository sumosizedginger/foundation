# System Architecture

## 1. Design objective

Build a deterministic economic-data pipeline with a static public presentation layer and agent-assisted operations.

The agent may research, maintain and repair the machine.

The agent must not be the machine.

## 2. High-level flow

```text
Official sources
      |
      v
Source connectors
      |
      v
Raw-download validation + metadata + SHA-256
      |
      v
Canonical observations / microdata transforms
      |
      v
Calculation layer
      |
      +--> Bottom-30 population anchor
      +--> candidate structural metrics
      +--> Daily Pressure observations
      +--> data-health metadata
      |
      v
Validation gates
      |
      v
Versioned JSON outputs
      |
      v
Static site build
      |
      v
Browser/static verification
      |
      v
GitHub Pages
```

## 3. Separation of responsibility

### `config/`
Machine-readable definitions, sources, candidates and provisional weights.

### `src/foundation/sources/`
Network/source-specific acquisition only.

These modules should know how to fetch/parse a publisher.

They should not decide what constitutes a healthy economy.

### `src/foundation/`
Canonical calculations, validation, models and export.

### `tests/`
Synthetic and regression tests.

### `data/current/`
Latest valid generated state.

### `data/history/`
Immutable published vintages.

### `data/revisions/`
Explicit revision records.

### `site/`
Static presentation.

The site may format, filter, sort and visualize.

The site may not calculate official economic values.

### `.agents/skills/`
Agent operating procedures.

## 4. No required database

V0.1 uses versioned JSON/CSV outputs and Git history.

A database is not justified yet.

Introduce one only when data size/query needs prove the requirement.

## 5. Raw data policy

Large source files, especially CPS ASEC, are downloaded during processing and may be cached locally/CI.

Do not commit giant raw files merely to prove they exist.

Persist:

- source URL;
- retrieval time;
- file hash;
- expected filename/archive contents;
- source/reference year;
- code version;
- produced results.

This gives reproducibility without bloating Git.

## 6. Atomic publication

Generated public JSON must be written to a temporary path, validated, and atomically replaced.

A partially written update may never become `latest.json`.

## 7. Versioning

Track separately:

- application version;
- methodology version;
- data/source vintage.

A code refactor that does not change results should not imply a methodology change.

## 8. Network failure

Connectors must support:

- clear timeouts;
- retry for transient failures;
- no infinite retry;
- HTTP status validation;
- content-type/size sanity checks;
- hash generation;
- source URL recording.

A connector may return `unavailable`.

It may not fabricate an observation.

## 9. Agent workflow

Antigravity is used as:

- maintainer;
- researcher;
- debugger;
- test runner;
- browser verifier;
- Git operator.

Core calculations remain Python functions that can run without an LLM.

## 10. Deployment

Target: GitHub Pages.

Recommended deployment boundary:

```text
site/
  index.html
  methodology.html
  sources.html
  history.html
  assets/
  data/
```

`scripts/build_site.py` copies validated generated JSON into `site/data/`.

GitHub Actions uploads `site/` as the Pages artifact.

## 11. Security

No secrets are needed for the canonical CPS ASEC download.

Any future optional API keys must be environment variables/GitHub secrets.

Never place credentials in source config.

See `SECURITY.md`.

## 12. Future scale

Potential later additions:

- DuckDB for historical query performance;
- Parquet for larger derived datasets;
- regional versions;
- methodology simulation;
- public downloadable research extracts;
- automated release notes.

Do not introduce these until V0.1 requires them.
