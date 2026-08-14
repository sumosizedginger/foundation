# Deliverable 2A closeout

**Exact commit SHA:** `b2a30ef4b87a2db38eb5f7d982e0e8b5c9b63b4c`

**NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.**

No Gap, Adequacy Ratio, state ranking, national median living cost, or composite living-cost score was calculated or published. `states_modeled = 0`.

## Workflows

GitHub Actions remain on `actions/checkout@v5`, `actions/setup-python@v6`, `actions/setup-node@v5` with Node 24.

## Tests

Unit suite (excluding integration): 73 passed at last local run.

## Source coverage before vs after this pass

Before: 38 blocking component/year combinations; food/BLS/HUD/ACS/EIA/BEA largely SOURCE_GAP or RETRIEVED_UNVALIDATED; USDA not retrieved.

After:

### Validated / modeled

- Housing: official HUD FY2024 `FMR2024_final_revised.xlsx` and FY2026 `FY26_FMRs_revised.xlsx` parsed (3228 / 3229 county 1BR rows).
- Population weights: official 2024 ACS 5-Year B01001 summary file, 3144 county-equivalents, 261,404,665 adults.
- Food: official CNPP Low-Cost / Thrifty / AK / HI Excel archives. 2024 annual average; 2026 YTD FOOD COST. Midpoint × 1.20 is MODELED_FROM_MEASURED_INPUTS.
- Mileage: 2022 NHTS V2.1 observed HHSIZE=1 / WRKCOUNT=1 ANNMILES with mean/median/P25/P75.
- Gas: EIA `pswrgvwall.xls` weekly regular retail; PADD/regional not labeled state-measured.
- Essentials / recreation: BLS CE Interview 2024 FMLI, MODELED_FROM_MEASURED_INPUTS, P20/P25/P30 recorded, no percentile frozen.
- RPP: official BEA SARPP 2024 All-items, 51 states + DC. 2026 uses SOURCE VINTAGE 2024 / PROJECT COST YEAR 2026.

### Retrieved but not nationally validated

- CMS federal-platform Rate / Plan / Service Area / Benefits zips retrieved. Join is implemented. 17 standalone SBE states plus some federal-platform gaps remain. `health_premium` is RETRIEVED_UNVALIDATED.
- MEPS HC-251 (2023 data year) zip retrieved. Official `h251.dat` is fixed-width; codebook-driven microdata parse is not yet VALIDATED. Required OOP statistic remains an owner decision (OD-002).

### Gaps / licensing / owner review

- MPG, maintenance, replacement: ESTIMATED_OWNER_REVIEW (28 MPG / $1,200 / $1,600 removed from production defaults).
- Registration: SOURCE_GAP (uncited 51-state table deleted).
- Insurance: LICENSING_REVIEW (NAIC).
- Connectivity: SOURCE_GAP / owner review (OD-009).
- State tax: inventory exists, not validated against primary PDFs.
- Local tax: classification A/B/C/D; municipal overlay is OD-011.
- Federal tax: coded tables exist and have boundary tests; IRS PDFs not retrieved, so not VALIDATED.

## HUD join

2024: 3135 / 3144 ACS geographies matched (~99.7% counties, ~98.9% adult population). Unmatched: Connecticut planning regions 09110–09190 (OD-013).

## CMS geography

Federal-platform Rate/Plan/Service Area/Benefits join produced 378 (2024) and 349 (2026) lowest-Silver rating areas. Service-area county rows: 2127 (2024), 1929 (2026). SBE 2024 official zip 404; SBE 2026 zip is documentation-only. `health_premium` remains RETRIEVED_UNVALIDATED.

## USDA months

2024 Low-Cost: 12 months annual average. 2026 Low-Cost: available months labeled YTD FOOD COST.

## Remaining blockers

See `living_cost_source_coverage.json` `blocking_components`. Typical remaining: health_oop, mpg, insurance, maintenance, registration, replacement, connectivity, state_tax, local_tax, and CMS SBE completeness.

## Owner decisions required

OD-001 through OD-013 in `living_cost_owner_decisions_pending.md`.

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.
