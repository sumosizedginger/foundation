# THE FOUNDATION — POST-OWNER-FREEZE AUDIT CORRECTIONS STATUS

Audited freeze SHA: `8a4157f62e41d54f58eb361f9188990ffb69c7b7`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**. Owner choices were not reopened.

`living_cost_release_authorized = false`. `states_modeled = 0`.

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.

---

## Completed this pass

1. **OD-007 schema mismatch fixed.**
   `select_maintenance_statistic()` now reads the production keys
   `mean_incl_zero`, `median_incl_zero`, `p25_positive`, `p50_positive`,
   `positive_spender_mean`. It accepts the live
   `living_cost_maintenance_candidates.json` artifact.
   Recovered values: 781.22 / 0.0 / 276.0 / 560.0 / 1728.47.
   Evidence remains `INCOMPLETE_PROVENANCE`, not VALIDATED.

2. **Local tax fail-closed (OD-011).**
   `calculate_local_income_tax()` returns a typed `LocalTaxResult`.
   Unresolved FIPS (e.g. 06075) is `UNRESOLVED_SOURCE_GAP`, amount `None`.
   Partial-city without overlay is `PARTIAL_CITY_NEEDS_OVERLAY`.
   Only verified-no-tax or verified-rate (or no-geography request) may
   contribute 0 / a computed amount.
   `evaluate_taxes_for_gross()` and `solve_gross_required_income()` raise
   `LocalTaxUnresolvedError` instead of silently omitting local tax.

3. **Unsupported tax years fail closed (OD-010 RULE_YEAR).**
   Federal, FICA, and state functions no longer fall back to 2024 law.
   2024 uses 2024 tables. 2026 uses 2026 tables. 2025 / 2027 / 2019 raise
   `UnsupportedTaxYearError`. No 2027 tables were invented.

4. **Freshness gate is now enforceable.**
   `assert_candidate_freshness_ready()` requires a machine-readable check
   for every required family (ACS, HUD, USDA, CMS, MEPS, NHTS, EPA, EIA,
   NAIC, BLS CE, FCC, mobile, federal/state/local tax, registration,
   OD-010 index). It refuses if a check is missing, newer data is unused,
   a required source is SOURCE_GAP / incomplete, the translation index is
   unbound, source year is silently relabeled, or release is not authorized.
   The guard does **not** calculate an MSLC.

5. **Release lock preserved.**
   Pipeline flag remains false. Public state lists remain empty.
   National living-cost distributions remain unpublished.

6. **Tests** cover production OD-007 keys, local-tax statuses, solver
   refusal on 06075, year fail-closed, and freshness refusal.

## NOT COMPLETED / still blocking a future candidate

These were **not** solved by this audit pass and must stay truthful:

- BLS CE official retrieve: HTTP 403 / `INCOMPLETE_PROVENANCE`
- Mobile phone price: `SOURCE_GAP`
- FCC broadband price evidence: `SOURCE_GAP` / incomplete retrieval
- Vehicle registration: `SOURCE_GAP`
- Vehicle replacement numeric inputs: `FORMULA_FROZEN_INPUTS_PENDING`
- NAIC state-table extraction: `RETRIEVED_UNVALIDATED`
- Federal tax tables: `INVENTORY_NOT_VALIDATED`
- State tax inventory: incomplete / unvalidated as applicable
- Local tax: `SOURCE_GAP` for any FIPS not in the verified-rate or
  verified-no-tax inventory (almost the entire county universe)
- MEPS 2024 Full Year Consolidated: use only if officially listed
- OD-010 component-specific CPI series: not yet bound into a live
  translation table (`translation_index_bound` is false)
- Place-level municipal overlay (OD-011 class C) is not generally
  implemented
- Independent audit of this correction SHA
- Any 2024/2026 MSLC, Gap, Adequacy, rankings, national median, Composite

## Next human task

Independent review of this correction. Then, only with a later owner
authorization **and** a passing freshness gate: candidate calculation.

Until then: do not calculate or publish a living-cost headline.
