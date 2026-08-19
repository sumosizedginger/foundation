# THE FOUNDATION — STATE TAX WAVE 3 AUDIT-DEFECT CLOSEOUT

IMPLEMENTATION SHA:
105bf68533fd00804de9fde80b6445984a495a2a

PARENT SHA:
1e239c6a5f9eb638b56145d326684da90a7b122f
(docs after Wave 3 implementation 4081cdb / NC provenance 5d8e9cc)

Functional commits on this closeout:

- 1e63db6 bind freshness to inventory and compare live schedules
- 105bf68 hash inventory identity with LF-normalized bytes

INVENTORY IDENTITY (LF-normalized file SHA-256):
3655dd92a20255a53cd6e13d5228dcb083d816f8ddd8bb4aae338873a887ec63
inventory generated_at: 2026-08-19T17:32:42+00:00
(unchanged inventory payload from 4081cdb)

GITHUB ACTIONS (head 105bf68 — do not reuse 5d8e9cc runs):

- Tests & Code Quality 32301984639 success
  363 passed, 5 skipped, 1 warning
- Validate Living Cost Sources 32301984717 success
- Deploy Pages 32301984723 success

Local pytest after implementation: 367 passed, 1 warning
(Windows cache present; CI skips 5 integration tests).

==================================================
FILES CHANGED
==================================================

src/foundation/sources/state_tax_currentness.py
Taxing-state VERIFIED_CURRENT now re-runs extract_official_schedule
against live first-party text and compares every material modeled field
(standard deduction, personal exemption, all bracket rates and
thresholds). Rate-substring matching is gone.

src/foundation/sources/state_tax.py
Inventory file SHA is LF-normalized so Windows CRLF checkouts and Linux
CI agree. Freshness/inventory binding fails closed on SHA, generated_at,
or stale-artifact mismatch. Taxing live currentness fetches the cell's
bound official URLs (run-cached), not a single rate token.

src/foundation/living_cost/freshness_discovery.py
discover_state_tax() records inventory_sha256, inventory_generated_at,
and inventory_binding on the freshness extra.

tests/test_state_tax_inventory.py
Adversarial currentness + cross-run freshness identity tests.

data/metadata/living_cost_candidate_freshness.json
Regenerated from current code + current inventory. Bound to inventory
identity. Obsolete NC 2026 landing page removed from selected artifacts.

data/metadata/living_cost_source_coverage.json
data/metadata/living_cost_tax_coverage.json
Canonical restamp of generated_at only (economic statuses unchanged).

data/metadata/living_cost_od010_bls_retrieve.json
data/metadata/living_cost_od010_live_currentness.json
Restamped by the same freshness run. observation_set_sha256 unchanged.
OD-010 remains VERIFIED_CURRENT from that run.

==================================================
CURRENTNESS DESIGN
==================================================

VERIFIED_CURRENT
A targeted first-party GET ran during this freshness run, AND:

- no-tax cell: official no-wage-income-tax wording still holds for 2026
  (a clearly future 2027+ tax does not disturb 2026); or
- taxing cell: live official schedule extraction re-establishes every
  material modeled field of the stored 2026 cell.

CHECK_FAILED
Live GET failed; live text empty; live extraction incomplete/ambiguous;
freshness is not bound to the current inventory; or 2026 currentness is
otherwise unestablished. Cached evidence is not demoted.
newer_data_exists = null.

NEWER_AVAILABLE
Live official text shows a 2026-applicable difference versus the stored
validated schedule (rate, deduction, exemption, brackets).

CURRENTNESS_PENDING
No live check was performed (cache-only / perform_live=False), or the
2026 cell is not yet evidence-valid. Never counted as verified.

Cached SHA/URL alone is not currentness.
Retrieval success alone is not currentness.
A historical rate token appearing on a page that also states a different
2026 rate is not currentness.
An unchanged rate with a changed 2026 standard deduction is not currentness.
One remaining progressive bracket rate with changed thresholds is not
currentness.

==================================================
STALE FRESHNESS FIX
==================================================

prior freshness generated_at: 2026-08-19T16:45:51Z
(older than inventory 2026-08-19T17:32:42+00:00; still listed
st_nc_2026_std_ded_page.html)

new freshness generated_at: 2026-08-19T20:53:55Z
bound inventory_sha256:
3655dd92a20255a53cd6e13d5228dcb083d816f8ddd8bb4aae338873a887ec63
bound inventory_generated_at: 2026-08-19T17:32:42+00:00
inventory_binding.ok = true

st_nc_2026_std_ded_page.html is absent from freshness selected_artifacts
and is not in the validated NC 2026 deduction path.
NC 2026 standard deduction remains bound to
st_nc_2026_standard_deduction (2026 withholding-table artifact)
SHA 56a00f942c48c51019c3b78d72da1f1cc04969890678c107fe9d0386c5d655be.

==================================================
KNOWN-GOOD WAVE 3 RESULTS (UNCHANGED)
==================================================

WASHINGTON 2024
I-2111 authority_effective_date = 2024-06-06
pre-June House Finance report SHA 6afb4003…
full-year no general wage-income tax
Do not invent 2024-01-01 applicability for I-2111.

WASHINGTON 2026
ESSB 6346 authority_effective_date = 2026-06-11
tax_imposition_start = 2028-01-01
first_tax_year = 2028
tax_applies_to_year_2026 = false

PA 2024 / 2026: 3.07%, deduction 0, complete, STATE_CODE_MATCH
NC 2024: 4.50%, standard deduction 12,750 (2024 D-400/Schedule artifact)
NC 2026: 3.99% from G.S. 105-153.7 After 2025; deduction 12,750 from
2026 withholding-table artifact. Old 4.25% remains rejected by tests.
2025-labeled NCDOR landing page cannot complete/verify 2026 evidence.
IL 2024: 4.95%, personal exemption 2,775, complete
IL 2026: rate may be present; personal exemption unproven; cell incomplete.
Do not fabricate exemption = 0.

==================================================
STATE TAX COUNTS
==================================================

validated_2024_count = 12
validated_2026_count = 11
evidence_valid_2026_count = 11
live_verified_current_2026_count = 9
live_failed_2026 = NC, TX
taxing_pairs_completed = 2 (PA both years, NC both years)
taxing_pairs_unresolved = 40
(IL 2024 complete; IL 2026 incomplete; 40 remaining general-wage pairs
after PA+NC both years and IL 2024)

NC 2026 evidence remains VALIDATED. Live full-schedule extraction against
the current first-party surfaces did not re-establish the stored deduction,
so currentness is CHECK_FAILED rather than a weak rate-token verify.
TX 2026 no-tax evidence remains VALIDATED; live GET failed; CHECK_FAILED.

Family: INVENTORY_NOT_VALIDATED
freshness: CHECK_FAILED
states_modeled = 0

Empirical blockers = 7
gate reasons = 64

Federal tax: VALIDATED / VERIFIED_CURRENT
NAIC: VALIDATED / VERIFIED_CURRENT
EIA: VALIDATED / VERIFIED_CURRENT
OD-010: VALIDATED / VERIFIED_CURRENT (this freshness run)

==================================================
TESTS
==================================================

CI Tests & Code Quality: 363 passed, 5 skipped, 1 warning

New adversarial tests:

- test_currentness_a_cache_without_live_is_not_verified_current (preserved)
- test_currentness_b_live_failure_keeps_evidence_valid (preserved)
- test_taxing_historical_rate_with_different_2026_rate_is_not_current
- test_taxing_same_rate_changed_2026_deduction_is_not_current
- test_taxing_progressive_one_rate_present_changed_brackets_is_not_current
- test_taxing_exact_live_schedule_agreement_may_verify
- test_taxing_future_only_2027_change_does_not_invalidate_2026_schedule
- test_nc_2025_labeled_page_cannot_complete_or_verify_2026
- test_stale_freshness_cannot_claim_sync_with_newer_inventory
- test_production_freshness_is_bound_to_current_inventory
- test_inventory_sha_is_newline_invariant

==================================================
LOCKS
==================================================

candidate_calculation_authorized = false
living_cost.release_authorized = false
candidate_inputs_bound = false
states_modeled = 0
ready_for_private_candidate = false

No candidate-input binding file.
No MSLC.

State tax remains INVENTORY_NOT_VALIDATED. Validation thresholds were not
lowered.

==================================================
REMAINING UNRESOLVED WORK (NOT BEGUN)
==================================================

- 40 remaining general-wage-tax jurisdiction pairs
- IL 2026 personal exemption unproven
- Mandatory employee SDI/PFML/similar: OWNER_TAX_METHOD_DECISION_REQUIRED
- Local tax beyond already-retrieved overlays
- FCC/mobile, vehicle registration, vehicle replacement, BLS CE
- Family VALIDATED (requires 51 x 2 parsed_ok cells)
- MSLC / candidate assembler / candidate authorization

STOP. Do not proceed into State Tax Wave 4.
Do not extract additional states.
Do not calculate candidate MSLC.
