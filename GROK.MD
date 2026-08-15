# THE FOUNDATION — FINAL YEAR-SPECIFIC / ATOMIC BINDING INTEGRITY FIX

## Status: COMPLETE (fail-closed)

Implementation HEAD: `20e515dadea7de7e0cbbacf7a8ce0d24b064bdd8`  
Audited FROM: `ad7df23c9a19073b0210fb692670c63049494d1b`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**.

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**  
**The private candidate assembler was not built.**

---

## End-state flags

| Flag | Value |
|---|---|
| `candidate_calculation_authorized` | `false` |
| `living_cost.release_authorized` | `false` |
| `states_modeled` | `0` |
| `candidate_inputs_bound` | `false` |
| `translation_index_bound` | `false` |
| `ready_for_private_candidate` | `false` |
| Canonical required components | **19** |
| Canonical CPI_UPDATED pairs | **7** |

---

## What this pass completed

### 1. Year-specific artifact cross-bind

Bindings match `year_coverage[project_cost_year]`, not the whole family.

HUD 2024 cannot bind `FY26_FMRs_revised.xlsx`. HUD 2026 cannot bind `FMR2024_final_revised.xlsx`.

### 2. source_data_year cross-check

`binding.source_data_year` must equal live `year_coverage[year].source_data_year`.

ACS 2026 may use source year 2024. ACS 2026 claiming 2026 fails. MEPS binding year must match the live selected FYC year (currently 2023).

### 3. OD-010 passing evidence

Translation records bind only if `retrieval_validation_state` is `VALIDATED` or `MODELED_FROM_MEASURED_INPUTS`.

`SOURCE_GAP`, `RETRIEVED_UNVALIDATED`, `INCOMPLETE_PROVENANCE`, and the other blocking states fail.

### 4. Real OD-010 record hashes

`od010_record_hash(record)` is SHA-256 of the canonical authorizing fields. The candidate binding's `record_hash` must equal that hash for the exact captured record. An arbitrary 64-character value fails.

### 5–6. Method vs evidence

| Component | Translation method | Evidence (unchanged) |
|---|---|---|
| registration | `RULE_YEAR` | `SOURCE_GAP` |
| local_tax | `RULE_YEAR` | `SOURCE_GAP` |
| replacement | `MODEL_SUBINPUT` (formula + sub-input policy) | `FORMULA_FROZEN_INPUTS_PENDING` |
| connectivity | `SOURCE_CLASSIFIED` (`high_frequency`→YTD, `point_in_time`→NONE) | `SOURCE_GAP` |

No registration fees or local rates were invented.

### 7–8. Atomic capture

`CapturedJsonArtifact` reads each binding file once. SHA-256 and parsed payload come from those exact bytes. Mid-run file rewrite to B leaves payload A + SHA(A). `freshness_run_id` uses those captured identities.

### 9–10. Tests

Year-specific HUD/ACS/MEPS tests and mutating-disk atomic-capture tests are in [tests/test_snapshot_cross_binding.py](tests/test_snapshot_cross_binding.py).

---

## GitHub CI (real Actions)

On HEAD `20e515d`:

| Workflow | Result |
|---|---|
| Tests & Code Quality | **success — 209 passed, 5 skipped, 1 warning** ([31901597152](https://github.com/sumosizedginger/foundation/actions/runs/31901597152)) |
| Validate Living Cost Sources | **success** ([31901597127](https://github.com/sumosizedginger/foundation/actions/runs/31901597127)) |
| Deploy Pages | **success** ([31901597096](https://github.com/sumosizedginger/foundation/actions/runs/31901597096)) |

Local pytest (not CI): 214 passed, 1 warning.

---

## Dual verifiers

Both `VERDICT: PASS` on HEAD `20e515d`:

- `/tmp/goal-verifier-30d5bb00b8ee-code-review.md`
- `/tmp/goal-verifier-30d5bb00b8ee-qa.md`

---

## NOT COMPLETED (still remaining)

Do not paper these over.

1. BLS CE HTTP 403 / `INCOMPLETE_PROVENANCE`
2. Mobile phone price `SOURCE_GAP`
3. FCC broadband `SOURCE_GAP`
4. Vehicle registration `SOURCE_GAP` (method is now `RULE_YEAR`; evidence still gap)
5. Vehicle replacement inputs pending
6. NAIC tables `RETRIEVED_UNVALIDATED`
7. Federal tax `INVENTORY_NOT_VALIDATED`
8. State / local tax `SOURCE_GAP`
9. MEPS health OOP `RETRIEVED_UNVALIDATED`
10. EPA MPG `RETRIEVED_UNVALIDATED`
11. OD-010 series not bound
12. Candidate inputs unbound — assembler not built
13. CMS current-year PUF byte currentness `CHECK_FAILED`
14. NHTS live discovery `CHECK_FAILED`
15. Both authorization flags remain `false`
16. Some discoverers still omit `source_data_year` on year_coverage (validator fail-closes; does not reopen family-wide matching)
17. No MSLC until later owner authorization **and** a passing freshness gate

---

## Stop

DO NOT BUILD THE CANDIDATE ASSEMBLER.

NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.
