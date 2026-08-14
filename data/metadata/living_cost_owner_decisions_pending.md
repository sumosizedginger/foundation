# Living-cost owner decisions pending

No Minimum Sustainable Living Cost headline was calculated or published.

Owner decisions are **not frozen**. No OD is marked ACCEPTED.

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
**Source support:** HC-251 (2023 Full Year Consolidated) remains the latest actually listed full-year MEPS file as of 2026-08-14. AHRQ's official 2026 release schedule (https://meps.ahrq.gov/mepsweb/about_meps/releaseschedule.jsp, page last updated July 31, 2026) lists the 2024 Full Year Consolidated Data File for AUGUST 2026. Do not claim the 2024 full-year file exists until it appears in the official MEPS PUF listing. A source-refresh check runs immediately before owner freeze / candidate calculation; if the 2024 FY file is listed it is retrieved, hashed, parsed, and preferred; otherwise HC-251 is used with true source year = 2023.
**Sensitivity:** Report mean, median, P75 once microdata parse is validated.

## OD-003 — Is observed NHTS mileage the living-cost mileage, or is a lower minimum-necessary mileage required?

**Why it matters:** Observed one-person working-age driver households travel far more than a commuting-only floor.

- Option A: Use measured NHTS weighted mean/median as mobility requirement.
- Option B: Define a separate MINIMUM NECESSARY MILEAGE assumption below observed travel.
- Option C: Use NHTS P25 as a conservative observed standard.

**Recommended:** C pending owner review; do not treat observed mean as 'necessary'.
**Directional effect:** Observed mean raises transportation vs P25.
**Source support:** 2022 NHTS V2.1: household file (HHSIZE=1, WRKCOUNT=1) joined to person file (R_AGE 18-64; DRIVER=1 when the field is present) and vehicle file (sum of ANNMILES; weight=WTHHFIN). Sample is labeled OBSERVED TRAVEL BEHAVIOR for one-person, one-worker, age-18-64 licensed-driver households with valid annual vehicle mileage — not MINIMUM NECESSARY MILEAGE. P25 / median / mean / P75 and unweighted sample count are all emitted.
**Sensitivity:** Publish P25/median/mean/P75 of observed miles; owner picks headline.

## OD-004 — Which EPA reference-vehicle cohort should set combined real-world MPG?

**Why it matters:** MPG scales fuel cost. This is a cohort decision, not a source-existence decision.

- Option A: Used-car window: gasoline (non-BEV, non-PHEV) compact/midsize passenger cars, model years approximately 8–12 years before the cost year, weighted/median combined real-world MPG from official EPA vehicle-level data.
- Option B: New-car window: same class/fuel filter on the latest final EPA model year (MY2024 detailed Automotive Trends / fueleconomy.gov vehicle file).
- Option C: A documented specific model-year compact/midsize gasoline sedan.

**Recommended:** A after owner review of candidate table; do not freeze 24/28/32.
**Directional effect:** Higher MPG lowers fuel cost. Used-car vs new-car window is typically lower MPG than new-car.
**Source support:** Official EPA Automotive Trends detailed data and/or EPA/DOE fueleconomy.gov vehicles file. Candidates include vehicle age/model-year window, class, fuel type, and weighted/median combined real-world MPG with sensitivity alternatives. Not frozen.
**Sensitivity:** Compare used-car vs new-car windows; compact vs midsize; median vs sales-weighted mean.

## OD-005 — How should the vehicle replacement reserve be set?

**Why it matters:** The $1,600 path (10k-2k)/5 is normative, not measured.

- Option A: Acquisition minus salvage over usable years, all assumptions listed.
- Option B: BLS CE vehicle-purchase P25 among single-person units annualized.
- Option C: No reserve until owner approves a formula.

**Recommended:** A as ESTIMATED_OWNER_REVIEW; do not publish $1,600 as measured.
**Directional effect:** Shorter life or higher acquisition raises annual reserve.
**Source support:** None measured. Retired prototype used 10k/5yr/2k salvage.
**Sensitivity:** Acquisition 8k/10k/12k; life 5/7/10 years.

## OD-006 — Which NAIC insurance measure should represent required auto insurance?

**Why it matters:** Insurance is mandatory where auto is the baseline. NAIC now publishes the 2022/2023 Auto Insurance Database Report as a free download; this is no longer a licensed-only source-existence question.

- Option A: Average expenditure per insured vehicle (what insured households actually spent, mixing coverage take-up).
- Option B: Combined average premium (liability + comprehensive + collision premiums per insured vehicle / car-year).
- Option C: Coverage-specific / mandatory-coverage measure (liability-only or state compulsory package) if the report tables permit.

**Recommended:** Do not freeze. Prefer the measure that most closely matches a legally required package for a single adult; document that free download is not a redistribution license.
**Directional effect:** Combined premium is typically above liability-only; expenditure mixes optional coverages.
**Source support:** Official free PDF: https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf (Adopted December 2025; data through 2023; released Feb 13, 2026). Derived statistics with attribution are handled separately from raw-artifact redistribution. redistribution_status = FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED.
**Sensitivity:** Publish A/B/C side-by-side for every state once tables are extracted; do not invent a CSV.

## OD-007 — Which long-run annualization of vehicle maintenance/repairs/tires should be the reserve?

**Why it matters:** Maintenance and repairs are lumpy. Zero spending in a survey period does not necessarily mean zero long-run maintenance need. Do not automatically use P25 among positive spenders.

- Option A: Weighted mean among single-person vehicle-owning consumer units, including zero-spend periods.
- Option B: Weighted median among the same units, including zero-spend periods.
- Option C: P25/P50 among positive spenders, and/or a multi-year annualized result if sufficient CE vintages can be reproduced. Split routine maintenance, tires, and repairs where FMLI/UCC codes support it.

**Recommended:** Do not freeze one until owner review. Emit all candidates.
**Directional effect:** Including zeros lowers the reserve vs positive-spender P25/mean; multi-year annualization smooths lumps.
**Source support:** BLS CE 2024 Interview PUMD (intrvw24.zip) FMLI vehicle-owning single-person units. Candidate statistics are computed; no $1,200 constant is used.
**Sensitivity:** Compare mean-with-zeros, median-with-zeros, positive-spender P25/P50, and split maintenance/tires/repairs.

## OD-008 — Which recreation percentile is the headline Social & Recreation amount?

**Why it matters:** Recreation must stay nonzero and modest.

- Option A: Weighted P25 among single-person positive spenders.
- Option B: P20.
- Option C: P30.

**Recommended:** A; publish P20/P25/P30 for review and do not freeze one.
**Directional effect:** Higher percentile raises Social & Recreation.
**Source support:** BLS CE Interview PUMD documented UCC/FMLI allowlist.
**Sensitivity:** P20/P25/P30 once CE is retrieved.

## OD-009 — What official PRICE sources should set the one-mobile-line + one-broadband connectivity standard?

**Why it matters:** Zero internet is not a sustainable adult life. ACS internet tables measure subscription/access/type — they are NOT a price source and are removed as a candidate PRICE series (they may remain supporting evidence for prevalence).

- Option A: One modest mobile line + one modest residential broadband connection, priced from official FCC Urban Rate Survey broadband results plus a reproducible authoritative mobile-price source.
- Option B: Mobile-only at the official mobile-price source.
- Option C: Broadband-only at the FCC Urban Rate Survey benchmark / surveyed urban rate.

**Recommended:** A as the Foundation minimum-service selection. Prices must come from real source evidence. ACS is not used for price.
**Directional effect:** Adding both line and broadband raises connectivity vs either alone.
**Source support:** Broadband: official FCC Urban Rate Survey (2024 and 2026 Excel results at fcc.gov/sites/default/files/). Mobile: no single official national prepaid price series is frozen; remaining SOURCE_GAP / ESTIMATED_OWNER_REVIEW until an authoritative reproducible mobile source is accepted. Broadband Consumer Label data are evaluated if published at sufficient geographic scale.
**Sensitivity:** Mobile-only vs broadband-only vs both; URS average vs reasonable-comparability benchmark.

## OD-010 — How should lagging sources be translated into the project cost year?

**Why it matters:** Relabeling 2024 observations as 2026 is forbidden. A single blanket LATEST_AVAILABLE rule is too coarse.

- Option A: HYBRID (recommended): QUANTITIES / STRUCTURAL CHARACTERISTICS use LATEST_AVAILABLE when appropriate (NHTS mileage, reference-population structure, RPP if the latest geography measure is older and clearly labeled). TARGET-YEAR LEGAL RULES use RULE_YEAR (federal tax, state tax, registration laws/fees). CURRENT MONTHLY PRICES use YTD or a defined annual average (USDA 2026 food; gasoline where applicable). LAGGED NOMINAL DOLLAR EXPENDITURE SERIES (2024 CE essentials/recreation used for 2026; older insurance dollars; older OOP amounts) evaluate CPI_UPDATED or a component-specific official price index rather than carrying old nominal dollars forward by default. Every component records project_cost_year, source_data_year, translation_method, and price_index_series if applicable.
- Option B: Unadjusted LATEST_AVAILABLE sensitivity for every lagged series.
- Option C: Refuse 2026 costs until every source has a 2026 observation.

**Recommended:** A (HYBRID). Keep B as a published sensitivity. Do not silently carry old nominal dollars forward.
**Directional effect:** CPI-updating lagged dollar series typically raises 2026 vs holding latest available nominal dollars.
**Source support:** GROK.MD post-2A §7 component-type translation rules.
**Sensitivity:** Show 2026 under HYBRID vs unadjusted LATEST_AVAILABLE for every lagged dollar series.

## OD-011 — How should municipal earned-income taxes be overlaid onto county geography?

**Why it matters:** NYC and Philadelphia are not statewide. Do NOT apply a municipal tax to an entire county merely because the taxing city is inside that county.

- Option A: Direct overlay only when geography is coterminous / the tax applies throughout the modeled county-equivalent, OR the tax is county-level.
- Option B: When the municipality occupies only part of the county: move the tax calculation to place/subcounty geography, population-weight municipal exposure, or mark local tax unresolved. Do not apply a city tax countywide without geographic justification.
- Option C: Invent a statewide average local tax.

**Recommended:** Classify every local tax as A (coterminous), B (county-level), C (partial municipality), or D (unresolved). Direct overlay only for A/B. Never C-as-statewide.
**Directional effect:** A/B raise living cost only where the tax actually applies; C without justification would overstate countywide cost.
**Source support:** GROK.MD post-2A §8 municipal-tax classification A/B/C/D.
**Sensitivity:** Compare county results with coterminous overlay vs place-level vs unresolved.

## OD-012 — Is an additional resilience reserve required after vehicle/health/clothing replacement is already annualized?

**Why it matters:** An extra 5%/10%/$1,200 buffer double-counts if replacement is already inside components.

- Option A: No extra reserve until a documented uncovered irregular cost is identified.
- Option B: Add a small ESTIMATED reserve after an overlap audit.
- Option C: Add 5% of net needs.

**Recommended:** A.
**Directional effect:** Any extra reserve raises gross required income.
**Source support:** GROK.MD resilience section; retired buffers are not authorized.
**Sensitivity:** None until owner requests one.

## OD-013 — How should Connecticut planning-region ACS weights join HUD legacy-county FMR?

**Why it matters:** There are nine current Connecticut county equivalents: 09110, 09120, 09130, 09140, 09150, 09160, 09170, 09180, 09190. HUD FMR still publishes eight legacy county FIPS. Do not invent planning-region rents. Do not default to allocating legacy HUD county rents into planning regions.

- Option A: KEEP HUD COST GEOGRAPHY = legacy HUD county. Reconstruct adult population weights for the eight legacy Connecticut counties by (1) retrieving 2024 ACS B01001 age data at county-subdivision / municipality geography, (2) using the official Census Connecticut County to County Subdivision Crosswalk and/or official Connecticut municipality mapping, (3) assigning towns to legacy counties, (4) summing age-18+ population into the eight legacy counties, (5) joining those reconstructed weights to HUD's legacy-county FMR rows. Validate: all CT population represented; no duplicate municipality; no missing town; eight legacy county totals; state adult-pop total reconciles to the Connecticut total.
- Option B: Leave CT unmatched rather than fabricate allocation if official sources cannot reproduce the reconstruction.
- Option C: Assign a statewide CT 1BR FMR or invent planning-region rents.

**Recommended:** A if the official Census crosswalk plus ACS county-subdivision B01001 can be reproduced; otherwise B. Never C.
**Directional effect:** A keeps CT housing in the join on HUD's published geography. B excludes ~1.1% of national adult population.
**Source support:** Official Census Connecticut County to County Subdivision Crosswalk at https://www2.census.gov/geo/docs/reference/ct_change/ct_cou_to_cousub_crosswalk.xlsx (and .txt). Planning-region FIPS are 09110–09190 (nine geographies), not 09110–09170.
**Sensitivity:** Reconcile reconstructed legacy-county adult pop to ACS Connecticut state total; leave unmatched if reconciliation fails.
