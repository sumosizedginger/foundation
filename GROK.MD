# THE FOUNDATION — EIA YEAR-COVERAGE / SELECTED-BYTE IDENTITY CORRECTION

OD-001 through OD-013 remain ACCEPTED / FROZEN.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

## FINAL SHA

Implementation: `f236ff44a173c8ea449cdd2c3426916fb5299669`

Pushed to `origin/main`.

## GitHub Actions (on f236ff4)

| Workflow                     | Run ID                                                                                | Conclusion |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------- |
| Tests & Code Quality         | [32175966230](https://github.com/sumosizedginger/foundation/actions/runs/32175966230) | success    |
| Deploy Pages                 | [32175966224](https://github.com/sumosizedginger/foundation/actions/runs/32175966224) | success    |
| Validate Living Cost Sources | [32175966342](https://github.com/sumosizedginger/foundation/actions/runs/32175966342) | success    |

Tests & Code Quality pytest: **288 passed**, **5 skipped**, **1 warning** (`load_module` deprecation in `test_validation_cli_is_callable`).

Local pytest on this tree: **293 passed**, 1 warning (integration tests ran locally).

The no-op `if not CACHE.exists(): return` unit test is gone. Year-summary/parser logic is unit-tested with a synthetic BIFF2 XLS. Official 2024/2026 year-specific evidence is asserted in Validate Living Cost Sources.

## EIA selected-byte identity

Selected identity is SHA-256 of `data/cache/pswrgvwall.xls` bytes.

- selected-byte SHA: `b352802e8c52b7276f002c0682d9867a89734815494269346941d810f9c78140`
- official retrieved SHA: same
- sidecar SHA is not used as selected identity
- missing workbook => `selected_sha=None` and freshness fail-closed

Regression: local bytes SHA A vs sidecar SHA B uses A.

## EIA year coverage (parser, not global max)

| Year | covered | source_data_year | first date | last date  | weeks | geos | SHA        |
| ---- | ------- | ---------------- | ---------- | ---------- | ----- | ---- | ---------- |
| 2024 | true    | 2024             | 2024-01-01 | 2024-12-30 | 53    | 12   | `b352802e…` |
| 2026 | true    | 2026             | 2026-01-05 | 2026-08-17 | 33    | 12   | `b352802e…` |

2024 last date is no longer the global 2026-08-17 max. Coverage comes from `parse_eia_gas_prices_xls(... reference_year=2024/2026)` plus the shared year-summary helper. A later-year-only workbook does not mark 2024 covered.

## EIA freshness

- official latest: `2026-08-17`
- selected latest: `2026-08-17`
- freshness_check_status: `VERIFIED_CURRENT`
- newer_data_exists: `false`

## Regenerated metadata

- source coverage generated_at: `2026-08-18T19:16:47+00:00`
- candidate freshness generated_at: `2026-08-18T19:16:55Z`
- freshness_run_id: `989a8efffa5736d6a0a108f089530c2330fc17923c3f1a657862fd78cb33a6fd`
- empirical_blocker_family_count: **9**
- gate_blocker_reason_count: **66**

Empirical families unchanged: `bls_ce`, `fcc_broadband`, `federal_tax_law`, `local_tax_law`, `mobile_price`, `naic_auto_insurance`, `state_tax_law`, `vehicle_registration`, `vehicle_replacement`. EIA is not an empirical evidence-status blocker.

## Preserved evidence

- MEPS: HC-251 / 2023, INSCOV23=1 ANY PRIVATE
- EPA: Compact Cars + Midsize Cars, comb08 only
- OD-010: live BLS, observation-set SHA `a40175e7…` unchanged (only volatile `responseTime` / raw-response SHA moved)

## Locks

- candidate_calculation_authorized = false
- living_cost.release_authorized = false
- candidate_inputs_bound = false
- states_modeled = 0
- ready_for_private_candidate = false
- no `living_cost_candidate_input_bindings.json`

NO MSLC.

Stopped before NAIC, taxes, FCC/mobile, registration, replacement, and BLS CE.
