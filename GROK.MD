# THE FOUNDATION — LIVE CANDIDATE-GATE TRUST BINDING

## Status: COMPLETE (fail-closed)

Implementation HEAD: `5d2b2e2a3f836a9d6ddac183fd778292c301b928`  
Core implementation: `855e42f10a883d59713b9cbc1281d288e8725104`  
Follow-up (CI collection): `5d2b2e2a3f836a9d6ddac183fd778292c301b928`

Audited FROM: `733f9d46ef7cea338da1555314e32903167a8901`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**.

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**  
**The private candidate assembler was not built.**  
**Private calculation was not authorized.**  
**Public release was not authorized.**

---

## End-state flags (config + runtime)

| Flag | Value |
|---|---|
| `candidate_calculation_authorized` | `false` |
| `living_cost.release_authorized` | `false` |
| `states_modeled` | `0` |
| `ready_for_private_candidate` | `false` |
| `candidate_inputs_bound` | `false` (derived; binding file absent) |
| `translation_index_bound` | `false` (derived; OD-010 table absent) |
| `required_project_cost_years` | `[2024, 2026]` |
| `calculates_mslc` | `false` |

Authorization is read only from `config/definitions.yml`.

---

## What this pass completed

### 1. Public candidate gate runs live discovery itself

Public production functions:

```text
run_candidate_readiness_gate() -> dict
assert_candidate_freshness_ready() -> dict
```

Both take **no** `checks` argument. Injecting checks raises `TypeError`.

The public gate internally:

1. refuses if `candidate_calculation_authorized()` is false (**before** discovery);
2. calls `current_family_truth()`;
3. wraps discovery failure as `FreshnessGateError`;
4. builds an immutable-style snapshot with `freshness_run_id`;
5. validates the **live** checks.

`_validate_candidate_checks(checks)` is the internal/pure validator for synthetic unit tests only.

A future assembler must consume the returned snapshot. It must not discard live discovery and later load an older committed JSON file.

### 2. Tests use synthetic checks only through the internal validator

Ordinary unit tests:

- inspect the public signature (no `checks`);
- monkeypatch `current_family_truth` under the public boundary;
- reconstruct committed-artifact checks without network;
- do **not** import a `tests` package (CI collection requires this).

### 3. Readiness-run ID

Each live snapshot records:

- `freshness_run_id` = SHA-256 of canonical JSON of `generated_at`, `required_project_cost_years`, selected artifacts/hashes, OD-010 binding identity, candidate-input binding identity
- `generated_at`
- `required_project_cost_years`

Committed artifact:

- `generated_at`: `2026-08-15T17:15:46Z`
- `schema_version`: `2.2`
- `freshness_run_id`: `da4d93960acab8d976f1926223449f2b20840fbc183426a5a4e2257765b18a8a`

### 4. Candidate-input binding is structural

`are_candidate_inputs_bound()` derives completeness. A manual `{"bound": true, "inputs": {...}}` is ignored.

Required components for 2024 and 2026:

housing, population_weights, food, health_premium, health_oop, mileage, mpg, gas, insurance, maintenance, registration, replacement, connectivity (broadband + mobile), essentials, recreation, rpp, federal_tax, state_tax, local_tax.

The binding file remains **absent**. `candidate_inputs_bound = false`. This still blocks the assertion gate.

### 5. OD-010 binding is structural

`is_translation_index_bound()` derives completeness from source-lag `CPI_UPDATED` pairs (currently health_oop 2024/2026, insurance 2024/2026, maintenance/essentials/recreation 2026).

`{"bound": true, "series": {"foo": "..."}}` does **not** bind.

The OD-010 table remains **absent**. `translation_index_bound = false`. `OD010_TRANSLATION_INDEX_NOT_BOUND` remains a blocker.

### 6. Mutable-artifact invariants are gated

Families: USDA, EIA, EPA/DOE, BEA, CMS current PUF, NAIC current report.

`freshness_check_status = VERIFIED_CURRENT` requires:

- `listing_freshness_status = VERIFIED_CURRENT`
- `artifact_currentness_status = VERIFIED_CURRENT`
- `selected_artifact_matches_latest = true`

An inconsistent object fails even if discovery later regresses.

### 7. Year coverage is explicit

A year is covered only when the record is a dict with `covered: true`.

Absent, `false`, `{"covered": false}`, and `{}` are missing.

### 8. BEA status is from the committed artifact

Historical SHA `733f9d4` reported `bea_rpp: CHECK_FAILED` (connection reset). That historical artifact was **not** rewritten.

This pass regenerated freshness by live discovery. **Actual committed result now:**

- BEA evidence: `VALIDATED`
- BEA freshness: `VERIFIED_CURRENT`
- listing: `VERIFIED_CURRENT`
- artifact currentness: `VERIFIED_CURRENT`
- `selected_artifact_matches_latest`: `true`
- vintage: BEA SARPP All-items 2024 / current release February 19, 2026

`freshness_status_summary()` derives text from the artifact. It does not invent `VERIFIED_CURRENT`.

### 9. Check failure is not bad data

Axes remain separate:

- BEA: `VALIDATED` evidence + `VERIFIED_CURRENT` freshness (this run)
- CMS: `MODELED_FROM_MEASURED_INPUTS` + `CHECK_FAILED` (listing current; current-year byte currentness unresolved)
- NHTS: `VALIDATED` + `CHECK_FAILED`
- EPA: `RETRIEVED_UNVALIDATED` + `CHECK_FAILED`

Validated cached evidence was not demoted. Freshness was not promoted merely because cached evidence is validated.

### 10. Preserved good state

- OD-001–OD-013 ACCEPTED / FROZEN
- recreation floor $1,200 / preferred $2,400
- extra resilience reserve $0
- USDA 2024 = 12 official months; USDA 2026 selected = January–May; official latest month = May 2026; `substituted_2024_for_2026 = false`
- EIA selected / official max observation = `2026-08-10`
- NAIC latest identifier = `AUT-PB 2022-2023`; local PDF not bound; state extraction `RETRIEVED_UNVALIDATED`; freshness `CHECK_FAILED`
- CMS current-year byte currentness still unresolved
- EPA cohort validation still unresolved
- local tax fail-closed
- unsupported tax years fail-closed
- authorization only from `config/definitions.yml`

### 11. Empirical blockers were not solved

12 empirical blocker families remain. Unique gate reasons in the committed artifact: **35**.

---

## GitHub CI (real Actions, not local pytest)

On implementation HEAD `5d2b2e2`:

| Workflow | Result |
|---|---|
| Tests & Code Quality | **success — 181 passed, 5 skipped, 1 warning** ([31898654468](https://github.com/sumosizedginger/foundation/actions/runs/31898654468)) |
| Deploy Pages | **success** ([31898654502](https://github.com/sumosizedginger/foundation/actions/runs/31898654502)) |

Validate Living Cost Sources is path-filtered. `5d2b2e2` changed tests only. Last validate on living-cost source changes (`855e42f`): **success** ([31898397462](https://github.com/sumosizedginger/foundation/actions/runs/31898397462)).

Local pytest (not CI): 186 passed, 1 warning (the 5 CI-skipped integration tests ran locally).

---

## Public gate report (GROK.MD §12)

- **Signature:** `run_candidate_readiness_gate()` / `assert_candidate_freshness_ready()` — no parameters
- **Live discovery internally:** yes (`current_family_truth()`)
- **freshness_run_id:** SHA-256 of the live snapshot core; committed `da4d93960acab8d976f1926223449f2b20840fbc183426a5a4e2257765b18a8a`
- **Candidate-input binding:** structurally unbound (`false`)
- **OD-010 binding:** structurally unbound (`false`)
- **Required project years:** `[2024, 2026]`
- **BEA actual freshness from committed artifact:** `VERIFIED_CURRENT` (evidence `VALIDATED`)
- **Empirical blocker family count:** 12
- **Gate blocker reason count:** 35

---

## Dual verifiers

Both wrote `VERDICT: PASS` on HEAD `5d2b2e2` after the CI collection fix:

- `/tmp/goal-verifier-b3658864afae-code-review.md`
- `/tmp/goal-verifier-b3658864afae-qa.md`

First QA FAIL: unpushed work + live-network unit test.  
Second QA FAIL: `from tests.test_freshness_control` broke GitHub collection (`ModuleNotFoundError: No module named 'tests'`).  
Fixed by inlining helpers. Both PASS on the same latest source.

---

## NOT COMPLETED (still remaining)

Do not paper these over. They are honest fail-closed blockers.

1. **BLS CE** official retrieve HTTP 403 / `INCOMPLETE_PROVENANCE` (maintenance, essentials, recreation cache)
2. **Mobile phone price** `SOURCE_GAP`
3. **FCC broadband** `SOURCE_GAP` / incomplete
4. **Vehicle registration** `SOURCE_GAP`
5. **Vehicle replacement** `FORMULA_FROZEN_INPUTS_PENDING` (acquisition / residual / usable years unbound)
6. **NAIC** state-table extraction `RETRIEVED_UNVALIDATED`; local PDF not bound to AUT-PB 2022-2023
7. **Federal tax** `INVENTORY_NOT_VALIDATED`
8. **State / local tax** `SOURCE_GAP` / most FIPS unresolved; class-C overlay not generally implemented
9. **MEPS health OOP** `RETRIEVED_UNVALIDATED` (download ≠ derivation; newest Full Year Consolidated is HC-251 / 2023)
10. **EPA MPG** `RETRIEVED_UNVALIDATED` (methodology frozen ≠ validated cohort extraction)
11. **OD-010** CPI/medical translation series not bound
12. **`candidate_inputs_bound = false`** — assembler not built (do not build it unless authorized)
13. **CMS** current-year PUF byte currentness still `CHECK_FAILED`
14. **NHTS** live discovery `CHECK_FAILED`
15. No MSLC until later owner authorization **and** a passing freshness gate
16. Both authorization flags remain `false`

Nit only (not a blocker): the committed snapshot still stores pre-fix binding-identity paths (`D:\Foundation\...`, `missing: ["ABSENT"]`). Live helpers now emit repo-relative paths and required component/year pairs. This does not affect the public gate.

---

## Stop

DO NOT BUILD THE CANDIDATE ASSEMBLER.

NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.
