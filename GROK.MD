# THE FOUNDATION — EIA FRESHNESS REFRESH + GITHUB CI CLOSEOUT

OD-001 through OD-013 remain ACCEPTED / FROZEN.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

## FINAL SHA

Implementation: `932d89e2a907460f6d6ae9a7e72b173514be71be`

Pushed to `origin/main`.

## GitHub Actions (on 932d89e)

| Workflow                     | Run ID                                                                                | Conclusion |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------- |
| Tests & Code Quality         | [32169866919](https://github.com/sumosizedginger/foundation/actions/runs/32169866919) | success    |
| Deploy Pages                 | [32169866939](https://github.com/sumosizedginger/foundation/actions/runs/32169866939) | success    |
| Validate Living Cost Sources | [32170077730](https://github.com/sumosizedginger/foundation/actions/runs/32170077730) | success    |

Validate was dispatched on this SHA (path filter skipped it on the metadata-only push).

Tests & Code Quality pytest: **282 passed**, **5 skipped**, **1 warning** (`load_module` deprecation in `test_validation_cli_is_callable`).

## EIA gasoline

Official retrieve: `https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls`

- official latest period: `2026-08-17`
- selected latest period: `2026-08-17`
- artifact SHA: `b352802e8c52b7276f002c0682d9867a89734815494269346941d810f9c78140`
- freshness_check_status: `VERIFIED_CURRENT`
- newer_data_exists: `false`
- 2024 weekly geos preserved (12 observations remain)

Prior selected max was `2026-08-10` (SHA `658c4b7a…`). Official latest at retrieve time was `2026-08-17`, not a later week.

## Regenerated metadata

- source coverage generated_at: `2026-08-18T18:11:58+00:00`
- candidate freshness generated_at: `2026-08-18T18:12:02Z`
- freshness_run_id: `d9dc07312e76475522a11a3a677ce3b7fe8238f5091ed1958d7dace3a033b4f8`
- empirical_blocker_family_count: **9**
- gate_blocker_reason_count: **66**

Empirical families unchanged: `bls_ce`, `fcc_broadband`, `federal_tax_law`, `local_tax_law`, `mobile_price`, `naic_auto_insurance`, `state_tax_law`, `vehicle_registration`, `vehicle_replacement`. EIA is not an empirical evidence-status blocker.

## Preserved evidence

- MEPS: HC-251 / 2023, INSCOV23=1 ANY PRIVATE, mean 1117.72, median 311.0, P75 1114.0
- EPA: Compact Cars + Midsize Cars, comb08 only, 2024 MY2012-2016, 2026 MY2014-2018
- OD-010: live BLS, observation-set SHA `a40175e7…`, 2026 July, five official series

## Locks

- candidate_calculation_authorized = false
- living_cost.release_authorized = false
- candidate_inputs_bound = false
- states_modeled = 0
- ready_for_private_candidate = false
- no `living_cost_candidate_input_bindings.json`

NO MSLC.

Stopped before NAIC, taxes, FCC/mobile, registration, replacement, and BLS CE.
