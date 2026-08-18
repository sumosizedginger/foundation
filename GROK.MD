# THE FOUNDATION — EVIDENCE CAMPAIGN AUDIT CORRECTION (CLOSED)

OD-001 through OD-013 remain ACCEPTED / FROZEN.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

This closeout records the evidence-integrity correction. It does not
redesign the gate architecture.

## FINAL SHA

`dd8ba691bf846113db1d52846a4047f7f0608997`

Closeout documentation may sit on a later commit; this SHA is the
correction implementation.

## GitHub CI

Pending push. Required green checks:

- Tests & Code Quality
- Validate Living Cost Sources
- Deploy Pages

Local pytest before commit: 279 passed, 1 warning.

## What was corrected

1. `discover_od010()` performs a live official BLS API request via
   `retrieve_bls_cpi_series()`. Cached table bytes are not
   `VERIFIED_CURRENT`.
2. Raw response SHA is preserved separately from canonical
   `observation_set_sha256` (seriesID, year, period, periodName, value
   for the seven frozen CPI_UPDATED pair observations). Cross-bind uses
   observation identity, not volatile `responseTime`.
3. Live currentness: `VERIFIED_CURRENT` only when the live inventory
   matches the persisted table. Newer official target month =>
   `NEWER_AVAILABLE` and `translation_index_bound=false`. Failed live
   retrieve => `CHECK_FAILED`.
4. `write_od010_artifacts()` archives the prior table and always writes
   the canonical current file. A newly retrieved incomplete table cannot
   leave a stale bound pointer.
5. EPA canonical VClass is exact `Compact Cars` + `Midsize Cars`.
   Subcompact/Minicompact are not in the canonical median.
6. Canonical MPG is `comb08` only. Missing/invalid comb08 is counted as
   `rows_missing_canonical_comb08`. No UCity / combA08 fallback.
7. EPA cohorts recomputed from official cached `vehicles.csv.zip`.
8. MEPS/EPA `MODELED_FROM_MEASURED_INPUTS` requires canonical validators
   (`evidence_validators.py`), not file existence. Fail-closed SHA
   mismatch tests added.
9. MEPS wording: adults 18-64 with INSCOV23=1 (ANY PRIVATE). Filter
   unchanged.

## OD-010 live BLS

- live BLS check status: `VERIFIED_CURRENT`
- live latest observation month: `2026 July`
- cached/table target month: `2026 July`
- raw response SHA: `33efde9de9040f432d4483b311cfc4dce9baf2b6aa9cdf7719ab3936f2c5e31b`
- canonical observation-set SHA: `a40175e7fffd11ce240db48d3db41336c8c2b21c4c02e3a5506b11e04967385d`
- translation_index_bound: `true`

Official series unchanged: CUUR0000SAM / CUUR0000SETE / CUUR0000SETD /
CUUR0000SAR / CUUR0000SA0.

## EPA

Exact VClass values used: `Compact Cars`, `Midsize Cars`.

| year | window      | gasoline ICE | exact compact/midsize | year-window | missing comb08 | final n | median | mean | compact median | midsize median |
| ---- | ----------- | ------------ | --------------------- | ----------- | -------------- | ------- | ------ | ---- | -------------- | -------------- |
| 2024 | MY2012-2016 | 45251        | 11565                 | 1708        | 0              | 1708    | 26.0   | 25.6 | 26.0           | 25.0           |
| 2026 | MY2014-2018 | 45251        | 11565                 | 1784        | 0              | 1784    | 26.0   | 26.1 | 26.0           | 25.0           |

Total source rows: 50242. Source SHA:
`66a2948c425c3cf8ad61a184a12296099ef368217d3012b3f7531dcc9c5e2649`.

Prior 24.0 / 25.0 values were not preserved. They included
subcompact/minicompact via substring matching.

EPA listing currentness remains `CHECK_FAILED` (mutable URL bytes not
proven equal to the currently advertised release). Evidence status is
`MODELED_FROM_MEASURED_INPUTS` because the cohort report matches the
selected cached official bytes.

## MEPS

- status: `MODELED_FROM_MEASURED_INPUTS`
- source SHA: `ad0edc2e34b28b90c8c89f43869f4e90338c93c97c0bfc2cad73140b96edd55a`
- mean: 1117.72
- median: 311.0
- P75: 1114.0
- filter unchanged: AGELAST 18-64, INSCOV23=1 (ANY PRIVATE), TOTSLF23>=0,
  PERWT23F>0, zeros included
- live listing: newest Full Year Consolidated still HC-251 / 2023

## Metadata

- source coverage generated_at: `2026-08-18T17:24:53+00:00`
- candidate freshness generated_at: `2026-08-18T17:25:00Z`
- empirical blocker family count: 9
  (`bls_ce`, `fcc_broadband`, `federal_tax_law`, `local_tax_law`,
  `mobile_price`, `naic_auto_insurance`, `state_tax_law`,
  `vehicle_registration`, `vehicle_replacement`)
- gate blocker reason count: 68

MEPS, corrected EPA evidence, and live OD-010 are not in the empirical
blocker-family list. Count derived from live statuses.

## Authorization (unchanged)

- candidate_calculation_authorized = false
- release_authorized = false
- candidate_inputs_bound = false
- states_modeled = 0
- ready_for_private_candidate = false

NO MSLC.
NO CANDIDATE ASSEMBLER.

Stopped before NAIC, taxes, FCC/mobile, registration, replacement, and
BLS CE acquisition work.
