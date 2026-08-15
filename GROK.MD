# THE FOUNDATION — OWNER FREEZE STATUS

OD-001 through OD-013

This file is the current work-order / history document after the owner-freeze
implementation. Anything not done is listed under NOT COMPLETED.

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.

`living_cost_release_authorized = false`. `states_modeled = 0`.

METHODOLOGY FROZEN is not SOURCE VALIDATED.

---

## What this pass was

Implement the owner's freeze of OD-001 through OD-013 into methodology,
decision records, configuration, source-selection logic, owner-decision
metadata, validation/release gates, tests, and project documentation.

Stop before any candidate economic calculation. Push. Report actual GitHub
Actions. Then stop for independent audit.

---

## Completed

- OD-001 through OD-013 recorded as **ACCEPTED / FROZEN** in
  `src/foundation/living_cost/owner_freeze.py` and
  `data/metadata/living_cost_owner_decisions_frozen.md`.
- Machine-readable freeze record includes decision, effective date, rationale,
  implementation rule, source-selection rule, required sensitivity, known
  evidence gaps, and whether a numeric value is currently available.
- Historical pending packet archived at
  `data/metadata/historical/living_cost_owner_decisions_pending.md`
  with SUPERSEDED / NOT CURRENT PROJECT STATUS header.
- D-043 added to `DECISIONS.md`. Methodology, validation, data-model, and
  project-status docs updated. Evolution of prior pending packets was not
  rewritten in place.
- Config: `config/definitions.yml` living_cost owner-freeze block.
- OD-001: `select_acs_weight_vintage` — current uses newest available ACS
  5-Year county vintage (today 2024); historical 2024 locked to 2024 ACS;
  fixed-2024-weight sensitivity retained.
- OD-002: weighted mean primary; median / P75 required sensitivities;
  HC-251 / 2023 until a later Full Year Consolidated file is actually listed.
- OD-003: NHTS parser canonical value is now the weighted median, labeled
  FOUNDATION MOBILITY STANDARD. Mean / P25 / P75 remain sensitivities.
- OD-004: used-car compact+midsize gasoline cohort; median MPG; 8–12 year
  window; 24/28/32 forbidden as hardcoded model.
- OD-005: formula `(acquisition − residual) / remaining years` exists.
  No $1,600 / $10,000 / $2,000 / 5-year defaults. Numeric result pending.
- OD-006: combined average premium is canonical.
- OD-007: weighted mean including zeros is canonical. Evidence remains
  `INCOMPLETE_PROVENANCE`. Freeze does not promote it to VALIDATED.
- OD-008: canonical recreation can never fall below $1,200/year.
  Preferred modest-life can never fall below $2,400/year.
- OD-009: canonical connectivity requires mobile AND broadband (100/20).
  Mobile price evidence remains SOURCE_GAP.
- OD-010: hybrid translation methods encoded. Lagged nominal dollars cannot
  use silent LATEST_AVAILABLE carry-forward.
- OD-011: A/B/C/D classification. Partial-city tax cannot be applied
  automatically to an entire county.
- OD-012: canonical extra resilience reserve is $0.
- OD-013: 2024 CT reconstruction; 2026 direct planning-region join.
- Additional freezes encoded: USDA Low-Cost canonical / Thrifty sensitivity;
  age-40 single nonsmoker unsubsidized Silver; independent 1-bedroom HUD FMR.
- Freshness gate checklist exists and does not authorize a headline.
- Release gate still hard-coded `living_cost_release_authorized = False`.
- Tests added in `tests/test_owner_freeze.py` (21 tests). Existing pending
  / unfrozen assertions updated.
- Local pytest: 123 collected, all passed, 1 warning (same
  `load_module` deprecation as before). This is LOCAL, not GitHub CI.
- Dual verifiers for harness `1a8e040d9593` required before goal close.

## Preserved prior-pass facts (not reopened)

- CPS 2025 ASEC canonical SHA
  `318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b`
- 2024 ACS raw county-equivalent count 3144 vs join geography 3143
- 100% modeled 50-state+DC housing coverage on the 2024 join
- Oklahoma 2024 is HealthCare.gov FFM, not SBE-FP
- Arkansas and Oregon 2024 are SBE-FP from year-specific CMS evidence
- Oregon SBE archive is SHOP-only
- VQB combined mean-including-zeros candidate $781.22
- BLS CE cache `INCOMPLETE_PROVENANCE` (official retrieve 403)

## NOT COMPLETED

- **Candidate MSLC calculation** for 2024 or 2026. Not authorized by this pass.
- **Gap, Adequacy Ratio, state rankings, national median MSLC, Composite.**
- **`living_cost_release_authorized` remains false.**
- **BLS CE official retrieve** still HTTP 403 / INCOMPLETE_PROVENANCE.
  Do not fabricate `retrieved_at`. Do not promote to VALIDATED.
- **FCC URS / broadband price retrieve** historically 403 → connectivity
  evidence SOURCE_GAP.
- **Mobile price** SOURCE_GAP. Methodology frozen; no invented price.
- **Vehicle registration** SOURCE_GAP.
- **Vehicle replacement numeric inputs** (acquisition, residual, usable years)
  not yet bound. Formula only.
- **NAIC state-table extraction** not yet a validated numeric series.
- **MEPS 2024 Full Year Consolidated** not claimed unless the official PUF
  listing actually has it. HC-251 / 2023 remains the listed file at freeze.
- **Federal tax tables** INVENTORY_NOT_VALIDATED.
- **State/local tax inventory** incomplete. Place-level municipal calculation
  is not generally supported.
- **Multi-year CE vintage pool** for lumpy repairs — preferred later, not
  required before a first later candidate.
- **Independent audit** after this push — next human task before any
  candidate economic calculation.
- **GitHub Actions exact results** for this freeze commit will be reported
  after push. Do not treat local 123-passed as GitHub CI.
- Leftover “36 tests” wording in PROJECT_STATUS.md (pre-existing nit).
- Untracked local `tmp_inspect_*.py` (intentionally not committed).

## Next human task

Independent audit of this owner-freeze implementation.

Then, only if authorized by a later owner work order: freshness-gate
re-check of volatile sources and a candidate economic calculation pass.

Until that authorization: do not calculate or publish a living-cost headline.
