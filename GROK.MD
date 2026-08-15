# THE FOUNDATION — LAST FRESHNESS-CONTROL CLEANUP STATUS

Cleanup SHA: `32a6abf2bf0ecc8df29e1e53105258b831ed8b76`  
Started from audited HEAD: `6ed5ee9118b243d9bf416b048235053bdf547dcc`

OD-001 through OD-013 remain **ACCEPTED / FROZEN**. They were not reopened.

Authorization source of truth is only `config/definitions.yml`:

```yaml
living_cost:
  candidate_calculation_authorized: false
  release_authorized: false
```

`states_modeled = 0`  
`ready_for_private_candidate = false`  
`translation_index_bound = false`  
`headline_calculated = false`

**NO MINIMUM SUSTAINABLE LIVING COST WAS CALCULATED OR PUBLISHED.**

The private candidate assembler was not built.

---

## GitHub CI (implementation SHA `32a6abf`)

These are GitHub Actions results, not local pytest.

| Workflow | Run | Result |
|---|---|---|
| Tests & Code Quality | [31866623783](https://github.com/sumosizedginger/foundation/actions/runs/31866623783) | **success — 151 passed, 5 skipped, 1 warning** |
| Validate Living Cost Sources | [31866623766](https://github.com/sumosizedginger/foundation/actions/runs/31866623766) | **success** |
| Deploy Pages | [31866623729](https://github.com/sumosizedginger/foundation/actions/runs/31866623729) | **success** |

Dual independent verifiers: both `VERDICT: PASS`  
(`/tmp/goal-verifier-23a579966517-code-review.md`, `/tmp/goal-verifier-23a579966517-qa.md`).  
PASS issues were `[nit]` only.

---

## Completed this pass

1. **USDA years stay separate.**  
   `historical_2024`: 12 official months, January–December.  
   `current_2026`: official YTD January–May (5 months).  
   Top-level `months_included` is the 2026 YTD set.  
   `substituted_2024_for_2026 = false`.  
   A complete 2024 series cannot overwrite 2026 YTD.

2. **USDA workbook URLs are parsed official FNS hrefs.**  
   Discovery and the download adapter do not construct `fna.usda.gov` URLs.  
   Example: `https://www.fns.usda.gov/sites/default/files/resource-files/usda-lowcostplan-sept2007-present.xlsx`  
   Missing hrefs fail closed to the official FNS landing.

3. **CMS records the federal + standalone SBE artifacts actually used.**  
   Combined family is `VERIFIED_CURRENT` only when both listing checks succeed.  
   Federal-only success does not pass the family.  
   Artifact list includes hashed federal PUF files and year-specific SBE archives, including `cms_sbe_or_2024` and `cms_sbe_or_2026`.  
   Oregon individual-market source remains `federal_exchange_puf`.  
   Oregon SBE archive remains **SHOP-only** in `living_cost_cms_sbe_lowest_silver.json` (`market_scope: SHOP_only`) and is not treated as individual-market QHP.

4. **Authorization has one source of truth.**  
   Public gates have no override parameters.  
   Readers load `config/definitions.yml` and fail closed if the config is absent or malformed.  
   Both flags remain false.

5. **Pipeline release logic is not inverted.**  
   `release_authorized=true` would fail as  
   “Public living-cost release engine is not implemented/approved.”  
   It does not say “not authorized.”  
   Candidate=true no longer calls the freshness gate with `{}`.

6. **NAIC official landing is the real publications listing.**  
   Landing: `https://content.naic.org/publications` (HTTP 200).  
   Obsolete `research-actuarial-services/auto-insurance-database-report` 404 is gone from source modules.  
   Leftover `content.naic.org/sites/default/files/inline-files/` FNA URLs are gone from live code/registry.  
   Latest identifier is parsed from the page. Evidence remains `RETRIEVED_UNVALIDATED`.

7. **NHTS has an optional FHWA corroboration page.**  
   If both official checks fail, status stays `CHECK_FAILED`.

8. **Blocker accounting is split.**  
   `empirical_blocker_family_count = 12`  
   `gate_blocker_reason_count = 24`  
   These are not 24 missing datasets.  
   Freshness artifact still **FAIL**s. That is correct.

9. **Freshness remains a real check.**  
   `timestamps_from_hardcoded_snapshot = false`.  
   Statuses used: `VERIFIED_CURRENT` / `NEWER_AVAILABLE` / `CHECK_FAILED` / `MANUAL_VERIFICATION_REQUIRED` / `SOURCE_GAP`.

---

## Actual discovery statuses (committed artifact)

From `freshness_status_summary()`, not a hand-written override:

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

Automated/verified discovery: ACS, HUD, USDA, CMS, MEPS listing, EPA, EIA, NAIC listing, BEA RPP.  
Manual: federal / state / local tax, OD-010.  
Check failed: NHTS, BLS CE, FCC.  
Source gap: mobile price, vehicle registration, vehicle replacement.

USDA 2024 months: January–December (12)  
USDA 2026 YTD months: January–May (5)  
CMS federal: VERIFIED_CURRENT  
CMS SBE: VERIFIED_CURRENT  
NAIC: VERIFIED_CURRENT (publications listing; tables unvalidated)  
BEA: VERIFIED_CURRENT  
NHTS: CHECK_FAILED

---

## NOT COMPLETED

These remain open. This pass did not paper over them.

- Private candidate engine (not authorized; do not build)
- Public MSLC / Gap / Adequacy / rankings / national median / Composite
- `candidate_calculation_authorized` still false
- `living_cost.release_authorized` still false
- Bound OD-010 CPI/medical translation table (`OD010_TRANSLATION_INDEX_NOT_BOUND`)
- Bound vehicle-replacement inputs (acquisition / residual / usable years)
- Official BLS CE ZIP retrieve (HTTP 403 / `INCOMPLETE_PROVENANCE`)
- Successful NHTS listing discovery
- Successful FCC Urban Rate Survey retrieve (HTTP 403 / `SOURCE_GAP`)
- Mobile phone price (`SOURCE_GAP`)
- Vehicle registration inventory (`SOURCE_GAP`)
- NAIC state-table extraction (`RETRIEVED_UNVALIDATED`)
- Federal tax inventory (`INVENTORY_NOT_VALIDATED`)
- State/local tax inventories; most FIPS unresolved; class-C overlay not generally implemented
- MEPS health OOP derivation (`RETRIEVED_UNVALIDATED`; newest released FY Consolidated is HC-251 / 2023; 2024 scheduled Aug 2026 ≠ released)
- EPA MPG cohort extraction (`RETRIEVED_UNVALIDATED`; methodology frozen ≠ validated evidence)
- 12 empirical evidence blocker families

Leftover nits (not blockers; do not treat as current):

- `living_cost_source_manifest.json` USDA `landing_page` still uses a host-swapped `fns.usda.gov/research/cnpp/...` path. Live GET 200s to the same official Cost of Food page. Workbook `url` / `resolved_url` are official FNS hrefs.
- Historical USDA cache `.provenance.json` sidecars still record old `fna.usda.gov` URLs. Live download/discovery no longer constructs that host.

---

## Next

Do not calculate an MSLC.

A later owner may set `candidate_calculation_authorized: true` only after freshness can pass.

Publication still needs `release_authorized` and a built, approved release engine. Candidate authorization never implies publication.

STOP.
