# Automation Contract

## Trigger phrase

The intended human workflow is:

> Update The Foundation.

The maintainer agent should interpret that as the workflow below.

## Phase 1 — Orient

1. Read `AGENT.md`.
2. Read `DECISIONS.md`.
3. Inspect Git status.
4. Refuse to overwrite unrelated uncommitted user work.
5. Read current data/source state.

## Phase 2 — Check sources

For each enabled source:

1. determine expected/latest release;
2. check whether a newer valid source release exists;
3. fetch only from approved source locations;
4. record HTTP/source metadata;
5. hash raw downloads;
6. validate schema.

If there is no new release, record "no change."

## Phase 3 — Research only when needed

Research is required when:

- a schema changes;
- a variable/series disappears;
- source methodology changes;
- release cadence changes;
- source documentation contradicts current config;
- a new official source is proposed.

Research does not authorize methodology changes.

## Phase 4 — Calculate

Run deterministic pipeline.

At minimum:

```bash
pytest
foundation validate
foundation update
python scripts/build_site.py
```

Exact CLI commands may evolve; update this document if the approved workflow changes.

## Phase 5 — Compare

Compare to prior valid vintage:

- cutoff movement;
- metric movement;
- freshness;
- missingness;
- source revisions;
- unusually large changes.

Large movement requires source and calculation review before publication.

## Phase 6 — Validate

Run:

- unit tests;
- schema tests;
- source metadata validation;
- JSON validation;
- no-secret scan where available;
- static site smoke test.

## Phase 7 — Publish

Only if all required gates pass:

1. write new current data atomically;
2. add immutable history entry if publication state warrants it;
3. build static site;
4. commit intentional files;
5. push;
6. confirm GitHub Pages deployment.

During prelaunch, deployment may show new research observations but must retain prelaunch labeling.

## Phase 8 — Report

Return a concise report:

```text
FOUNDATION UPDATE

New releases:
- ...

No new release:
- ...

Bottom-30 cutoff:
- measured reference year:
- measured value:
- current-dollar estimate, if enabled:

Candidate metrics changed:
- ...

Data health:
- ...

Tests:
- X passed
- Y failed

Warnings:
- ...

Files changed:
- ...

Commit:
- ...

Deploy:
- ...
```

## Fail-closed examples

### BLS series missing
Do not pick another series.

### Census column renamed
Research official documentation, then update connector only if semantic equivalence is verified.

### Redfin unavailable
Do not scrape around it or replace with Zillow without approval.

### One test fails
No official result publication.

### Weird result
Investigate. Do not adjust a weight or filter until the result "looks right."

## Scheduling

V0.1 is owner-triggered.

Scheduled automatic updates may be introduced only after:

- manual update workflow is trusted;
- error reporting is reliable;
- source failures fail closed;
- no methodology change can be auto-approved.
