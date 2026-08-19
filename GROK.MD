# THE FOUNDATION — FEDERAL TAX SUCCESSOR-DISCOVERY / LIVE-INVENTORY BINDING CLOSEOUT

OD-001 through OD-013 remain ACCEPTED / FROZEN.

FIELD-LEVEL FEDERAL TAX EVIDENCE remains ACCEPTED. Not redesigned.

NAIC AUTO INSURANCE remains CLOSED. Not reopened.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

This pass was one narrow federal-tax currentness correction.

## FINAL SHA

Implementation: `966202dc81d096b5b53c5660bf5a6f671d8d0cab`

Pushed to `origin/main`.

Audited starting implementation: `e5aaa1fccf1f744adffffd572f576896c92d38a2`

## GitHub Actions (on 966202d)

| Workflow                     | Run ID                                                                                | Conclusion |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------- |
| Tests & Code Quality         | [32209827225](https://github.com/sumosizedginger/foundation/actions/runs/32209827225) | success    |
| Deploy Pages                 | [32209827285](https://github.com/sumosizedginger/foundation/actions/runs/32209827285) | success    |
| Validate Living Cost Sources | [32209827387](https://github.com/sumosizedginger/foundation/actions/runs/32209827387) | success    |

Tests & Code Quality pytest: **325 passed**, **5 skipped**, **1 warning** (`load_module` deprecation in `test_validation_cli_is_callable`).

## Problem 1 — successor discovery

`discover_federal_tax_live()` no longer treats the historical October 9, 2025 announcement (`IRS_2026_NEWS_URL`) as proof that Rev. Proc. 2025-32 remains current.

Current first-party surface: official IRS Topics in the News
`https://www.irs.gov/newsroom/topics-in-the-news`

Live result from the current “Inflation adjustments for tax year 2026” section:

- current_2026_inflation_authority: **Rev. Proc. 2025-32**
- current_authority_status: **IDENTIFIED**
- current_authority_source_url: `https://www.irs.gov/newsroom/topics-in-the-news`
- current_authority_checked_at: `2026-08-19T02:40:15Z`
- successor_rev_proc: **null**
- rev_proc_2025_32_current: **true**

The historical announcement may remain corroboration. It is not the successor scan.

If the current surface is unretrieved, missing, or ambiguous: freshness `CHECK_FAILED`, `newer_data_exists=null`. Cached evidence may remain VALIDATED.

If the current surface identifies a later/modifying authority: `NEWER_AVAILABLE`, not `VERIFIED_CURRENT`.

## Problem 2 — live payroll compare

Live Publication 15 payroll is compared to one captured validated 2026 inventory payload. The compare no longer uses duplicated literals (`184500`, `0.062`, `0.0145`, `200000`, `0.009`).

Compared fields:

- OASDI employee rate
- OASDI taxable maximum
- Medicare HI employee rate
- Medicare no-wage-base condition
- Additional Medicare threshold
- Additional Medicare rate

Live result: `current_pub15_payroll_matches=true`.

Mutating a captured inventory payroll field while leaving the live Publication 15 fixture unchanged makes the compare false.

## Federal tax status

- retrieval_validation_status / evidence: **VALIDATED**
- freshness_check_status: **VERIFIED_CURRENT**
- newer_data_exists: **false**

Inventory SHA: `14475b0aa4bed4342efb9337f90c0495dff849169b9fc3525188bf80168435ea`

Bound official bytes unchanged:

- 2024 Rev. Proc. 2023-34 SHA: `544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57`
- 2024 Publication 15 SHA: `3a15da95e39b24f2b6c61f4abc85298c897f57600c3508f9381fab7180a092e0`
- 2026 Rev. Proc. 2025-32 SHA: `e9ada115fb43a4af5ea326ca91edd40ab0bf29b9be01d2c13d7b8fa96214635b`
- 2026 Publication 15 SHA: `b46c3622439d8521e3a0faca4cd5b5ece3451b526f65f06a5e38d5c9f804c88b`

Numeric rules unchanged (from official IRS bytes):

| Year | std deduction | first bracket | OASDI | OASDI cap | Medicare HI | Additional Medicare |
| ---- | ------------- | ------------- | ----- | --------- | ----------- | ------------------- |
| 2024 | 14600         | 11600 @ 10%   | 6.2%  | 168600    | 1.45% no limit | 0.9% above 200000 |
| 2026 | 16100         | 12400 @ 10%   | 6.2%  | 184500    | 1.45% no limit | 0.9% above 200000 |

Field-level source-artifact / SHA validation preserved. Additional Medicare remains extracted evidence.

## Regenerated metadata

- inventory generated_at: `2026-08-19T02:40:10+00:00`
- source coverage generated_at: `2026-08-19T02:40:10+00:00`
- candidate freshness generated_at: `2026-08-19T02:40:50Z`
- freshness_run_id: `6c158aa0eaa619a142fe51c06e27008ff59d4da6c562d65d06625ad7ad63dab7`
- empirical_blocker_family_count: **8**
- gate_blocker_reason_count: **75**

Empirical families: `bls_ce`, `fcc_broadband`, `local_tax_law`, `mobile_price`, `od010_price_index`, `state_tax_law`, `vehicle_registration`, `vehicle_replacement`.

OD-010 remains honest `CHECK_FAILED` (BLS daily quota).

BEA RPP naturally cleared to `VERIFIED_CURRENT` on this live freshness run. BEA was not redesigned.

NAIC remains `VALIDATED` / `VERIFIED_CURRENT`.

## NAIC (unchanged)

- AUT-PB 2022-2023
- source_data_year 2023
- Table 5 Combined Average Premium
- 51 jurisdictions
- selected PDF SHA `34759655ce8e5387b48d523ebab89f9cd8f29d3f67c6d391838398b7d2659b78`

## Locks

- candidate_calculation_authorized = false
- living_cost.release_authorized = false
- candidate_inputs_bound = false
- states_modeled = 0
- ready_for_private_candidate = false
- no `living_cost_candidate_input_bindings.json`

NO MSLC.

Stopped. Did not open state/local tax, FCC/mobile, registration, replacement, or BLS CE.
