# THE FOUNDATION — FINAL READINESS-GATE CORRECTION STATUS

HEAD this pass started from: `2baec0caaeaa3f4f40f64b10833fdb7bd4b332d7`

Audited freeze SHA: `8a4157f62e41d54f58eb361f9188990ffb69c7b7`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**. Owner choices were not reopened.

`candidate_calculation_authorized = false`  
`living_cost_release_authorized = false`  
`states_modeled = 0`

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**

The two authorizations are separate. Private-candidate permission never implies publication.

---

## Completed this pass

1. **Separated authorization.**
   `candidate_calculation_authorized` is distinct from
   `living_cost_release_authorized`. The freshness gate for a PRIVATE
   candidate requires candidate auth and **must not** require public
   release auth. Publication still requires the separate release flag.
   Both flags remain false.

2. **Added freshness family `vehicle_replacement`.**
   Covers OD-005 acquisition, residual, and usable remaining years.
   Status: `FORMULA_FROZEN_INPUTS_PENDING`. No invented numbers.

3. **Added freshness family `bea_rpp` with a real vintage check.**
   Official BEA landing page still lists Current Release
   February 19, 2026 and Next release December 10, 2026.
   Newest official All-items state RPP data year is 2024.
   Selected artifact is `SARPP.zip`
   (sha256 `38713c6224c4c26ae020ffecd4549b82dca84f43d34f93dfdb43f4070cf011da`).
   A VALIDATED parse alone is not enough; the freshness record must name
   the concrete vintage/artifact. Placeholder strings
   `"latest retrieved BEA RPP"` / `"bea rpp artifact"` are refused.

4. **Documented MEPS health OOP as RETRIEVED_UNVALIDATED.**
   HC-251 download is not derivation-ready. Remaining tasks are listed in
   coverage `blocker_notes.health_oop` and the freshness artifact.

5. **Documented EPA MPG as RETRIEVED_UNVALIDATED.**
   Frozen OD-004 methodology is not VALIDATED evidence. Cohort-validation
   tasks are listed in `blocker_notes.mpg`.

6. **Generated `data/metadata/living_cost_candidate_freshness.json`.**
   19 required families, each with source_id, latest_checked_at, vintage,
   artifact, newer_data_exists, retrieval_validation_status, reason.
   **Readiness verdict: FAIL.** `ready_for_private_candidate = false`.
   `blocker_count = 12`. That is desired. Do not fake readiness.

7. **Regenerated source coverage from current truth.**
   Evidence statuses were not improved.
   Official `write_coverage()` now persists `blocker_notes` so a later
   validator run cannot drop the OOP/MPG documentation.

8. **Tests no longer rewrite the production freshness artifact.**
   Writers use `tmp_path`. Production `generated_at` is stable across the
   suite.

9. **Did not build the private candidate assembler.**
   Engine still emits transition-state UNAVAILABLE outputs only.

10. Dual independent verifiers on this correction:
    `/tmp/goal-verifier-88f296288823-code-review.md` **PASS**
    `/tmp/goal-verifier-88f296288823-qa.md` **PASS**

## NOT COMPLETED

These remain truthful blockers. This pass did not paper them over.

- Private candidate engine (not authorized)
- Public MSLC / Gap / Adequacy / rankings / national median / Composite
- 12 current freshness blockers:
    - MEPS OOP `RETRIEVED_UNVALIDATED` (download ≠ derivation)
    - EPA MPG `RETRIEVED_UNVALIDATED` (frozen methodology ≠ validated cohort)
    - BLS CE official retrieve HTTP 403 / `INCOMPLETE_PROVENANCE`
      (maintenance, essentials, recreation cache)
    - NAIC state-table extraction `RETRIEVED_UNVALIDATED`
    - Mobile phone price `SOURCE_GAP`
    - FCC broadband `SOURCE_GAP` / incomplete
    - Vehicle registration `SOURCE_GAP`
    - Vehicle replacement inputs unbound
      (`FORMULA_FROZEN_INPUTS_PENDING`)
    - Federal tax `INVENTORY_NOT_VALIDATED`
    - State tax `SOURCE_GAP`
    - Local tax `SOURCE_GAP` for most FIPS; class-C overlay not generally
      implemented
    - OD-010 CPI/medical translation series not bound
- Place-level municipal overlay
- Binding real numeric replacement inputs
- Official BLS CE re-retrieve
- Authoritative mobile price source
- Independent audit of this readiness-gate SHA after push

## Next

Owner authorization of a PRIVATE candidate
(`candidate_calculation_authorized`) only after freshness can pass.
A later, separate authorization is still required to publish.

Until then: do not calculate or publish an MSLC.
