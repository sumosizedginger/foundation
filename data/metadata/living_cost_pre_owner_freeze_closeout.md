# Pre-owner-freeze closeout (current)

Current HEAD at write time is recorded in git. This file is the current
project-status closeout for the living-cost evidence layer.

**NOT an owner freeze. OD-001 through OD-013 remain pending.**

**NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.**

No Gap, Adequacy Ratio, state living-cost rankings, national living-cost
median, or Composite was calculated or published.
`living_cost_release_authorized = false`. `states_modeled = 0`.

Stale Deliverable 2A snapshot (SHA `b2a30ef…`, obsolete CI majors, 73 tests,
Connecticut unmatched, outdated CMS/health_premium): archived at
`data/metadata/historical/living_cost_deliverable_2a_report.md`.
That file is **NOT current project status**.

## What is accepted from the correction pass

- Canonical CPS 2025 ASEC SHA
  `318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b`
  is the active artifact. Legacy hash is ledger-only.
- 2024 HUD/ACS source hashes recorded on the geo-join report.
- Raw ACS county-equivalents 3144 vs FY2024 join universe 3143.
- 100% 50-state+DC 2024 housing population coverage.
- Oregon individual-market source = federal Exchange PUF (2024 and 2026).
- 19 standalone SBE individual markets in 2024; 21 in 2026.
- Real SBE lowest-Silver joins on standalone SBE states.
- Oklahoma 2024 governance is HealthCare.gov/FFM, **not** SBE-FP.
  Oklahoma SBE-FP is effective May 1, 2026 (official CMS).
  Arkansas and Oregon remain SBE-FP in 2024 and 2026.
  Individual-market data source for OK/AR/OR remains federal Exchange PUF.
- BLS CE maintenance candidates from official VQB/MTBI. Combined mean
  including zeros is measured from VQB, not a $1 fuel residual.
- CE evidence status is `INCOMPLETE_PROVENANCE` (official retrieve 403).
  Methodology status is `OWNER_REVIEW_PENDING` (OD-007). Those are
  different dimensions. The candidate is not a guessed estimate and is
  not VALIDATED.

## Owner decisions (labels from the canonical owner packet)

Do not change the OD definitions. These labels match
`living_cost_owner_decisions_pending.md`:

- OD-001 — ACS adult-population vintage for 2024 and 2026 weights
- OD-002 — MEPS OOP statistic
- OD-003 — NHTS observed vs minimum-necessary mileage
- OD-004 — EPA MPG cohort
- OD-005 — vehicle replacement
- OD-006 — NAIC auto insurance measure
- OD-007 — vehicle maintenance/repairs/tires annualization
- OD-008 — recreation percentile
- OD-009 — connectivity / mobile price
- OD-010 — lag / CPI translation method
- OD-011 — municipal earned-income tax geography/overlay
- OD-012 — additional resilience reserve
- OD-013 — Connecticut HUD/ACS geography treatment

None are ACCEPTED.

## CI reporting rule

GitHub Actions results are reported from GitHub after push.
Local pytest counts are labeled LOCAL and are not GitHub CI.

## Next task

OWNER FREEZE of OD-001 through OD-013.
