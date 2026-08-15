# THE FOUNDATION — LAST FRESHNESS-CONTROL CLEANUP STATUS

Started from audited HEAD: `6ed5ee9118b243d9bf416b048235053bdf547dcc`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**.

`candidate_calculation_authorized = false`  
`living_cost.release_authorized = false`  
`states_modeled = 0`

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**

The private candidate assembler was not built.

Status lines below are taken from the committed freshness artifact via
`freshness_status_summary()`. They are not a hand-written override.

---

## Completed this pass

1. **USDA years are separate.**
   `historical_2024`: 12 official months (January–December).
   `current_2026`: official YTD January–May (5 months).
   Top-level `months_included` is the 2026 YTD set. A complete 2024 series
   cannot overwrite 2026 YTD.

2. **USDA workbook URLs are parsed official FNS hrefs.**
   No constructed `fna.usda.gov` URLs in freshness discovery.
   Example: `https://www.fns.usda.gov/sites/default/files/resource-files/usda-lowcostplan-sept2007-present.xlsx`

3. **CMS checks both federal Exchange PUF and standalone SBE PUF listings.**
   Combined family is `VERIFIED_CURRENT` only when both checks succeed.
   Federal-only success does not pass the family.

4. **Public authorization gates have no override parameters.**
   Tests monkeypatch `definitions()`. Config is the sole authority.
   Both flags remain false.

5. **Pipeline release logic is no longer inverted.**
   `release_authorized=true` would fail as
   “Public living-cost release engine is not implemented/approved.”
   It does not say “not authorized.”
   Candidate=true no longer calls the freshness gate with `{}`.

6. **NAIC discovery uses `https://content.naic.org/publications`.**
   The obsolete 404 research-actuarial-services URL is gone.
   Latest identifier is parsed from the page. Evidence remains
   `RETRIEVED_UNVALIDATED`.

7. **NHTS has an optional FHWA corroboration page.**
   If both official checks fail, status stays `CHECK_FAILED`.

8. **Blocker accounting is split.**
   `empirical_blocker_family_count = 12`
   `gate_blocker_reason_count = 24`
   These are not 24 missing datasets.

## Actual discovery statuses (committed artifact)

```
acs_population_weights: VERIFIED_CURRENT
hud_fmr: VERIFIED_CURRENT
usda_food: VERIFIED_CURRENT
cms_marketplace_sbe: VERIFIED_CURRENT
meps_full_year_consolidated: VERIFIED_CURRENT
nhts_mileage: CHECK_FAILED
epa_vehicle: VERIFIED_CURRENT
eia_gasoline: VERIFIED_CURRENT
naic_auto_insurance: VERIFIED_CURRENT
bls_ce: CHECK_FAILED
fcc_broadband: CHECK_FAILED
mobile_price: SOURCE_GAP
bea_rpp: VERIFIED_CURRENT
federal_tax_law: MANUAL_VERIFICATION_REQUIRED
state_tax_law: MANUAL_VERIFICATION_REQUIRED
local_tax_law: MANUAL_VERIFICATION_REQUIRED
vehicle_registration: SOURCE_GAP
vehicle_replacement: SOURCE_GAP
od010_price_index: MANUAL_VERIFICATION_REQUIRED
```

USDA 2024 months: January–December (12)  
USDA 2026 YTD months: January–May (5)  
CMS federal: VERIFIED_CURRENT  
CMS SBE: VERIFIED_CURRENT  
NAIC: VERIFIED_CURRENT (publications listing)  
BEA: VERIFIED_CURRENT  
NHTS: CHECK_FAILED

## NOT COMPLETED

- Private candidate engine (not authorized)
- Public MSLC / Gap / Adequacy / rankings / national median / Composite
- 12 empirical evidence blocker families
- Bound OD-010 translation table
- Bound replacement inputs
- Official BLS CE ZIP retrieve
- Successful NHTS / BLS CE listing / FCC discovery
- 51-state tax / registration inventories

## Next

Do not calculate an MSLC. A later owner may set
`candidate_calculation_authorized: true` only after freshness can pass.
Publication still needs `release_authorized` and a built release engine.
