# THE FOUNDATION — STATUS WRITE-UP
## Pre-owner-freeze work is implemented. Owner freeze is NOT COMPLETED.

Repository: https://github.com/sumosizedginger/foundation

**This file is current status, not a new work order.**
Anything still open is marked **NOT COMPLETED**.

---

## Verdict

Two successive passes on top of audited HEAD `e497d451088a054d43fda9921aa699531077888a`
are implemented, dual-verified, pushed, and CI-green.

| Pass | SHA | What it was |
|---|---|---|
| Audited start | `e497d451088a054d43fda9921aa699531077888a` | Post-correction-pass audit baseline |
| Evidence correction | `94362d8bcd7f4e9ef08a44cb436619c9b9647a6c` | Provenance, CMS map, CPS SHA, VQB maintenance |
| **Current HEAD** | `77edf3f3ae032e85b338ba4b6398486ff767d97d` | OK 2024 not SBE-FP; coverage semantics; 2A archive; OD labels |

**NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.**

Not calculated, not published:

- 2024 MSLC
- 2026 MSLC
- Gap
- Adequacy Ratio
- state living-cost rankings
- national living-cost median
- Composite

`living_cost_release_authorized = false`  
`states_modeled = 0`

**Owner freeze is NOT COMPLETED.** OD-001 through OD-013 remain pending. None ACCEPTED.

Current living-cost closeout:
`data/metadata/living_cost_pre_owner_freeze_closeout.md`

---

## GitHub CI on current HEAD `77edf3f` (not local)

| Workflow | Result | Run |
|---|---|---|
| Tests & Code Quality | **success — 97 passed, 5 skipped, 1 warning** | https://github.com/sumosizedginger/foundation/actions/runs/31851900912 |
| Validate Living Cost Sources | **success** | https://github.com/sumosizedginger/foundation/actions/runs/31851900879 |
| Deploy Pages | **success** | https://github.com/sumosizedginger/foundation/actions/runs/31851900877 |

Pre-cleanup GitHub baseline was 94 passed / 5 skipped / 1 warning.

LOCAL pytest (cached artifacts; **not** GitHub CI): 102 passed, 1 warning.

Dual verifiers on `77edf3f` (harness `9dbd0dbca1ef`): both PASS, nits only.

---

## COMPLETED — cleanup pass (`77edf3f`)

### 1. Oklahoma 2024 CMS governance — COMPLETED

Official CMS State-based Exchanges page (updated 2026-08-13): PY2026 SBE-FPs are
Arkansas, Oregon, and **Oklahoma (Effective May 1, 2026)**.

| Year | OK platform | OK individual-market source |
|---|---|---|
| 2024 | `healthcare_gov_ffm` (not SBE-FP) | `federal_exchange_puf` |
| 2026 | `sbe_fp` | `federal_exchange_puf` |

2024 SBE-FP set is **AR, OR only**. Premium data path did not change.

Arkansas and Oregon 2024 remain SBE-FP from year-specific continuity
(AR SBE-FP since 2017; OR SBE-FP since 2015; both still listed for PY2026),
not from HealthCare.gov use alone. Oklahoma uses HealthCare.gov in 2024
and is correctly **not** labeled SBE-FP.

Tests: `OK 2024 != sbe_fp`, `OK 2026 == sbe_fp`, federal PUF both years.

Regenerated:

- `data/metadata/cms_individual_market_platform_map.json`
- `data/metadata/living_cost_cms_coverage.json`
- `data/metadata/living_cost_cms_sbe_lowest_silver.json`

### 2. Source coverage regenerated — COMPLETED

`data/metadata/living_cost_source_coverage.json`
`generated_at` = `2026-08-14T23:48:58+00:00`

Maintenance is no longer conflated as `ESTIMATED_OWNER_REVIEW`:

- `coverage_by_year[*].maintenance` = `INCOMPLETE_PROVENANCE`
- `status_dimensions.by_year[*].maintenance.evidence_status` = `INCOMPLETE_PROVENANCE`
- `status_dimensions.by_year[*].maintenance.methodology_status` = `OWNER_REVIEW_PENDING`

The VQB candidate is not a guessed estimate. It is not VALIDATED.

Same evidence / methodology split is recorded for other components that
had both dimensions (mpg, insurance, replacement, health_oop, etc.).

### 3. Stale Deliverable 2A archived — COMPLETED

Removed from appearing as current status.

Archived at:
`data/metadata/historical/living_cost_deliverable_2a_report.md`

Header:

```
SUPERSEDED HISTORICAL DELIVERABLE 2A SNAPSHOT
NOT CURRENT PROJECT STATUS
```

Obsolete claims in that snapshot (SHA `b2a30ef…`, checkout@v5 / setup-python@v6 /
setup-node@v5, 73 tests, Connecticut unmatched, outdated CMS / health_premium)
are historical only.

`PROJECT_STATUS.md` points at the current closeout.

### 4. Closeout OD labels — COMPLETED

Canonical labels (definitions unchanged; none ACCEPTED):

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

---

## COMPLETED — earlier correction pass (`94362d8` and predecessors)

These remain in force. Do not regress them.

- CPS 2025 ASEC official re-retrieve SHA
  `318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b`
  is the active artifact in `historical.py`, `history.json`, `latest.json`,
  `population.json`. Legacy `…ea6497284` is ledger-only.
- 2024 HUD/ACS geo-join hashes recorded:
  ACS `1637b18a…13718f0e`, HUD FY2024 `0a6634d5…ecfbf98`
- Raw Census county-equivalents **3144** vs FY2024 join universe **3143**
  (CT 9 planning regions → 8 reconstructed legacy counties)
- 100% 50-state+DC 2024 housing population coverage
  (85 unmatched HUD rows = 84 territories + 1 special/non-county; 0 actual
  50-state+DC counties)
- Oregon individual-market source = federal Exchange PUF (2024 and 2026)
- Oregon SBE archives retained as SHOP-only; not used for individual Silver
- 19 standalone SBE individual markets (2024); 21 (2026)
- Real SBE lowest-Silver joins on every true standalone SBE state/year
- BLS CE maintenance from official VQB (`vqb24.csv`) + MTBI UCC map
  Combined mean incl. zeros **$781.22** (not the $1 UCC 470212 fuel residual)
  470212 excluded. Absent TIRECQ / 470211 / 470220 is not measured zero.
- CE evidence remains `INCOMPLETE_PROVENANCE` (official retrieve HTTP 403)
- GitHub Actions majors: `checkout@v7`, `setup-python@v7`, `setup-node@v6`, Node 24

---

## NOT COMPLETED

These are open. Do not treat them as done.

### Owner freeze — NOT COMPLETED

OD-001 through OD-013 are pending. None ACCEPTED.
The next task is owner freeze of those thirteen decisions.

### Living-cost headline — NOT COMPLETED (forbidden until owner freeze)

No 2024/2026 MSLC, Gap, Adequacy, rankings, national median, or Composite.

### Source / evidence gaps — NOT COMPLETED

| Item | Honest status |
|---|---|
| BLS CE official retrieve | HTTP 403; cache `INCOMPLETE_PROVENANCE` |
| BLS Interview/Diary Dictionary xlsx + stubs.zip | HTTP 403 from this client |
| FCC URS / mobile price | `SOURCE_GAP` |
| Vehicle registration | `SOURCE_GAP` |
| Vehicle replacement | `ESTIMATED_OWNER_REVIEW` (OD-005) |
| MEPS 2024 full-year file | **NOT COMPLETED** — do not claim HC-251 is 2024. Latest listed FY file is HC-251 (2023), `RETRIEVED_UNVALIDATED` |
| Federal tax tables | `INVENTORY_NOT_VALIDATED` |
| State tax | `SOURCE_GAP` |
| Local tax / municipal EIT overlay | `SOURCE_GAP` + OD-011 pending |
| NAIC redistribution rights | `FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED` |
| Multi-year CE maintenance vintages | **NOT COMPLETED** (2024 Interview only) |
| HUD unmatched classifier fourth bucket | **NOT COMPLETED** (nit: `unmatched_50_state_dc_county` is unreachable; coverage is 100% this vintage) |
| `census_county_universe_count` rename | **NOT COMPLETED** (still 3143, now qualified as the join count) |

### Housekeeping — NOT COMPLETED

- Untracked local inspect scripts `tmp_inspect_vqb.py` and `tmp_inspect_expname.py` were never committed and never deleted.
- `PROJECT_STATUS.md` still contains leftover early-project text “36 tests passing” (nit; not GitHub CI).
- Definition lock and never-do list were not changed. They were not supposed to be.

---

## Current component honesty (not a headline)

From `data/metadata/living_cost_source_coverage.json` (both years unless noted):

| Component | Coverage status | Notes |
|---|---|---|
| housing | VALIDATED | |
| population_weights | VALIDATED | OD-001 pending |
| food | MODELED_FROM_MEASURED_INPUTS | |
| health_premium | MODELED_FROM_MEASURED_INPUTS | joins exist; no healthcare headline |
| health_oop | RETRIEVED_UNVALIDATED | OD-002 pending |
| mileage | VALIDATED | observed NHTS, not minimum-necessary; OD-003 pending |
| mpg | RETRIEVED_UNVALIDATED | OD-004 not frozen |
| gas | VALIDATED | PADD/regional is not state-measured |
| insurance | RETRIEVED_UNVALIDATED | OD-006 pending |
| maintenance | INCOMPLETE_PROVENANCE | evidence; OD-007 methodology pending |
| registration | SOURCE_GAP | |
| replacement | ESTIMATED_OWNER_REVIEW | OD-005 pending |
| connectivity | SOURCE_GAP | OD-009 pending |
| essentials | INCOMPLETE_PROVENANCE | same CE retrieve 403 |
| recreation | INCOMPLETE_PROVENANCE | OD-008 pending |
| rpp | VALIDATED | |
| federal_tax | INVENTORY_NOT_VALIDATED | |
| state_tax | SOURCE_GAP | |
| local_tax | SOURCE_GAP | OD-011 pending |

---

## Definition lock (unchanged)

```
household money income / number of people in the household
```

Every person in that household receives that value. Rank persons using official
person survey weights. The weighted 30th percentile is the cutoff.

This work did not change that definition, did not introduce an equivalence
scale, and did not change pillar or metric weights.

---

## Next action that requires the owner

**OWNER FREEZE of OD-001 through OD-013.**

Until that happens, do not calculate or publish a Minimum Sustainable Living Cost.

A truthful gap is acceptable. A guessed headline is not.
