# THE FOUNDATION — EVIDENCE ACQUISITION CAMPAIGN

## STATUS: COMPLETE FOR THIS RUN (PARTIAL HONEST CLOSURE)

THIS FILE IS THE CAMPAIGN REPORT.

OD-001 through OD-013 remain ACCEPTED / FROZEN.

**AUDITED FROM:** `55223158f9ae2e217a8c878a083f4f7fdc06231f`  
**IMPLEMENTATION SHA:** `fc18bbdb0923acc2c403f0a7e78e1eb6240e2292`  
**Prior campaign commits:** `8bf9a70` (OD-010 BLS), `76dd95b` (EPA cohorts; GitHub Tests failed ruff)

No MSLC, Gap, Adequacy, rankings, national median, or Composite was calculated.  
The candidate assembler was not built.  
`living_cost_candidate_input_bindings.json` was not created.

```text
candidate_calculation_authorized = false
living_cost.release_authorized   = false
candidate_inputs_bound           = false
translation_index_bound          = true
ready_for_private_candidate      = false
states_modeled                   = 0
```

`is_translation_index_bound()` is **true** from the official BLS OD-010 table plus live series/numeric cross-bind.  
Committed `living_cost_candidate_freshness.json` is still a stale fail-closed snapshot (`translation_index_bound=false` on disk) and was not rewritten.

---

## CLOSED THIS RUN

### CI failure on `76dd95b`

GitHub Tests & Code Quality failed because `ruff format --check` wanted three files reformatted:

- `src/foundation/sources/epa_mpg.py`
- `tests/test_epa_mpg_cohort.py`
- `tests/test_qa_year_atomic_independent.py`

Fixed. No test logic was weakened.

### A. Wave 1A — OD-010 official series inventory

| | |
|---|---|
| BEFORE | `INVENTORY_NOT_VALIDATED` / `MANUAL_VERIFICATION_REQUIRED` / no production table |
| AFTER | Official BLS CPI-U NSA series retrieved and cross-bound |
| Source | BLS public API `https://api.bls.gov/publicAPI/v2/timeseries/data/` |
| Retrieve SHA | `91d408871d6789455435af6ed0188ade2ef0496db613f2d316cc6f17794941b0` |

Official series (not invented):

| component | series | item |
|---|---|---|
| health_oop | CUUR0000SAM | Medical care |
| insurance | CUUR0000SETE | Motor vehicle insurance |
| maintenance | CUUR0000SETD | Motor vehicle maintenance and repair |
| recreation | CUUR0000SAR | Recreation |
| essentials | CUUR0000SA0 | All items (disclosed fallback; OD-010 freeze: component-specific else CPI-U with disclosure) |

Factors = official target / base:

| pair | base | target | factor |
|---|---|---|---|
| health_oop 2024 | 2023 annual 549.084 | 2024 annual 563.841 | 1.026875669296501 |
| health_oop 2026 | 2023 annual 549.084 | 2026 July 593.781 | 1.0814028454662674 |
| insurance 2024 | 2023 annual 716.004 | 2024 annual 843.098 | 1.177504594946397 |
| insurance 2026 | 2023 annual 716.004 | 2026 July 856.080 | 1.1956357785710694 |
| maintenance 2026 | 2024 annual 407.275 | 2026 July 460.185 | 1.1299122214719783 |
| essentials 2026 | 2024 annual 313.689 | 2026 July 333.918 | 1.064487438195155 |
| recreation 2026 | 2024 annual 138.158 | 2026 July 145.242 | 1.0512746276002838 |

`living_cost_od010_translation_table.json` exists and passes structural + numeric + live-series cross-bind.

### B. Wave 1B — EPA MPG official cohort

Official `vehicles.csv.zip` (SHA `66a2948c425c3cf8ad61a184a12296099ef368217d3012b3f7531dcc9c5e2649`).  
OD-004 windows are year-specific (`cost_year-12 .. cost_year-8`), not one shared MY window.

| year | MY window | n | median comb08 | mean | compact | midsize |
|---|---|---|---|---|---|---|
| 2024 | 2012–2016 | 2508 | 24.0 | 24.7 | 24.0 | 24.0 |
| 2026 | 2014–2018 | 2618 | 25.0 | 25.2 | 25.0 | 25.0 |

These medians are data-derived. 24 / 28 / 32 are not the model.  
Evidence promoted to **MODELED_FROM_MEASURED_INPUTS** when the cohort report SHA matches the cached official zip.

### C. Wave 1B — MEPS OOP official derivation

Download is not derivation. HC-251 2023 FYC was already cached. This run parsed official fixed-width `h251.dat` using official codebook / SAS `@start` columns:

| variable | columns | meaning |
|---|---|---|
| AGELAST | 194–195 | age last eligible |
| INSCOV23 | 2090 | 1 = ANY PRIVATE |
| TOTSLF23 | 2483–2488 | total amt paid by self/family 2023 |
| PERWT23F | 3847–3859 | final person weight 2023 |

Filter: AGELAST 18–64, INSCOV23=1, PERWT23F>0, TOTSLF23≥0 (zeros included).

| statistic | value |
|---|---|
| rows | 18,919 (matches official codebook total) |
| in-universe n | 7,039 |
| weighted mean (OD-002 canonical) | **$1,117.72** |
| weighted median (sensitivity) | $311.00 |
| weighted P75 (sensitivity) | $1,114.00 |
| `source_data_year` | **2023** |
| zip SHA | `ad0edc2e34b28b90c8c89f43869f4e90338c93c97c0bfc2cad73140b96edd55a` |

2024 Full Year Consolidated is still **not listed** (AHRQ schedule: August 2026).  
Evidence promoted to **MODELED_FROM_MEASURED_INPUTS**. Lagged project years still use OD-010 medical-care CPI.

---

## NOT COMPLETED

### Wave 1C

| family | status | remaining issue |
|---|---|---|
| Federal tax | INVENTORY_NOT_VALIDATED | 2024/2026 tables exist in code (Rev. Proc. 2023-34 / 2025-32 cited); official IRS PDFs were not retrieved/parsed into a validated inventory this run |
| State tax | SOURCE_GAP | 51-jurisdiction official DOR inventory not built |
| Local tax | SOURCE_GAP | 3143 join geos not generally classified A/B/C/D; class C needs OD-011 overlay |
| Vehicle registration | SOURCE_GAP | 51-jurisdiction official DMV/DOR fee inventory not built |
| Vehicle replacement | FORMULA_FROZEN_INPUTS_PENDING | acquisition / residual / usable years unbound; NADA/KBB still prohibited |

### Wave 2

| family | status | remaining issue |
|---|---|---|
| BLS CE | INCOMPLETE_PROVENANCE | official ZIP retrieve historically HTTP 403 |
| FCC broadband | SOURCE_GAP | URS retrieve/method still blocked (candidate review exists) |
| Mobile price | SOURCE_GAP | no accepted authoritative PRICE source |
| NAIC insurance | RETRIEVED_UNVALIDATED | AUT-PB 2022-2023 PDF cached; state combined-average table not extracted |
| CMS currentness | CHECK_FAILED / incomplete | current-year byte proof still incomplete |
| NHTS | 2022 structural | no newer released NHTS used |

Committed freshness snapshot is stale (fail-closed). Live discovery is the authority.

---

## GITHUB CI on `fc18bbd`

| workflow | result |
|---|---|
| Tests & Code Quality | **success — 257 passed, 5 skipped, 1 warning** [31912746502](https://github.com/sumosizedginger/foundation/actions/runs/31912746502) |
| Validate Living Cost Sources | **success** [31912746541](https://github.com/sumosizedginger/foundation/actions/runs/31912746541) |
| Deploy Pages | **success** [31912746537](https://github.com/sumosizedginger/foundation/actions/runs/31912746537) |

Local collection is 262 tests (5 skipped on CI).

---

## DUAL VERIFIERS

Both `VERDICT: PASS` after last source edit (`2026-08-15T22:40:15Z`):

- `/tmp/goal-verifier-3964948915df-code-review.md` — PASS at `2026-08-15T22:48:59Z` (nits only)
- `/tmp/goal-verifier-3964948915df-qa.md` — PASS at `2026-08-15T22:45:40Z` (nits only)

---

## NEVER-DO (still in force)

Do not calculate or publish MSLC / Gap / Adequacy / rankings / median / Composite.  
Do not authorize candidate or release.  
Do not build the assembler.  
Do not invent prices, fees, or series.

---

## STOP

Evidence that could be closed truthfully in this run was closed (ruff CI; official OD-010 table; EPA cohort; official MEPS HC-251 derivation).  
Wave 1C and Wave 2 remain visibly blocked.

NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.
