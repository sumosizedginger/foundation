# THE FOUNDATION — STATE TAX WAVE 3 CLOSEOUT
# EFFECTIVE-DATE TRUTH + REAL CURRENTNESS + TAXING-STATE EXTRACTION

IMPLEMENTATION SHA:
5d8e9cc8a0d3ea80f897807c1f059fe24f284ce9

INVENTORY SHA:
5dbac1efa42718f2f592035430c094ef44569e779b869016ee4633486de7ff19

GITHUB ACTIONS (head 5d8e9cc):
- Tests & Code Quality 32278258913 success
  354 passed, 5 skipped, 1 warning
- Validate Living Cost Sources 32278258828 success
- Deploy Pages 32278258798 success

Local pytest: 354 passed, 5 skipped, 1 warning (CI identical).

==================================================
WASHINGTON 2024
==================================================

pre-June evidence authority:
  Washington House Finance Committee report on Initiative 2111
  https://lawfilesext.leg.wa.gov/biennium/2023-24/Pdf/Bill%20Reports/House/I2111%20HIB%20FIN%2024.pdf
  SHA 6afb40039d86f2bb71223290411cc495c3ffb7e1a50c51febb1c613b3ef93ccc
  Official committee record: the initiative codifies the state's longstanding
  tradition of not having an income tax on personal income and does not capture
  existing revenue sources.

Initiative 2111 / Chapter 5, Laws of 2024:
  SHA db4e7e5f98602c99d87a4583ff1acf5d437793072a09e5c0006bc2c0c764d019
  authority_effective_date = 2024-06-06
  (parsed from session-law header EFFECTIVE DATE: June 6, 2024)
  role = prospective prohibition

rule_year_2024_result:
  no general wage-income tax for the full tax year

Do not invent January 1, 2024 applicability for Initiative 2111.

==================================================
WASHINGTON 2026
==================================================

ESSB 6346 / Chapter 238, Laws of 2026:
  authority_effective_date = 2026-06-11
  (session-law header EFFECTIVE DATE: June 11, 2026)

tax_imposition_start = 2028-01-01
first_tax_year = 2028
tax_applies_to_year_2026 = false

Session-law effective date and tax imposition date are recorded separately.
2026 ordinary wage income tax remains 0.

==================================================
CURRENTNESS
==================================================

evidence_valid_2026_count = 11
live_verified_current_2026_count = 10
verified_current_2026_count = 10  (same as live; not cached SHA-counting)
live_check_performed = true
live_failed_2026 = TX
  Texas 2026 no-tax artifact remains VALIDATED.
  Targeted live currentness GET did not confirm current wording.
  freshness CHECK_FAILED; newer_data_exists = null.
  Evidence is not demoted.

Cached SHA + URL is not VERIFIED_CURRENT.
CURRENTNESS_PENDING is not counted as verified.
Family freshness CHECK_FAILED (not all 51 live-verified).

==================================================
TAXING JURISDICTIONS
==================================================

new state/year cells closed:
  PA 2024  GENERAL_WAGE_INCOME_TAX  3.07%  deduction 0  STATE_CODE_MATCH
  PA 2026  GENERAL_WAGE_INCOME_TAX  3.07%  deduction 0  STATE_CODE_MATCH
  NC 2024  GENERAL_WAGE_INCOME_TAX  4.50%  std ded 12750  STATE_CODE_MATCH
  NC 2026  GENERAL_WAGE_INCOME_TAX  3.99%  std ded 12750  STATE_CODE_MATCH
  IL 2024  GENERAL_WAGE_INCOME_TAX  4.95%  personal exemption 2775  STATE_CODE_MATCH

states fully closed for both years:
  PA, NC
  (plus the 9 no-general-wage-tax jurisdictions)

states with code corrections:
  NC 2026: candidate table 4.25% replaced with official G.S. 105-153.7
  After 2025 rate 3.99%. Old 4.25% behavior recorded in tests.

states with model gaps:
  IL 2026: official 4.95% parsed; personal exemption not on the 2026 artifact.
  Remaining taxing landing pages retrieved where HTTP succeeded; rates not
  extracted.

states still unresolved:
  40 taxing-jurisdiction pairs (42 minus PA and NC).
  IL is 2024-only.

validated_2024_count = 12
validated_2026_count = 11
no-general-wage-tax count (both years) = 9
  AK FL NV NH SD TN TX WA WY
taxing-state pairs completed = 2
taxing-state pairs unresolved = 40

Family: INVENTORY_NOT_VALIDATED / freshness CHECK_FAILED
states_modeled = 0  (public lock; official extracted cells are inventory, not MSLC)

==================================================
COUNTS
==================================================

empirical_blocker_family_count = 7
gate_blocker_reason_count = 64

Federal tax VALIDATED / VERIFIED_CURRENT (unchanged).
NAIC VALIDATED / VERIFIED_CURRENT (unchanged).
EIA closed (unchanged).
OD-010 live retrieve this run: VERIFIED_CURRENT (not redesigned).

==================================================
LOCKS
==================================================

candidate_calculation_authorized=false
living_cost.release_authorized=false
candidate_inputs_bound=false
states_modeled=0
ready_for_private_candidate=false

No candidate-input binding file.
NO MSLC.

==================================================
STOP
==================================================

Productive taxing-state extraction run closed PA and NC for both years
and IL 2024. Stopped.

Did not begin:
  local tax
  FCC/mobile
  BLS CE
  vehicle registration
  vehicle replacement
  candidate calculation.
