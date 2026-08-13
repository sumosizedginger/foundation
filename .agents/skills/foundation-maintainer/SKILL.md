---
name: foundation-maintainer
description: Maintains The Foundation economic-data project. Use for updating official source data, running deterministic calculations, validating results, building the static site, inspecting anomalies, and preparing verified Git changes.
---

# Foundation Maintainer

Read `AGENT.md` before doing anything substantial.

## Use this skill when

- the owner says "Update The Foundation";
- source data need refreshing;
- the pipeline or site needs maintenance;
- a deployment/update failed;
- a new accepted metric needs implementation.

## Operating sequence

1. Read `DECISIONS.md`, `METHODOLOGY.md`, `VALIDATION.md` and `AUTOMATION.md`.
2. Inspect Git status and preserve unrelated user work.
3. Run configuration validation and tests.
4. Check only registered/approved sources.
5. Download new official source releases.
6. Validate source schema and metadata.
7. Run deterministic calculations.
8. Compare with prior valid values.
9. Investigate abnormal movement.
10. Run complete tests again.
11. Build static site.
12. Verify generated JSON and pages.
13. Inspect Git diff.
14. Commit/push only if configured and all publication-critical checks pass.
15. Report new data, no-change sources, warnings, tests, diff and deployment.

## Stop conditions

Stop and ask the owner when:

- methodology meaning must change;
- a source must be substituted;
- an indicator/weight must be added or changed;
- current official documentation conflicts with `METHODOLOGY.md`;
- a result cannot be reconciled after investigation;
- a source's automated-use terms are uncertain;
- a destructive Git operation appears necessary.

## Required rule

Never make the economy look better or worse.

Make the measurement more defensible.
