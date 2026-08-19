# THE FOUNDATION — FEDERAL TAX FIELD-PROVENANCE + LIVE-CURRENTNESS CORRECTION

OD-001 through OD-013 remain ACCEPTED / FROZEN.

NAIC AUTO INSURANCE remains CLOSED. Not reopened.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

This pass was a narrow federal-tax evidence correction.

## FINAL SHA

Implementation: `e5aaa1fccf1f744adffffd572f576896c92d38a2`

Pushed to `origin/main`.

Field-provenance implementation: `751832355f8c50b2e47c017c3a697a5060af0712`

Payroll-compare fail-closed follow-up: `e5aaa1fccf1f744adffffd572f576896c92d38a2`

Audited starting implementation: `5992047a08284430de7e3f907c974b24ea68aa84`

## GitHub Actions (on e5aaa1f)

| Workflow                     | Run ID                                                                                | Conclusion |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------- |
| Tests & Code Quality         | [32206076477](https://github.com/sumosizedginger/foundation/actions/runs/32206076477) | success    |
| Deploy Pages                 | [32206076475](https://github.com/sumosizedginger/foundation/actions/runs/32206076475) | success    |
| Validate Living Cost Sources | [32206076471](https://github.com/sumosizedginger/foundation/actions/runs/32206076471) | success    |

Tests & Code Quality pytest: **320 passed**, **5 skipped**, **1 warning** (`load_module` deprecation in `test_validation_cli_is_callable`).

The extra passing test versus 7518323 is `test_unknown_payroll_compare_is_not_verified_current`.

## Federal tax field provenance

Global “>= 2 hashed artifacts” is gone. Every required field now carries:

- authority_id
- source_artifact_key
- source_sha256
- extraction_identity

The validator resolves each reference: artifact exists, `http_ok=true`, SHA present, official IRS/SSA host, year-appropriate key, recorded SHA equals retrieved SHA. Missing/wrong references emit `FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:<year>:<field>`.

Required authorities:

| Year | Income tax / standard deduction | Payroll |
| ---- | ------------------------------- | ------- |
| 2024 | IRS Rev. Proc. 2023-34          | IRS Publication 15 (2024) |
| 2026 | IRS Rev. Proc. 2025-32          | IRS Publication 15 (2026) |

IRB 2023-48 and Topic 751 remain corroboration only. They cannot substitute for the Rev. Proc. or year-specific Publication 15.

Each field is parsed from its designated official artifact. Unrelated IRS files are not concatenated into one parse soup.

### Bound official bytes

- 2024 Rev. Proc. 2023-34 SHA: `544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57`
- 2024 Publication 15 SHA: `3a15da95e39b24f2b6c61f4abc85298c897f57600c3508f9381fab7180a092e0`
- 2026 Rev. Proc. 2025-32 SHA: `e9ada115fb43a4af5ea326ca91edd40ab0bf29b9be01d2c13d7b8fa96214635b`
- 2026 Publication 15 SHA: `b46c3622439d8521e3a0faca4cd5b5ece3451b526f65f06a5e38d5c9f804c88b`
- 2026 Pub 15 URL (year-specific prior, discovered from official IRS publications listing showing Publication 15 (2026)): `https://www.irs.gov/pub/irs-prior/p15--2026.pdf`

Additional Medicare source artifact: Publication 15 for that tax year (`irs_pub15_2024` / `irs_pub15_2026`). Extracted from official text (“withhold a 0.9% Additional Medicare Tax … in excess of $200,000”). The Python constant is compared after extraction and does not manufacture the inventory record. Unparsed Additional Medicare is `ADDITIONAL_MEDICARE_UNPARSED`.

SSA fact sheets still 403 from this client. They are recorded `http_ok=false` and are **not** counted as bound authorities.

### Numeric rules

These numbers come from the bound official IRS bytes, not from the prompt text.

| Year | std deduction | first bracket | OASDI | OASDI cap | Medicare HI | Additional Medicare |
| ---- | ------------- | ------------- | ----- | --------- | ----------- | ------------------- |
| 2024 | 14600         | 11600 @ 10%   | 6.2%  | 168600    | 1.45% no limit | 0.9% above 200000 |
| 2026 | 16100         | 12400 @ 10%   | 6.2%  | 184500    | 1.45% no limit | 0.9% above 200000 |

2026 standard deduction **16100** is the value extracted from official Rev. Proc. 2025-32 bytes (`e9ada115…`). It was not adopted merely because a prompt listed 16100.

Field-provenance validator result: **VALIDATED** (no issues).

Inventory SHA: `e75de5101492ed4e22440a176fa9da4b6c681caf7aaf027a304d1365eb71b3d1`

## Live currentness

Evidence validity and freshness are separate.

- retrieval_validation_status / evidence: **VALIDATED**
- freshness_check_status: **VERIFIED_CURRENT**
- newer_data_exists: **false**

Targeted live discovery used the official IRS publications listing and the 2026 inflation-adjustment page — not `https://www.irs.gov/irb`. Live result: Publication 15 current revision is 2026; Rev. Proc. 2025-32 remains the cited 2026 inflation authority; current Publication 15 payroll values agree with the bound 2026 inventory.

Fail-closed currentness (`evaluate_federal_tax_freshness`):

- live discovery throws => evidence stays VALIDATED; freshness `CHECK_FAILED`; `newer_data_exists=null`
- current Pub 15 revision newer than 2026 => `NEWER_AVAILABLE` / `CHECK_FAILED`, not `VERIFIED_CURRENT`
- `current_pub15_payroll_matches is False` => `CHECK_FAILED`
- `current_pub15_payroll_matches is None` => `CHECK_FAILED` (unknown compare is not agreement)
- `VERIFIED_CURRENT` requires inventory valid AND Pub 15 revision 2026 AND Rev. Proc. 2025-32 current AND payroll compare `True`

Adversarial tests A–I plus live-freshness tests, including `test_unknown_payroll_compare_is_not_verified_current`, cover that split.

## Regenerated metadata

- inventory generated_at: `2026-08-19T01:23:07+00:00`
- source coverage generated_at: `2026-08-19T01:23:21+00:00`
- candidate freshness generated_at: `2026-08-19T01:23:40Z`
- freshness_run_id: `6acf95c874628bf13071da7925a88fa2cfb2b663272e2a7b3dd68898bab7bd9a`
- empirical_blocker_family_count: **8**
- gate_blocker_reason_count: **76**

Empirical families: `bls_ce`, `fcc_broadband`, `local_tax_law`, `mobile_price`, `od010_price_index`, `state_tax_law`, `vehicle_registration`, `vehicle_replacement`.

OD-010 remains honest `CHECK_FAILED` (BLS daily quota). NAIC remains `VALIDATED` / `VERIFIED_CURRENT`.

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
