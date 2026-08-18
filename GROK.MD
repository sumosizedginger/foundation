# THE FOUNDATION — NAIC AUTO INSURANCE + FEDERAL TAX EVIDENCE CLOSURE

OD-001 through OD-013 remain ACCEPTED / FROZEN.

NO MSLC.
NO CANDIDATE ASSEMBLER.
NO CANDIDATE AUTHORIZATION.
NO RELEASE AUTHORIZATION.

This pass authorized evidence acquisition and validation for only:

1. NAIC auto insurance
2. Federal tax law

## FINAL SHA

Implementation: `5992047a08284430de7e3f907c974b24ea68aa84`

Pushed to `origin/main`.

NAIC Table 5 + federal-tax inventory implementation: `71b8188f48fbb33a593b4e2197a0bc5511a8f2a9`

Follow-up: coverage `status_dimensions.federal_tax` now reports the inventory validator instead of a hardcoded `INVENTORY_NOT_VALIDATED`.

## GitHub Actions (on 5992047)

| Workflow                     | Run ID                                                                                | Conclusion |
| ---------------------------- | ------------------------------------------------------------------------------------- | ---------- |
| Tests & Code Quality         | [32186679021](https://github.com/sumosizedginger/foundation/actions/runs/32186679021) | success    |
| Deploy Pages                 | [32186678925](https://github.com/sumosizedginger/foundation/actions/runs/32186678925) | success    |
| Validate Living Cost Sources | [32186679010](https://github.com/sumosizedginger/foundation/actions/runs/32186679010) | success    |

Tests & Code Quality pytest: **305 passed**, **5 skipped**, **1 warning** (`load_module` deprecation in `test_validation_cli_is_callable`).

Local pytest on this tree: **310 passed**, 1 warning (integration tests ran locally).

## NAIC auto insurance

Live official publications listing still shows AUT-PB 2022-2023 as newest. No newer Auto Insurance Database Report was found.

- publisher: National Association of Insurance Commissioners
- report title: Auto Insurance Database Report
- publication identifier: `AUT-PB 2022-2023`
- listing identifier: `AUT-PB 2022-2023` (matches PDF)
- data-year range: 2022–2023
- source_data_year: **2023** (not relabeled 2024 or 2026)
- landing: `https://content.naic.org/publications`
- resolved PDF: `https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf`
- selected-byte SHA: `34759655ce8e5387b48d523ebab89f9cd8f29d3f67c6d391838398b7d2659b78`
- sidecar is not identity; missing PDF fails closed
- canonical measure: Combined Average Premium (OD-006)
- sensitivity: Average Expenditure kept separate; not substituted
- table identity: Table 5 Combined Average Premium, data year 2023
- jurisdictions: 51 (50 states + DC); no fabricated states; no duplicates
- national/Countrywide combined average premium from the report: **1438.60**
- official release sanity check: **1438** (rounded national figure; PDF/table is production truth)
- national row is the report figure, not the arithmetic mean of states
- derived artifact: `data/metadata/living_cost_naic_auto_insurance.json`
- evidence: **VALIDATED**
- freshness: **VERIFIED_CURRENT** (`newer_data_exists=false`)

Promotion required live listing identity, actual PDF bytes, Table 5 extract, SHA bind, state-set validation, and national sanity. File existence is not enough.

## Federal tax law

Existing `FEDERAL_TAX_RULES[2024]` and `[2026]` were checked field-by-field against retrieved official IRS artifacts.

### 2024 authorities bound

- IRS Rev. Proc. 2023-34: `https://www.irs.gov/pub/irs-drop/rp-23-34.pdf` SHA `544ba41c7ba64f77da521e0d174a7b7394dc72b5c7c73d10adb19952d5aaae57`
- IRS IRB 2023-48: SHA `5cafae764dbb9b11d90f61300196543425f093acec48b970c45f4cfd79520e86`
- IRS Publication 15 (2024): SHA `3a15da95e39b24f2b6c61f4abc85298c897f57600c3508f9381fab7180a092e0`
- IRS Topic 751: SHA `ce8fee83e6758e56357d4dd1e7a2b91d7bdc6711efd02866c26471ed1bf72a7e`

### 2026 authorities bound

- IRS Rev. Proc. 2025-32 (current post-amendment): `https://www.irs.gov/pub/irs-drop/rp-25-32.pdf` SHA `e9ada115fb43a4af5ea326ca91edd40ab0bf29b9be01d2c13d7b8fa96214635b`
- IRS 2026 inflation-adjustment news (includes OBBBA amendments): SHA `41af03f6b46c87997f36276ba98ae6b63dc621f0cc4eca9d9546a34d74891e77`
- IRS Topic 751 as official payroll-rate / wage-base equivalent

### SSA retrieve note

Official SSA COLA fact sheets and OACT CBB/tax-rate pages returned HTTP 403 from this client. Payroll rates and OASDI wage bases were therefore bound from official IRS Publication 15 / Topic 751 (allowed equivalent). SSA SHAs remain unbound (`http_ok=false`). That is reported, not hidden.

### Inventory vs code (SINGLE filer)

| Year | standard deduction | first ordinary cap | OASDI rate | OASDI cap | Medicare HI | Additional Medicare |
| ---- | ------------------ | ------------------ | ---------- | --------- | ----------- | ------------------- |
| 2024 | 14600              | 11600 @ 10%        | 6.2%       | 168600    | 1.45% no limit | 0.9% above 200000 |
| 2026 | 16100              | 12400 @ 10%        | 6.2%       | 184500    | 1.45% no limit | 0.9% above 200000 |

2026 standard deduction **16100** is the current Rev. Proc. 2025-32 / post-OBBBA figure, not the obsolete pre-amendment 15750 table.

Inventory SHA: `c0ff02d1f20fd81c6e2397e36beb60e67dc653fee5a95ccf403b5fcecd7f94a8`

Code-vs-authority: **match**. No `FEDERAL_TAX_RULES_MISMATCH`.

### Additional Medicare Tax

Already modeled in the existing tax engine (`additional_medicare_rate=0.009`, threshold `$200,000` SINGLE). Not silently ignored. **No `FEDERAL_TAX_MODEL_GAP`.** No methodology change. No MSLC calculated while testing.

Statutory boundary tests cover below/at/above first bracket, standard-deduction boundary, OASDI cap-1 / cap / cap+1, ordinary Medicare, and Additional Medicare threshold+1. Expected values are statutory arithmetic from the inventory, not an online calculator. Year 2025 remains fail-closed.

- evidence: **VALIDATED**
- freshness: **VERIFIED_CURRENT**
- coverage `coverage_by_year` and `status_dimensions` both report VALIDATED via the shared validator

## Regenerated metadata

- source coverage generated_at: `2026-08-18T21:09:35+00:00`
- candidate freshness generated_at: `2026-08-18T20:49:00Z`
- freshness_run_id: `09e4b9fb9a5a3f70a7cb4ecd9633c3e18b117392f4063ea3befa25f4ec3b1588`
- empirical_blocker_family_count BEFORE: **9**
- empirical_blocker_family_count AFTER: **8**
- gate_blocker_reason_count BEFORE: **66**
- gate_blocker_reason_count AFTER: **75**

Empirical families after this pass: `bls_ce`, `fcc_broadband`, `local_tax_law`, `mobile_price`, `od010_price_index`, `state_tax_law`, `vehicle_registration`, `vehicle_replacement`.

NAIC and federal tax left the empirical list. The mathematical expectation of 7 did not occur because live BLS CPI for OD-010 hit the daily API quota (`REQUEST_NOT_PROCESSED` / daily threshold). Cached OD-010 translation-table evidence is **not** marked `VERIFIED_CURRENT`. That is fail-closed freshness, not a rewrite of the bound table.

Gate-reason count rose because the live freshness run recorded additional CROSS_BIND / CHECK_FAILED reasons (including unbound candidate inputs and the OD-010 live miss). Machine-derived statuses are authority; 75 is not hand-edited.

## Preserved evidence

- EIA: selected-byte SHA `b352802e8c52b7276f002c0682d9867a89734815494269346941d810f9c78140`; official=selected `2026-08-17`; 2024 last date `2024-12-30` (53 weeks); 2026 last date `2026-08-17` (33 weeks); `VERIFIED_CURRENT`
- MEPS: HC-251 / 2023, INSCOV23=1 ANY PRIVATE; `MODELED_FROM_MEASURED_INPUTS`
- EPA: exact Compact Cars + Midsize Cars, comb08 only
- OD-010 translation table itself is unchanged; live currentness is `CHECK_FAILED` this run because of BLS quota, not because a newer index vintage was proven

## Locks

- candidate_calculation_authorized = false
- living_cost.release_authorized = false
- candidate_inputs_bound = false
- states_modeled = 0
- ready_for_private_candidate = false
- no `living_cost_candidate_input_bindings.json`

NO MSLC.
NO GAP.
NO ADEQUACY.
NO RANKINGS.
NO NATIONAL LIVING-COST MEDIAN.
NO COMPOSITE.

Stopped before FCC/mobile, registration, replacement, BLS CE, and state/local tax.

Next work after independent audit will target the remaining evidence blockers.
