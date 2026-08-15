# THE FOUNDATION — OD-010 LIVE-FRESHNESS CROSS-BIND

## STATUS: COMPLETE

This bar is finished. This file is the completed-vs-remaining write-up.

OD-001 through OD-013 remain ACCEPTED / FROZEN.

**Implementation SHA:** `a26d7a56b3811c160e93aea7e3fdcf9e72f0779b`

**Audited FROM:** `20e515dadea7de7e0cbbacf7a8ce0d24b064bdd8` (year-specific / atomic binding)

---

## WHAT THIS BAR DID

Sealed the last architecture chain-of-custody gap: a structurally complete OD-010 translation table can no longer bind independently of the live `od010_price_index` FreshnessCheck.

Before this pass, candidate components were year-specific-bound to live artifacts, and OD-010 records were structurally validated and individually hashed — but the captured translation table was not cross-bound to the live index series inventory. Live freshness could later authorize artifact B while the table still held factors derived from artifact A.

That gap is now fail-closed.

**This pass did not:**

- calculate or publish an MSLC, Gap, Adequacy, rankings, national median, or Composite
- build the private candidate assembler
- authorize private calculation or public release
- reopen OD-001–OD-013
- solve the 12 empirical evidence blocker families
- invent CPI series IDs or observations
- create `living_cost_od010_translation_table.json`

---

## COMPLETED

### 1. OD-010 → live freshness cross-binding

`validate_od010_bindings_against_snapshot(od010_payload, live_checks, years)` compares every frozen CPI_UPDATED pair to live `od010_price_index` evidence.

Frozen pairs (unchanged):

| component | project_cost_year |
|---|---|
| health_oop | 2024 |
| health_oop | 2026 |
| insurance | 2024 |
| insurance | 2026 |
| maintenance | 2026 |
| essentials | 2026 |
| recreation | 2026 |

### 2. Live OD-010 freshness identifies series, not just "BLS CPI"

`FreshnessCheck.series_coverage` is a structured inventory per component/year: identifier, periods, artifact/API identity, hash, source_data_year, `covered`.

`discover_od010()` emits required slots for all seven pairs with `covered: false` and **no invented identifiers**. A vague `publisher=BLS` + `landing_url=/cpi/` cannot authorize a translation factor (`OD010_SERIES_COVERAGE_TOO_VAGUE`).

### 3. Series identifier match

Table `official_series_identifier` must exactly equal the live authorized identifier. Mismatch → `SERIES_IDENTIFIER_MISMATCH` → FAIL CLOSED.

### 4. Source / observation / artifact match

Cross-bound: component, project_cost_year, source_data_year, official_series_identifier, publisher, observation period, selected artifact or API identity, SHA/response hash when retained.

### 5. Calculation inputs bound to live observations

A naked `translation_factor` without `calculation_inputs` matching live series / periods / index values cannot become bound (`TRANSLATION_FACTOR_UNBOUND`).

### 6. Cross-bind is part of candidate readiness

`build_live_readiness_context()` captures `od010_cross_binding` from the same atomic read.

```text
translation_index_bound =
    od010_eval.bound
    AND
    od010_cross_binding.ok
```

No caller override.

### 7. Cross-binding is in `freshness_run_id`

`authorizing_state_core` includes per-family `series_coverage` and normalized `od010_cross_binding`. Changing series, artifact/hash, observation, or source-data year changes the run id.

Committed `freshness_run_id`: `4b966f664968da6e938167e74eb8a12b921db10924f95b6f8ce61ec293aa24ff`

### 8. Current evidence status preserved

```text
od010_price_index freshness = MANUAL_VERIFICATION_REQUIRED
od010_price_index evidence  = INVENTORY_NOT_VALIDATED
translation_table_bound     = false
series_inventory_status     = NOT_INVENTORIED
od010_cross_binding.ok      = false
issues                      = OD010_SERIES_COVERAGE_TOO_VAGUE, OD010_TABLE_ABSENT
```

### 9. Tests

[`tests/test_od010_live_cross_binding.py`](tests/test_od010_live_cross_binding.py) — 14 tests, no network — covers all 8 required cases plus naked-factor, vague-landing, discover-invents-nothing, and production-lock tests.

### 10. Preserved good state

Year-specific artifact binding; source_data_year binding; atomic capture; real `od010_record_hash()`; passing evidence states only; registration/local_tax `RULE_YEAR` + `SOURCE_GAP` evidence; replacement `MODEL_SUBINPUT`; connectivity `SOURCE_CLASSIFIED`; 19 components; 7 CPI_UPDATED pairs; OD-001–OD-013 frozen; both auth flags false.

### 11. Dual verifiers (this goal)

Both wrote `VERDICT: PASS` after last source edit (`2026-08-15T19:18:38Z`):

- `/tmp/goal-verifier-d63e46c0bef3-code-review.md` — PASS at `2026-08-15T19:53:14Z`
- `/tmp/goal-verifier-d63e46c0bef3-qa.md` — PASS at `2026-08-15T19:52:10Z`

### 12. GitHub CI on `a26d7a5`

| workflow | result |
|---|---|
| Tests & Code Quality | **success — 223 passed, 5 skipped, 1 warning** [31903557769](https://github.com/sumosizedginger/foundation/actions/runs/31903557769) |
| Validate Living Cost Sources | **success** [31903557625](https://github.com/sumosizedginger/foundation/actions/runs/31903557625) |
| Deploy Pages | **success** [31903557672](https://github.com/sumosizedginger/foundation/actions/runs/31903557672) |

---

## END-STATE CONTROLS (all still fail-closed)

```text
candidate_calculation_authorized = false
living_cost.release_authorized   = false
candidate_inputs_bound           = false
translation_index_bound          = false
ready_for_private_candidate      = false
states_modeled                   = 0
od010_cross_binding.ok           = false
```

Public gate still takes no `checks` argument and still runs live discovery.
Candidate assembler = **not built**.

`empirical_blocker_family_count = 12`
`gate_blocker_reason_count = 75`

---

## NOT COMPLETED (still remaining; do not paper over)

- BLS CE official retrieve HTTP 403 / `INCOMPLETE_PROVENANCE`
- Mobile phone price `SOURCE_GAP`
- FCC broadband `SOURCE_GAP` / incomplete
- Vehicle registration `SOURCE_GAP` (method `RULE_YEAR`; evidence `SOURCE_GAP`)
- Vehicle replacement `FORMULA_FROZEN_INPUTS_PENDING` / `MODEL_SUBINPUT`
- NAIC state-table extraction `RETRIEVED_UNVALIDATED` (AUT-PB 2022-2023; local PDF not bound)
- Federal tax `INVENTORY_NOT_VALIDATED`
- State/local tax `SOURCE_GAP` / most FIPS unresolved
- MEPS health OOP `RETRIEVED_UNVALIDATED` (newest released FYC is HC-251 / 2023)
- EPA MPG `RETRIEVED_UNVALIDATED`
- OD-010 CPI/medical series not inventoried (`translation_index_bound=false`)
- `candidate_inputs_bound=false` (do not build the assembler; no fake bindings)
- CMS / NHTS / EPA / NAIC currentness still `CHECK_FAILED` where previously so
- No MSLC until later owner authorization **and** a passing freshness gate
- Both authorization flags remain false

Do not solve the 12 empirical blocker families unless a later GROK.MD explicitly authorizes that work.

---

## NEVER-DO (still in force)

Do not calculate or publish MSLC / Gap / Adequacy / rankings / median / Composite.
Do not reopen OD-001–OD-013.
Do not change the Bottom-30 definition or introduce an equivalence scale.
Do not change weights or substitute sources.
Do not treat missing as zero or interpolate official observations.
Do not overwrite vintages or delete raw metadata.
Do not build the candidate assembler.
Do not invent series IDs or create a fake OD-010 table.

---

## STOP

OD-010 live-freshness cross-binding is fail-closed.

No MSLC was calculated or published.

The candidate assembler was not built.
