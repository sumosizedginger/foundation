# Living-cost owner decisions pending

No Minimum Sustainable Living Cost headline was calculated or published.

## OD-001 — Which ACS adult-population vintage should weight both 2024 and 2026 cost distributions?

**Why it matters:** Changing weights between vintages confounds cost change with population-mix change.

- Option A: Freeze 2024 ACS 5-Year adult 18+ for both cost years (implemented as the current candidate).
- Option B: Use 2023 ACS 5-Year for both years.
- Option C: Use a different vintage for each cost year.

**Recommended:** A
**Directional effect:** Holds geography mix constant so 2024 vs 2026 cost movement is a cost change.
**Source support:** Census ACS 5-Year B01001 official summary file acsdt5y2024-b01001.dat.
**Sensitivity:** Recompute state ranks with 2023 ACS weights after owner approval.

## OD-002 — Which MEPS OOP statistic is the headline healthcare utilization amount?

**Why it matters:** Mean is pulled by high spenders; median is more typical; P75 is a stress case.

- Option A: Weighted mean among adults 18-64 with private insurance.
- Option B: Weighted median among the same population.
- Option C: Publish mean as primary with median/P75 sensitivity.

**Recommended:** C
**Directional effect:** Mean raises healthcare vs median.
**Source support:** MEPS HC-251 2023 Full Year Consolidated (newest official FY file; 2024 FY due later).
**Sensitivity:** Report mean, median, P75 once microdata parse is validated.

## OD-003 — Is observed NHTS mileage the living-cost mileage, or is a lower minimum-necessary mileage required?

**Why it matters:** Observed 1-person/1-worker households travel far more than a commuting-only floor.

- Option A: Use measured NHTS weighted mean/median as mobility requirement.
- Option B: Define a separate MINIMUM NECESSARY MILEAGE assumption below observed travel.
- Option C: Use NHTS P25 as a conservative observed standard.

**Recommended:** C pending owner review; do not treat observed mean as 'necessary'.
**Directional effect:** Observed mean (~19,400 mi in current extract) raises transportation vs P25.
**Source support:** 2022 NHTS V2.1 hhv2pub+vehv2pub; ANNMILES; WTHHFIN; HHSIZE=1; WRKCOUNT=1.
**Sensitivity:** Publish P25/median/mean/P75 of observed miles; owner picks headline.

## OD-004 — What is the reference used vehicle and EPA combined MPG?

**Why it matters:** MPG scales fuel cost. 28 MPG in code is unsupported.

- Option A: EPA compact/midsize used-car combined MPG near the fleet median.
- Option B: Keep 28 MPG as ESTIMATED until EPA table is frozen.
- Option C: Use a documented specific model-year compact sedan.

**Recommended:** A after EPA table extract; until then ESTIMATED_OWNER_REVIEW.
**Directional effect:** Higher MPG lowers fuel cost.
**Source support:** EPA fueleconomy.gov public data; not yet frozen.
**Sensitivity:** 24 / 28 / 32 MPG.

## OD-005 — How should the vehicle replacement reserve be set?

**Why it matters:** The $1,600 path (10k-2k)/5 is normative, not measured.

- Option A: Acquisition minus salvage over usable years, all assumptions listed.
- Option B: BLS CE vehicle-purchase P25 among single-person units annualized.
- Option C: No reserve until owner approves a formula.

**Recommended:** A as ESTIMATED_OWNER_REVIEW; do not publish $1,600 as measured.
**Directional effect:** Shorter life or higher acquisition raises annual reserve.
**Source support:** None measured. Retired prototype used 10k/5yr/2k salvage.
**Sensitivity:** Acquisition 8k/10k/12k; life 5/7/10 years.

## OD-006 — What public source replaces licensed NAIC auto-insurance averages?

**Why it matters:** Insurance is mandatory where auto is the baseline.

- Option A: Licensed NAIC Auto Insurance Database Report if owner supplies artifact.
- Option B: State DOI public average-premium tables where they exist.
- Option C: Leave LICENSING_REVIEW / SOURCE_GAP; no commercial quote sites.

**Recommended:** C until a reusable public series is inventoried.
**Directional effect:** Missing insurance blocks VALIDATED transportation.
**Source support:** NAIC is licensed. No fabricated content.naic.org CSV.
**Sensitivity:** If owner licenses NAIC, ingest once with honest provenance.

## OD-007 — What is the maintenance + tires + repairs standard?

**Why it matters:** $1,200 in code is unsupported.

- Option A: BLS CE vehicle-maintenance/tires P25 among single-person positive spenders.
- Option B: Keep a labeled ESTIMATED reserve until CE parse is approved.
- Option C: Split ordinary maintenance, tires, and repairs if CE UCC codes support it.

**Recommended:** A+C after CE variables are verified against the official dictionary.
**Directional effect:** P25 is below mean maintenance spend.
**Source support:** BLS CE 2024 Interview PUMD (intrvw24.zip) retrieved and FMLI parsed.
**Sensitivity:** P20/P25/P30 on vehicle-maintenance/tires UCC codes after dictionary freeze.

## OD-008 — Which recreation percentile is the headline Social & Recreation amount?

**Why it matters:** Recreation must stay nonzero and modest.

- Option A: Weighted P25 among single-person positive spenders.
- Option B: P20.
- Option C: P30.

**Recommended:** A; publish P20/P25/P30 for review and do not freeze one.
**Directional effect:** Higher percentile raises Social & Recreation.
**Source support:** BLS CE Interview PUMD documented UCC/FMLI allowlist.
**Sensitivity:** P20/P25/P30 once CE is retrieved.

## OD-009 — What is the minimum connectivity standard?

**Why it matters:** Zero internet is not a sustainable adult life.

- Option A: One prepaid/postpaid mobile line + one residential broadband plan at a documented low-cost official series.
- Option B: Mobile-only.
- Option C: Broadband-only.

**Recommended:** A as Foundation minimum-service selection, not a measured typical bill.
**Directional effect:** Adding both line and broadband raises connectivity.
**Source support:** FCC Urban Rate Survey / ACS computer-internet tables are candidates; not frozen.
**Sensitivity:** Mobile-only vs mobile+broadband.

## OD-010 — How should lagging 2026 structural sources be translated?

**Why it matters:** Relabeling 2024 observations as 2026 is forbidden.

- Option A: LATEST_AVAILABLE for structural survey files; RULE_YEAR for tax; YTD for monthly prices.
- Option B: CPI-update every lagged dollar series.
- Option C: Refuse 2026 costs until every source has a 2026 observation.

**Recommended:** A with explicit project_cost_year / source_data_year / translation_method on every component.
**Directional effect:** CPI-updating raises 2026 vs holding latest available.
**Source support:** GROK.MD §25 translation methods.
**Sensitivity:** Show 2026 under LATEST_AVAILABLE vs CPI_UPDATED.

## OD-011 — How should municipal earned-income taxes that do not map to county geography be handled?

**Why it matters:** NYC and Philadelphia are not statewide.

- Option A: Attach tax only to counties that contain the taxing city; other counties UNAVAILABLE for local tax.
- Option B: Ignore municipal taxes until a place-level geography is authorized.
- Option C: Invent a statewide average local tax.

**Recommended:** A. Never C.
**Directional effect:** A raises living cost only in affected counties.
**Source support:** GROK.MD local-tax classification A/B/C/D.
**Sensitivity:** Compare county results with and without municipal overlay.

## OD-012 — Is an additional resilience reserve required after vehicle/health/clothing replacement is already annualized?

**Why it matters:** An extra 5%/10%/$1,200 buffer double-counts if replacement is already inside components.

- Option A: No extra reserve until a documented uncovered irregular cost is identified.
- Option B: Add a small ESTIMATED reserve after an overlap audit.
- Option C: Add 5% of net needs.

**Recommended:** A.
**Directional effect:** Any extra reserve raises gross required income.
**Source support:** GROK.MD resilience section; retired buffers are not authorized.
**Sensitivity:** None until owner requests one.

## OD-013 — How should Connecticut ACS planning regions be joined to HUD county FMR rows?

**Why it matters:** 2024 ACS 5-Year uses Connecticut planning-region FIPS (09110-09170). HUD FMR still publishes legacy county FIPS. Nine ACS geographies (about 2.9 million adults) currently unmatched.

- Option A: Build an official CT OPM/Census crosswalk from planning regions to legacy counties and allocate FMR.
- Option B: Leave CT unmatched until HUD publishes planning-region FMR.
- Option C: Assign a statewide CT 1BR FMR to unmatched planning regions.

**Recommended:** A if an official crosswalk exists; otherwise B. Never invent county rents.
**Directional effect:** B excludes ~1.1% of national adult population from the housing join.
**Source support:** living_cost_geo_join_2024.json unmatched_census_counties 09110-09190.
**Sensitivity:** Recompute CT after an official crosswalk is frozen.
