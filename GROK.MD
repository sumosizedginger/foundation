# THE FOUNDATION — STATE TAX WAVE 4 CLOSEOUT

IL-2026 + FIRST FLAT-TAX EXTRACTION TRANCHE

This file records facts after Wave 4. It is not an authorization to reopen
Wave 3, federal tax, NAIC, EIA, OD-010, local tax, or candidate MSLC.

==================================================
IMPLEMENTATION SHA
==================================================

064962df2dd2fcb39d29f2f146b64cca2669ae3b

PARENT SHA (documentation):
f48ff2b8aa6f30110a44bab1bbba197a7f65a709

FUNCTIONAL PARENT (Wave 3 audit-defect closeout):
105bf68533fd00804de9fde80b6445984a495a2a

Do NOT reuse 105bf68 runs 32301984639 / 32301984717 / 32301984723
or 5d8e9cc runs as Wave 4 CI evidence.

==================================================
PRE-FLIGHT HARDENING
==================================================

compare_live_schedule_to_cell() now requires live_extracted.complete is True.

- live_extracted is None -> incomplete -> CHECK_FAILED
- live_extracted.complete is not True -> incomplete -> CHECK_FAILED
- complete + field mismatch -> NEWER_AVAILABLE
- complete + exact modeled equivalence -> VERIFIED_CURRENT

No-tax currentness was not changed.

Regression:
tests/test_state_tax_inventory.py::test_taxing_incomplete_live_extraction_is_not_verified_current

A matching subset of rate/deduction/exemption with complete=False MUST NOT
return VERIFIED_CURRENT.

==================================================
WAVE 3 INVARIANTS — STILL TRUE
==================================================

Washington 2024: I-2111 authority_effective_date = 2024-06-06; preexisting
no-wage-tax evidence remains separate; no fabricated January 1.

Washington 2026: ESSB 6346 authority_effective_date = 2026-06-11;
tax_imposition_start = 2028-01-01; first_tax_year = 2028; does not apply
to RULE_YEAR 2026.

Pennsylvania 2024/2026: 3.07%; no standard deduction; both complete.

North Carolina 2024: 4.50%. North Carolina 2026: 3.99%.
2024 deduction stays on the 2024 artifact. 2026 deduction stays on the
2026 withholding artifact. A 2025-labeled landing page remains invalid
for 2026. Live NC 2026 CHECK_FAILED is still honest.

Illinois 2024 remains 4.95% with personal exemption 2,775.

==================================================
TARGET CELLS
==================================================

IL 2026
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- rate: 4.95% from IDOR income-tax rates page
  https://tax.illinois.gov/research/taxrates/income.html
  artifact st_il_2026_schedule sha256
  96a4db285da69ec40c770182b9e89238cdda9efff8402ae8ad1813d6be3eecf7
- standard deduction: not established
- personal exemption: NOT ESTABLISHED
- starting income base: Illinois net income
- unresolved: 35 ILCS 5/204 (7) sets 2024–2028 at $2,050 plus COLA.
  IDOR "currentyear" IL-1040 instructions are the 2025 booklet
  (exemption $2,850; due date April 15, 2026). That is not tax-year 2026
  identity. 2026 Form IL-1040 instructions were not posted. Did not copy
  2024 $2,775. Did not inflate. Did not fabricate zero.

AZ 2024
- tax_status: GENERAL_WAGE_INCOME_TAX
- parsed_ok: true
- code_match: STATE_CODE_MATCH
- rate: 2.5%
- standard deduction: 14,600 (SINGLE)
- personal exemption: 0 (Form 140 uses a standard deduction, not a
  taxpayer personal exemption subtracted from income)
- starting income base: Arizona taxable income after standard deduction
- authority: 2024 Form 140 booklet
  https://azdor.gov/sites/default/files/document/FORMS_INDIVIDUAL_2024_140Booklet.pdf
  artifact st_az_2024_form_140_booklet sha256
  32d7b7597c926ef7afcda7dded77e68fe050904ab8cff3a88970d73137d2ef7c
- A.R.S. 43-1041 $12,200 is the unindexed BASE and was not used as the
  2024 modeled deduction. The published azleg.gov A.R.S. 43-1011 page
  still shows pre-flat progressive brackets and was not treated as 2.5%
  proof.

AZ 2026
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- unresolved: no 2026 Form 140 booklet. 2025 booklet (single $15,750)
  was rejected as wrong-year. Did not copy 2024 $14,600.

IN 2024
- tax_status: GENERAL_WAGE_INCOME_TAX
- parsed_ok: true
- code_match: STATE_CODE_MATCH
- rate: 3.05%
- standard deduction: 0
- personal exemption: 1,000
- starting income base: Indiana adjusted gross income after personal exemption
- authority: 2024 IT-40 instruction booklet
  https://forms.in.gov/Download.aspx?id=16379
  artifact st_in_2024_schedule sha256
  baeb0f32c6838b49760c1330ed89abbe16033af1be6aedb14e83e0fd35395f6d
- County/local Indiana income tax was not modeled and was not folded
  into the state rate.

IN 2026
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- rate: 2.95% from official DOR Schedule EZ year windows
  After Dec. 31, 2025 and before Jan. 1, 2027 2.95%
  https://forms.in.gov/Download.aspx?id=2750
  artifact st_in_2026_schedule sha256
  bd6142014812c3112d7658103b04caad625a15332c946466e6c48752a3c0f258
- personal exemption: NOT ESTABLISHED for 2026. Did not copy 2024 $1,000.
- Parser does not let 3.00% (2025) or 2.90% (after Dec. 31, 2026) win.

KY 2024
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- rate: 4.00% from KRS 141.020
  "beginning on or after January 1, 2024, but before January 1, 2026,
  the tax shall be four percent (4%) of net income"
  https://apps.legislature.ky.gov/law/statutes/statute.aspx?id=56339
  artifact st_ky_2024_schedule sha256
  ba8f7b25f40ff55012f8e1713d4b4b58fcee9ac5a14b116e7b77c9c6a27b6777
- standard deduction: NOT ESTABLISHED. Prior catalog URL id=54091 was
  KRS 151.110 (water resources), not KRS 141.020. Replaced with the
  actual 141.020 PDF. Year-specific Form 740 deduction not bound.
  Did not use 2018 packet $2,530.

KY 2026
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- rate: 3.50% from the same KRS 141.020
  "beginning on or after January 1, 2026, the tax shall be three and
  one-half percent (3.5%) of net income"
- standard deduction: NOT ESTABLISHED. Later-year reduction-trigger
  language was not applied backwards or forwards as a 2026 deduction.

MI 2024
- tax_status: GENERAL_WAGE_INCOME_TAX
- parsed_ok: true
- code_match: STATE_CODE_MATCH
- rate: 4.25%
- standard deduction: 0 (MI-1040 uses personal exemption, not a
  federal-style standard deduction)
- personal exemption: 5,600
- starting income base: Federal AGI less Michigan personal exemption
- authority: 2024 MI-1040 instructions
  https://www.michigan.gov/taxes/-/media/Project/Websites/taxes/Forms/IIT/TY2024/MI-1040-Instructions.pdf
  artifact st_mi_2024_mi1040_instructions sha256
  70649c626de2e57ccc2ead002b8bbc5dab9c03c39fcb0fb88eda8d784ef1602a
- Historical 4.05% trigger language does not override the 2024 4.25%
  sentence on the same instructions.

MI 2026
- tax_status: STATE_EVIDENCE_INCOMPLETE
- parsed_ok: false
- unresolved: 2026 MI-1040 instructions not posted. 2025 guidance
  (4.25% / $5,800) is the wrong year. Did not copy 2024 $5,600.

==================================================
STATE TAX COUNTS
==================================================

Start Wave 3 baseline -> Wave 4:

validated_2024_count: 12 -> 15
validated_2026_count: 11 -> 11
taxing_pairs_completed: 2 -> 2
taxing_pairs_unresolved: 40 -> 40
  (51 jurisdictions - 9 no-tax pairs - 2 completed taxing pairs)
evidence_valid_2026_count: 11
live_verified_current_2026_count: 9
live_failed_2026: NC, TX
newer_available_2026: []
family: INVENTORY_NOT_VALIDATED
states_modeled: 0

The +3 2024 cells are Arizona, Indiana, and Michigan. No 2026 target
closed, so no new completed taxing pair.

==================================================
FRESHNESS BINDING
==================================================

inventory generated_at: 2026-08-19T23:31:13+00:00
inventory LF-normalized SHA-256:
42ab5eda817eacdd400a2bd3a8827637e49aa5bf73b7448405dcb6c9f034d7ac

freshness generated_at: 2026-08-19T23:31:47Z
inventory_binding.ok: true
binding issues: []

Live BLS CPI during this freshness run hit the daily quota. OD-010 was
restored from the last valid live check (parent VERIFIED_CURRENT).
OD-010 was not redesigned. Cached translation-table evidence was not
demoted.

==================================================
TESTS
==================================================

Local: full pytest passed.
New parser/adversarial tests:
- test_taxing_incomplete_live_extraction_is_not_verified_current
- test_il_2024_exemption_does_not_copy_into_2026
- test_az_2024_form_140_schedule_and_wrong_year_rejection
- test_in_year_windows_and_exemption_not_first_percentage
- test_ky_2024_four_percent_not_later_3_5
- test_mi_2024_rate_is_not_historical_4_05

==================================================
GITHUB ACTIONS (SHA 064962d)
==================================================

Tests & Code Quality
- run ID 32314199110
- head SHA 064962df2dd2fcb39d29f2f146b64cca2669ae3b
- conclusion success
- https://github.com/sumosizedginger/foundation/actions/runs/32314199110

Validate Living Cost Sources
- run ID 32314199024
- head SHA 064962df2dd2fcb39d29f2f146b64cca2669ae3b
- conclusion success
- https://github.com/sumosizedginger/foundation/actions/runs/32314199024

Deploy Pages
- run ID 32314198977
- head SHA 064962df2dd2fcb39d29f2f146b64cca2669ae3b
- conclusion success
- https://github.com/sumosizedginger/foundation/actions/runs/32314198977

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

==================================================
UNRESOLVED TARGETS
==================================================

IL 2026: 2026 IL-1040 instructions / published COLA exemption amount.
AZ 2026: 2026 Form 140 booklet standard deduction.
IN 2026: 2026 IT-40 exemption (rate 2.95% is parsed).
KY 2024/2026: year-specific Form 740 / KRS 141.081 published deduction
  (rates 4.00% / 3.50% are parsed).
MI 2026: 2026 MI-1040 instructions rate and exemption.

Do not begin another jurisdiction.
Do not calculate MSLC.
Do not start Wave 5 from this file.
