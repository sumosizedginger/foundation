# THE FOUNDATION — FINAL FRESHNESS-CONTROL AUDIT FIX STATUS

Started from audited HEAD: `bd350887e6550311abce30fde432348264086c6c`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**.

`candidate_calculation_authorized = false` (from `config/definitions.yml`)  
`living_cost_release_authorized = false` (`living_cost.release_authorized`)  
`states_modeled = 0`

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**

The private candidate assembler was not built.

---

## Completed this pass

1. **Freshness is a real check, not a timestamped snapshot.**
   `current_family_truth()` no longer assigns `latest_checked_at=NOW` and
   `newer_data_exists=false` from a hard-coded constructor.
   Each family has `freshness_check_status`:
   `VERIFIED_CURRENT` / `NEWER_AVAILABLE` / `CHECK_FAILED` /
   `MANUAL_VERIFICATION_REQUIRED` / `SOURCE_GAP`.
   `newer_data_exists` is nullable. Not-checked is not encoded as false.

2. **Source-specific discovery.**
   `src/foundation/living_cost/freshness_discovery.py` fetches official
   landing/listing pages per publisher. No generic downloader pretends to
   understand every agency. If discovery cannot run, status is
   `CHECK_FAILED` and the family blocks.

3. **`translation_index_bound` actually blocks.**
   `evaluate_freshness_readiness()` and `assert_candidate_freshness_ready()`
   emit `OD010_TRANSLATION_INDEX_NOT_BOUND` when the live OD-010 table is
   unbound. A VALIDATED `od010_price_index` record with
   `translation_index_bound=false` still fails.

4. **Concrete provenance for passing evidence.**
   `VALIDATED` and `MODELED_FROM_MEASURED_INPUTS` must name publisher,
   landing URL, period, and selected artifact(s). USDA reports
   `months_included` / `month_count` / first / last from official parsed
   rows. CMS references the retrieve-record artifact list with hashes.

5. **One authorization source of truth.**
   Both flags are read from `config/definitions.yml`. Hard-coded
   `return False` authorization functions are gone. The pipeline calls
   the same functions. Absent/malformed config fails closed.
   This commit leaves both flags false.

6. **Empirical blockers unchanged.**
   MEPS OOP, EPA MPG, NAIC remain `RETRIEVED_UNVALIDATED`.
   BLS CE / maintenance / essentials / recreation remain
   `INCOMPLETE_PROVENANCE`. Mobile, FCC, registration remain
   `SOURCE_GAP`. Replacement remains `FORMULA_FROZEN_INPUTS_PENDING`.
   Federal tax remains `INVENTORY_NOT_VALIDATED`. State/local tax
   remain `SOURCE_GAP`.

7. **Freshness artifact regenerated from discovery.**
   `data/metadata/living_cost_candidate_freshness.json`
   `ready_for_private_candidate = false`.
   Timestamps are check times, not constructor time.

## Automated vs manual (this run)

Automated / verified-current when the official page answered:
ACS, HUD, USDA, CMS, MEPS listing, EPA, EIA, BEA.

Manual verification required:
federal / state / local tax, OD-010 indexes.

Check failed (page not established):
NHTS, NAIC, BLS CE listing, FCC (failure recorded; evidence still SOURCE_GAP).

Source gap (no authoritative source bound):
mobile price, vehicle registration, vehicle replacement inputs.

## NOT COMPLETED

- Private candidate engine (not authorized)
- Public MSLC / Gap / Adequacy / rankings / national median / Composite
- The 12 empirical evidence blockers listed above
- Binding real OD-010 translation series
- Binding replacement acquisition / residual / usable years
- Official BLS CE ZIP retrieve (listing check ≠ bytes in hand)
- Complete 51-state tax / registration inventories
- Place-level municipal overlay
- Flipping either authorization flag

## Next

Do not calculate an MSLC. A later owner may set
`candidate_calculation_authorized: true` only after freshness can pass.
Publication still needs the separate `release_authorized` flag.
