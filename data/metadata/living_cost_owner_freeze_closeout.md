# Living-cost owner freeze closeout

**Effective date:** 2026-08-15  
**Decision record:** D-043 / `living_cost_owner_decisions_frozen.md`

OD-001 through OD-013 are **ACCEPTED / FROZEN**.

`living_cost_release_authorized = false`. `states_modeled = 0`.

**No Minimum Sustainable Living Cost headline was calculated or published.**

METHODOLOGY FROZEN is not SOURCE VALIDATED.

## Frozen decisions

- OD-001 — ACS geographic population weights (freshest appropriate + fixed-2024 sensitivity)
- OD-002 — MEPS OOP weighted mean primary; median/P75 sensitivity
- OD-003 — NHTS weighted median Foundation Mobility Standard
- OD-004 — used-car compact+midsize gasoline cohort; median MPG; no hardcoded 24/28/32
- OD-005 — replacement formula frozen; numeric inputs pending; no $1,600 default
- OD-006 — NAIC combined average premium
- OD-007 — weighted mean including zeros; evidence remains INCOMPLETE_PROVENANCE
- OD-008 — MAX(empirical P25, $1,200) canonical; MAX(empirical P25, $2,400) preferred modest life
- OD-009 — mobile + broadband canonical; mobile price SOURCE_GAP
- OD-010 — hybrid translation; no silent LATEST_AVAILABLE nominal carry-forward
- OD-011 — municipal earned-income tax geography/overlay A/B/C/D
- OD-012 — additional resilience reserve = $0
- OD-013 — Connecticut HUD/ACS geography treatment (2024 reconstruction; 2026 direct join)

## Remaining evidence gaps (not solved by freeze)

- BLS CE official retrieve HTTP 403 / INCOMPLETE_PROVENANCE
- FCC URS retrieve historically 403 / connectivity SOURCE_GAP
- Mobile price SOURCE_GAP
- Vehicle registration SOURCE_GAP
- Vehicle replacement numeric inputs pending
- State/local tax inventory incomplete
- Federal tax tables INVENTORY_NOT_VALIDATED
- MEPS 2024 Full Year Consolidated not claimed unless officially listed
- NAIC state-table extraction not yet a validated numeric series
