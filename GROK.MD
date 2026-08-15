# THE FOUNDATION — OD-010 LIVE-FRESHNESS CROSS-BIND

## STATUS: COMPLETE

This bar is finished. This file is the completed-vs-remaining write-up.

OD-001 through OD-013 remain ACCEPTED / FROZEN.

**Implementation SHA:** `a26d7a56b3811c160e93aea7e3fdcf9e72f0779b`

**Audited FROM:** `20e515dadea7de7e0cbbacf7a8ce0d24b064bdd8` (year-specific / atomic binding)

**Prior docs HEAD:** `2e028351d77ed6680794faf6556b258ec65acbb8`

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

`validate_od010_bindings_against_snapshot(od010_payload, live_checks, years)` in [`src/foundation/living_cost/candidate_bindings.py`](src/foundation/living_cost/candidate_bindings.py) compares every frozen CPI_UPDATED pair to live `od010_price_index` evidence.

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

`FreshnessCheck.series_coverage` is a structured inventory:

```text
series_coverage[component][year] = {
  covered,
  official_series_identifier,
  publisher,
  latest_observation_period / target_observation_period / base_observation_period,
  source_data_year,
  selected_artifact / api_identity,
  sha256,
}
```

`discover_od010()` now emits required slots for all seven pairs with `covered: false` and **no invented identifiers**. A vague `publisher=BLS` + `landing_url=/cpi/` cannot authorize a translation factor (`OD010_SERIES_COVERAGE_TOO_VAGUE`).

### 3. Series identifier match

Table `official_series_identifier` must exactly equal the live authorized identifier for that component / project year. Mismatch → `SERIES_IDENTIFIER_MISMATCH` → FAIL CLOSED.

### 4. Source / observation period / artifact match

Cross-bound where applicable:

- component
- project_cost_year
- source_data_year
- official_series_identifier
- publisher
- observation period / latest observation
- selected artifact or API identity
- artifact SHA / response hash when either side retains one

### 5. Calculation inputs bound to live observations

A naked `translation_factor` without `calculation_inputs` matching live series / periods / index values cannot become bound (`TRANSLATION_FACTOR_UNBOUND`).

Expected `calculation_inputs`:

- base_observation_period
- base_index_value
- target_observation_period
- target_index_value
- translation_factor
- official_series_identifier / source_artifact / sha256 when retained

### 6. Cross-bind is part of candidate readiness

`build_live_readiness_context()` captures `od010_cross_binding` from the same atomic read as the OD-010 payload and live checks.

```text
translation_index_bound =
    od010_eval.bound
    AND
    od010_cross_binding.ok
```

No caller override. Structurally complete table + failed live cross-bind ⇒ `translation_index_bound = false`.

### 7. Cross-binding is in `freshness_run_id`

`authorizing_state_core` now includes:

- per-family `series_coverage`
- normalized `od010_cross_binding` (`ok`, `issues`, `required`, `normalized` pairs)

Changing series identifier, artifact/hash, base/target observation, observation period, source data year, or live index evidence changes the run id.

Committed `freshness_run_id`: `4b966f664968da6e938167e74eb8a12b921db10924f95b6f8ce61ec293aa24ff`

### 8. Current evidence status preserved

Production today:

```text
od010_price_index freshness = MANUAL_VERIFICATION_REQUIRED
od010_price_index evidence  = INVENTORY_NOT_VALIDATED
translation_table_bound     = false
series_inventory_status     = NOT_INVENTORIED
od010_cross_binding.ok      = false
issues                      = OD010_SERIES_COVERAGE_TOO_VAGUE, OD010_TABLE_ABSENT
```

No fake table. No invented series IDs. No CPI retrieve in this pass.

### 9. Tests

[`tests/test_od010_live_cross_binding.py`](tests/test_od010_live_cross_binding.py) — 14 tests, no network:

1. live series X + table series X ⇒ may pass
2. live X + table Y ⇒ FAIL
3. same series, live hash B + table hash A ⇒ FAIL
4. source_data_year differs ⇒ FAIL
5. target observation period differs ⇒ FAIL
6. structurally complete + failed cross-bind ⇒ `translation_index_bound = false`
7. structurally complete + successful cross-bind ⇒ `translation_index_bound` may become true
8. changing live series / artifact / observation changes `freshness_run_id`

Plus: naked factor unbound; vague BLS landing fail-closed; discover_od010 invents nothing; production locks stay fail-closed.

### 10. Preserved good state

- year-specific candidate artifact binding
- source_data_year binding
- atomic `CapturedJsonArtifact` capture
- real `od010_record_hash()` identity
- passing evidence states only (`VALIDATED`, `MODELED_FROM_MEASURED_INPUTS`)
- registration / local_tax method = `RULE_YEAR`; evidence = `SOURCE_GAP`
- replacement = `MODEL_SUBINPUT`
- connectivity = `SOURCE_CLASSIFIED`
- 19 canonical required components
- 7 frozen CPI_UPDATED pairs
- OD-001–OD-013 ACCEPTED / FROZEN
- both authorization flags false

### 11. Dual verifiers

Both wrote `VERDICT: PASS` on SHA `a26d7a5` after the last source edit (`2026-08-15T19:18:38Z`):

- `/tmp/goal-verifier-4f28b7d8ddac-code-review.md` — PASS at `2026-08-15T19:32:55Z` (nits only)
- `/tmp/goal-verifier-4f28b7d8ddac-qa.md` — PASS at `2026-08-15T19:23:28Z`

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
One readiness context is still atomically captured.
Year-specific artifact / source_data_year cross-binding still holds.
OD-010 record hashes still bind to the exact captured record.
OD-010 table is now also cross-bound to live series inventory.
Candidate assembler = **not built**.

`empirical_blocker_family_count = 12`
`gate_blocker_reason_count = 75` (includes per-component `CROSS_BIND:*:STRUCTURALLY_INCOMPLETE` plus `OD010_CROSS_BIND:OD010_SERIES_COVERAGE_TOO_VAGUE` and `OD010_CROSS_BIND:OD010_TABLE_ABSENT`)

---

## NOT COMPLETED (still remaining; do not paper over)

These were **out of scope** for this bar. They remain real blockers.

- BLS CE official retrieve HTTP 403 / `INCOMPLETE_PROVENANCE` (maintenance, essentials, recreation cache)
- Mobile phone price `SOURCE_GAP`
- FCC broadband `SOURCE_GAP` / incomplete (often HTTP 403)
- Vehicle registration `SOURCE_GAP` (methodology `RULE_YEAR`; evidence still `SOURCE_GAP`)
- Vehicle replacement `FORMULA_FROZEN_INPUTS_PENDING` / `MODEL_SUBINPUT` (acquisition / residual / usable years unbound)
- NAIC state-table extraction `RETRIEVED_UNVALIDATED` (landing current; vintage AUT-PB 2022-2023; local PDF not bound; tables unvalidated)
- Federal tax `INVENTORY_NOT_VALIDATED`
- State/local tax `SOURCE_GAP` / most FIPS unresolved; class-C overlay not generally implemented
- MEPS health OOP `RETRIEVED_UNVALIDATED` (download ≠ derivation; newest released FY Consolidated is HC-251 / 2023)
- EPA MPG `RETRIEVED_UNVALIDATED` (methodology frozen ≠ validated cohort extraction)
- OD-010 CPI/medical translation series not inventoried (`translation_index_bound=false` / `OD010_TRANSLATION_INDEX_NOT_BOUND` / `OD010_SERIES_COVERAGE_TOO_VAGUE`)
- `candidate_inputs_bound=false` (assembler not built — do not build it unless authorized; no fake binding file)
- CMS current-year byte currentness still `CHECK_FAILED`; NHTS `CHECK_FAILED`; EPA `CHECK_FAILED`; NAIC PDF bind `CHECK_FAILED`
- No MSLC until later owner authorization **and** a passing freshness gate
- `candidate_calculation_authorized` and `release_authorized` both remain false

Do not solve the 12 empirical blocker families unless a later GROK.MD explicitly authorizes that work.

---

## NEVER-DO (still in force)

Do not calculate or publish MSLC / 2024/2026 MSLC / Gap / Adequacy / state rankings / national median / Composite.

Do not reopen OD-001–OD-013.

Do not change the Bottom-30 definition.

Do not introduce an equivalence scale.

Do not change pillar or metric weights.

Do not substitute a failed source.

Do not treat missing as zero.

Do not interpolate official observations merely to make a daily line move.

Do not overwrite historical vintages.

Do not delete raw-source metadata.

Do not publish an unvalidated score.

Do not build the candidate assembler.

Do not create a fake OD-010 table or fake bindings to make gates pass.

Do not invent series IDs or observations.

---

## STOP

OD-010 live-freshness cross-binding is fail-closed.

No MSLC was calculated or published.

The candidate assembler was not built.
