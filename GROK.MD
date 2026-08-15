# THE FOUNDATION — FINAL SNAPSHOT / INPUT CROSS-BINDING HARDENING

## Status: COMPLETE (fail-closed)

Implementation HEAD: `ad7df23c9a19073b0210fb692670c63049494d1b`  
Core cross-bind: `4e8346ea423b5c632178a9339ed0493c77268be3`  
Writer/policy lock: `ad7df23c9a19073b0210fb692670c63049494d1b`

Audited FROM: `5d2b2e2a3f836a9d6ddac183fd778292c301b928` / `855e42f10a883d59713b9cbc1281d288e8725104`

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
| `required_project_cost_years` | `[2024, 2026]` |
| Canonical required components | **19** |
| Canonical CPI_UPDATED pairs | **7** |

---

## What this pass completed

### 1. Candidate inputs are cross-bound to live freshness

`validate_candidate_bindings_against_snapshot()` requires each component/year binding to match the live family:

- `source_id` / `source_family` must be the mapped family or `{family}_{year}`
- selected artifact IDs + SHA-256 must match the live FreshnessCheck
- `evidence_status` must equal live `retrieval_validation_status`

Connectivity: broadband → `fcc_broadband`, mobile → `mobile_price`.  
Healthcare: premium → CMS, OOP → MEPS (separate).

Hash B on freshness + hash A on the binding **fails**.

### 2. Binding evidence must be a passing state

Complete bindings require `VALIDATED` or `MODELED_FROM_MEASURED_INPUTS`.

`SOURCE_GAP`, `UNAVAILABLE`, `INCOMPLETE_PROVENANCE`, `FORMULA_FROZEN_INPUTS_PENDING`, `INVENTORY_NOT_VALIDATED`, and `RETRIEVED_UNVALIDATED` are incomplete.

### 3. translation_method matches frozen OD-010 policy

`FROZEN_TRANSLATION_POLICY` is the authority. Binding method must equal `expected_translation_method(component, year)`.

CPI_UPDATED also requires a matching OD-010 record (same component, project year, source data year) plus a bound record identity/hash.

Frozen CPI_UPDATED pairs:

health_oop 2024/2026, insurance 2024/2026, maintenance 2026, essentials 2026, recreation 2026.

### 4. Generated coverage cannot shrink the component universe

`required_candidate_components()` returns the frozen 19-tuple only.

If `coverage.required_components` differs in set or order: **FAIL CLOSED**.

### 5. OD-010 pairs cannot silently shrink

`required_cpi_updated_bindings()` is frozen, not generated `source_lag`.

If generated `source_lag` drops or relabels a frozen CPI_UPDATED pair: **FAIL CLOSED**.

`write_coverage()` now emits `maintenance` 2024 as `NONE` (not `NONE_ALREADY_LOCAL`) and asserts both the component universe and frozen source-lag before writing.

### 6. One readiness context

Public path:

1. `current_family_truth()`
2. `build_live_readiness_context()` — reads bindings **once**
3. `validate_readiness_context()` — uses that captured context only
4. `snapshot_from_context()` — `freshness_run_id` from that exact context

A future assembler must consume this snapshot. Binding files are not re-read after capture.

### 7. freshness_run_id hashes authorizing state

Per family: source_id, latest_checked_at, vintages, selected artifact + hashes, newer_data_exists, retrieval/freshness/listing/artifact currentness, selected_artifact_matches_latest, year_coverage, input_evidence_status, transformation_method.

Also: years, authorization flags, both binding identities (file SHA, derived bound, missing, normalized identities).

Changing retrieval status, artifact currentness, artifact SHA, candidate-binding SHA, or OD-010 SHA changes the run id.

### 8. Future candidate contract (no assembler)

Snapshot field `future_candidate_must_record`:

- `freshness_run_id`
- `candidate_input_binding_identity`
- `od010_binding_identity`
- must not reload a different binding file after readiness
- if the binding file changes, run readiness again

### 9. Tests

15 required behavioral tests plus a writer/policy lock test. No live-network calls in those tests.

### 10–11. Preserved / empirical blockers not solved

Public gate still takes no `checks` argument. Auth only from `config/definitions.yml`. Year coverage still requires `covered: true`. Mutable-artifact invariants remain. BEA evidence vs freshness axes remain separate. CMS / NHTS / NAIC / EPA statuses unchanged. 12 empirical blocker families unchanged. Recreation $1,200 / $2,400. Reserve $0. No fake binding file. No fake OD-010 table.

---

## GitHub CI (real Actions)

On HEAD `ad7df23`:

| Workflow | Result |
|---|---|
| Tests & Code Quality | **success — 199 passed, 5 skipped, 1 warning** ([31900500449](https://github.com/sumosizedginger/foundation/actions/runs/31900500449)) |
| Validate Living Cost Sources | **success** ([31900500443](https://github.com/sumosizedginger/foundation/actions/runs/31900500443)) |
| Deploy Pages | **success** ([31900500450](https://github.com/sumosizedginger/foundation/actions/runs/31900500450)) |

Local pytest (not CI): 204 passed, 1 warning.

---

## Dual verifiers

Both `VERDICT: PASS` on HEAD `ad7df23`:

- `/tmp/goal-verifier-bd7f7b938dcf-code-review.md`
- `/tmp/goal-verifier-bd7f7b938dcf-qa.md`

First code-review FAIL: `write_coverage()` emitted `NONE_ALREADY_LOCAL` for maintenance 2024 and Validate CI crashed. Fixed, then both PASS.

---

## NOT COMPLETED (still remaining)

Do not paper these over.

1. BLS CE HTTP 403 / `INCOMPLETE_PROVENANCE`
2. Mobile phone price `SOURCE_GAP`
3. FCC broadband `SOURCE_GAP`
4. Vehicle registration `SOURCE_GAP`
5. Vehicle replacement `FORMULA_FROZEN_INPUTS_PENDING`
6. NAIC tables `RETRIEVED_UNVALIDATED`; PDF unbound
7. Federal tax `INVENTORY_NOT_VALIDATED`
8. State / local tax `SOURCE_GAP`
9. MEPS health OOP `RETRIEVED_UNVALIDATED`
10. EPA MPG `RETRIEVED_UNVALIDATED`
11. OD-010 series not bound
12. `candidate_inputs_bound = false` — assembler not built
13. CMS current-year PUF byte currentness `CHECK_FAILED`
14. NHTS live discovery `CHECK_FAILED`
15. Both authorization flags remain `false`
16. No MSLC until later owner authorization **and** a passing freshness gate

---

## Stop

DO NOT BUILD THE CANDIDATE ASSEMBLER.

NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.
