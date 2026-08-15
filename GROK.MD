# THE FOUNDATION — OD-010 NUMERIC OBSERVATION / FACTOR INTEGRITY FIX

## STATUS: COMPLETE

This bar is finished. This file is the completed-vs-remaining write-up.

OD-001 through OD-013 remain ACCEPTED / FROZEN.

**Implementation SHA:** `55223158f9ae2e217a8c878a083f4f7fdc06231f`

**Audited FROM:** `a26d7a56b3811c160e93aea7e3fdcf9e72f0779b`

---

## WHAT THIS BAR DID

Narrow integrity correction: a matching series/artifact can no longer carry the wrong numeric observations or a hand-entered translation factor.

`validate_od010_bindings_against_snapshot()` now fail-closes unless:

1. `calculation_inputs.base_index_value` equals the live authorized base observation
2. `calculation_inputs.target_index_value` equals the live authorized target observation
3. `translation_factor` equals recomputed `target / base`
4. `calculation_inputs.translation_factor` equals the record factor and the recomputed factor
5. `calculation_inputs` SHA/response identity matches the live slot (even if the record SHA already matches)

**This pass did not:**

- calculate or publish an MSLC
- build the candidate assembler
- authorize private calculation or release
- solve empirical evidence blockers
- invent CPI series or observations
- create a production OD-010 translation table

---

## COMPLETED

### Live inventory must carry authorized observation values

`od010_series_inventory_is_specific()` now requires finite numeric:

- `base_index_value > 0`
- `target_index_value > 0`

NaN / Infinity / zero / negative / non-numeric fail. Production discovery still emits `covered=false` slots with null values. No invented numbers.

Comparison policy (documented in code):

- Index observations: exact `Decimal(str(value))` after normalize
- Factors: same exact compare, then documented `1e-12` relative fallback for stored precision
- Frozen operation: `target_index_value / base_index_value`

### Cross-bind and recompute

Mismatch codes:

- `CALC_BASE_VALUE_MISMATCH`
- `CALC_TARGET_VALUE_MISMATCH`
- `INVALID_BASE_INDEX_VALUE`
- `INVALID_TARGET_INDEX_VALUE`
- `TRANSLATION_FACTOR_MISMATCH`
- `CALC_ARTIFACT_HASH_MISMATCH`

Table-level SHA is no longer allowed to stand in for `calculation_inputs` SHA.

### Normalized output / `freshness_run_id`

Each OD-010 pair now includes:

- `live_base_index_value` / `table_base_index_value`
- `live_target_index_value` / `table_target_index_value`
- `claimed_translation_factor`
- `calculation_input_translation_factor`
- `recomputed_translation_factor`

Changing only a live index value changes `freshness_run_id`.

### Tests A–I

[`tests/test_od010_numeric_factor.py`](tests/test_od010_numeric_factor.py) — no network:

| case | result |
|---|---|
| A live base=100 / table base=99 | `CALC_BASE_VALUE_MISMATCH` |
| B live target=102 / table target=103 | `CALC_TARGET_VALUE_MISMATCH` |
| C record factor=9.99 | `TRANSLATION_FACTOR_MISMATCH` |
| D record 1.02 / calc 1.03 | `TRANSLATION_FACTOR_MISMATCH` |
| E record SHA matches live, calc SHA differs | `CALC_ARTIFACT_HASH_MISMATCH` |
| F base=0 | FAIL |
| G NaN / Inf / negative | FAIL |
| H base=100, target=102, factor=1.02 | may pass |
| I change only live index value | `freshness_run_id` changes |

### Dual verifiers

Both `VERDICT: PASS` after last source edit (`2026-08-15T20:47:13Z`):

- `/tmp/goal-verifier-8cf5a4032e92-code-review.md` — PASS at `2026-08-15T20:54:19Z` (nits only)
- `/tmp/goal-verifier-8cf5a4032e92-qa.md` — PASS at `2026-08-15T20:51:23Z`

### GitHub CI on `5522315`

| workflow | result |
|---|---|
| Tests & Code Quality | **success — 234 passed, 5 skipped, 1 warning** [31907654859](https://github.com/sumosizedginger/foundation/actions/runs/31907654859) |
| Validate Living Cost Sources | **success** [31907654894](https://github.com/sumosizedginger/foundation/actions/runs/31907654894) |
| Deploy Pages | **success** [31907654887](https://github.com/sumosizedginger/foundation/actions/runs/31907654887) |

---

## END-STATE CONTROLS (still fail-closed)

```text
candidate_calculation_authorized = false
living_cost.release_authorized   = false
candidate_inputs_bound           = false
translation_index_bound          = false
ready_for_private_candidate      = false
states_modeled                   = 0
od010_cross_binding.ok           = false
od010_price_index freshness      = MANUAL_VERIFICATION_REQUIRED
od010_price_index evidence       = INVENTORY_NOT_VALIDATED
series_inventory_status          = NOT_INVENTORIED
```

Candidate assembler = **not built**.

---

## NOT COMPLETED (still remaining)

The 12 empirical families are unchanged and still out of scope:

- BLS CE HTTP 403 / `INCOMPLETE_PROVENANCE`
- Mobile `SOURCE_GAP`
- FCC broadband `SOURCE_GAP`
- Vehicle registration `SOURCE_GAP`
- Vehicle replacement inputs pending
- NAIC tables `RETRIEVED_UNVALIDATED`
- Federal tax `INVENTORY_NOT_VALIDATED`
- State/local tax `SOURCE_GAP`
- MEPS OOP `RETRIEVED_UNVALIDATED`
- EPA MPG `RETRIEVED_UNVALIDATED`
- OD-010 series not inventoried
- `candidate_inputs_bound=false`

No MSLC until later owner authorization **and** a passing freshness gate.

Do not solve those families unless a later GROK.MD explicitly authorizes that work.

---

## STOP

Numeric observation / factor integrity is fail-closed.

No MSLC was calculated or published.

The candidate assembler was not built.
