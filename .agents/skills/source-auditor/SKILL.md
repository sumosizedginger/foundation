---
name: source-auditor
description: Audits an economic data source for The Foundation. Use when a series, variable, schema, release cadence, unit, population definition, URL, or source methodology is new, changed, missing, or uncertain.
---

# Source Auditor

## Objective

Establish exactly what a source measures before production code consumes it.

## Process

1. Identify the original publisher.
2. Locate current official technical documentation.
3. Record:
   - dataset/series/variable name;
   - identifier;
   - population universe;
   - geography;
   - reference period;
   - release cadence;
   - seasonal adjustment;
   - unit and scale;
   - revision policy;
   - missing/sentinel codes;
   - methodological breaks;
   - allowed access/reuse considerations.
4. Compare the finding with:
   - `DATA_SOURCES.md`;
   - `config/sources.yml`;
   - `config/indicators.yml`;
   - existing connector.
5. Determine one of:
   - semantically unchanged;
   - compatible but implementation changed;
   - materially changed;
   - uncertain.
6. For material/uncertain changes, do not modify methodology. Escalate.

## Source priority

Primary government/first-party documentation outranks:

- news;
- blogs;
- aggregators;
- old code comments;
- model memory.

## Output

Provide a concise audit memo with links and explicit confidence.

Do not say "looks equivalent" without naming the definitions compared.
