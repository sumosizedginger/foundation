# Living-cost owner decisions FROZEN

Effective date: 2026-08-15

Status: **ACCEPTED / FROZEN** for OD-001 through OD-013.

No Minimum Sustainable Living Cost headline was calculated or published.

`living_cost_release_authorized = false`. `states_modeled = 0`.

**METHODOLOGY FROZEN is not SOURCE VALIDATED.** Evidence gaps remain.

## Global rules

1. Freshest authoritative data actually available at pipeline run time.
2. Minimum sustainable ≠ extreme deprivation.
3. Social/recreation floor $100/month canonical; $200/month preferred modest life.
4. No generic savings / emergency / miscellaneous resilience reserve.

## Recreation standards

- MINIMUM SUSTAINABLE: at least $1,200/year ($100/month).
- PREFERRED MODEST LIFE: at least $2,400/year ($200/month).

Canonical MSLC uses the $100 floor. The $200 version is a named sensitivity.

## Additional freezes

- Food: USDA Low-Cost canonical; Thrifty is lower sensitivity; YTD if year incomplete.
- Health premium: age 40, single, nonsmoker, no dependents, unsubsidized Silver.
- Housing: independent 1-bedroom HUD FMR; no roommate; no utility double-count.

## Freshness gate

Before any future candidate MSLC calculation, re-check MEPS Full Year Consolidated, USDA current-year months, CMS Marketplace/SBE, EIA gasoline, and current tax-law sources. Do not recalculate historical 2024 costs with 2026 price observations.

## OD-001 — ACS geographic population weights

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Use the newest authoritative ACS 5-Year county/county-equivalent adult 18+ vintage actually available and appropriate at calculation time. Do not permanently freeze an obsolete ACS vintage. Historical 2024 costs use 2024 ACS 5-Year weights and must not be rewritten with later population vintages. Current/2026 costs use the newest available ACS 5-Year county vintage (today: 2024). Retain a fixed-2024-weight sensitivity for longitudinal comparison.
**Owner rationale:** Freshest appropriate weights answer the current question. A fixed-2024 sensitivity answers how costs changed holding geographic mix constant.
**Implementation rule:** select_acs_weight_vintage(cost_year, available, mode=canonical|fixed_2024_sensitivity)
**Source-selection rule:** Newest ACS 5-Year county adult-population vintage that exists at run time; historical 2024 locked to 2024 ACS 5-Year.
**Required sensitivity:** ['fixed_2024_weight']
**Known evidence gaps:** []
**Numeric value currently available:** True
**Evidence status:** VALIDATED

## OD-002 — MEPS out-of-pocket healthcare

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Canonical statistic is the weighted mean annual OOP among adults 18–64 who are privately insured in the independent-adult reference population. Required sensitivities: weighted median and weighted P75. Use the newest Full Year Consolidated MEPS file actually released when the candidate calculation runs. At freeze time that file is HC-251 / 2023.
**Owner rationale:** Medical spending is skewed and episodic. A median underfunds expected long-run healthcare. The budget should represent expected annual burden.
**Implementation rule:** canonical=weighted_mean; sensitivities=weighted_median,weighted_p75
**Source-selection rule:** If 2024 Full Year Consolidated is listed on the official MEPS PUF page, retrieve/hash/validate/use it. Otherwise HC-251 with true source year 2023.
**Required sensitivity:** ['weighted_median', 'weighted_p75']
**Known evidence gaps:** ['2024 Full Year Consolidated not listed as of owner freeze; scheduled August 2026']
**Numeric value currently available:** False
**Evidence status:** RETRIEVED_UNVALIDATED

## OD-003 — Necessary annual vehicle mileage

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Canonical mobility requirement is the NHTS weighted median observed annual mileage for one-person, one-worker, age 18–64 licensed-driver households with valid annual vehicle mileage. Label: FOUNDATION MOBILITY STANDARD derived from observed NHTS median. Do not use the mean (~19,000) as minimum necessary. Do not use P25 as canonical.
**Owner rationale:** The mean is pulled by high-mileage households. P25 risks unusually constrained mobility. The median is the modest observed standard.
**Implementation rule:** canonical=weighted_median; sensitivities=P25,mean,P75
**Source-selection rule:** Latest available NHTS microdata (structural quantity; do not inflate miles).
**Required sensitivity:** ['weighted_p25', 'weighted_mean', 'weighted_p75']
**Known evidence gaps:** []
**Numeric value currently available:** True
**Evidence status:** MEASURED

## OD-004 — Reference vehicle / MPG

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Used-car cohort: gasoline non-BEV/non-PHEV compact + midsize passenger cars, model years approximately 8–12 years before the project cost year. Canonical MPG is the cohort median estimated real-world combined MPG. Do not freeze 24 / 28 / 32.
**Owner rationale:** A modest reliable used car, not a new car, luxury car, cherry-picked efficient model, or $1,500 beater.
**Implementation rule:** canonical cohort=used_compact_midsize_gasoline; statistic=median_mpg; window=cost_year-12 .. cost_year-8
**Source-selection rule:** Newest final authoritative EPA/DOE fueleconomy.gov vehicle file when extracting those historical model-year cohorts.
**Required sensitivity:** ['compact_only', 'midsize_only', 'median', 'weighted_mean']
**Known evidence gaps:** ['Production/sales weights not always available on the vehicle file']
**Numeric value currently available:** True
**Evidence status:** MODELED_FROM_MEASURED_INPUTS

## OD-005 — Vehicle replacement reserve

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** ANNUAL REPLACEMENT RESERVE = (reference used-car acquisition cost - expected residual/salvage value) / expected remaining usable years. Formula is frozen. Numeric constants are not. Retired $10,000 / $2,000 / 5 years / $1,600 must not be defaults.
**Owner rationale:** Pretending the existing vehicle lasts forever understates sustainable transportation. The model is explicit and is not MEASURED.
**Implementation rule:** vehicle_replacement_reserve(acquisition, residual, years)
**Source-selection rule:** Newest reproducible authoritative/defensible used-vehicle price source; defensible vehicle-age/survival evidence; documented residual.
**Required sensitivity:** ['acquisition_price', 'usable_years', 'residual_value']
**Known evidence gaps:** ['Authoritative used-vehicle acquisition price not yet bound', 'Usable remaining life evidence not yet bound', 'Residual/salvage value not yet bound']
**Numeric value currently available:** False
**Evidence status:** FORMULA_FROZEN_INPUTS_PENDING

## OD-006 — Automobile insurance

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Canonical insurance cost is the NAIC combined average premium where the relevant state statistic is available. Sensitivities: average expenditure and mandatory/liability-only where reproducible. Newest NAIC Auto Insurance Database as of freeze: 2022/2023 report, data through 2023. Translate later project years with OD-010 motor-vehicle-insurance CPI. Do not label 2023 NAIC dollars as 2026 dollars.
**Owner rationale:** Ordinary insurance capable of protecting a modest reliable vehicle, not merely the cheapest statutory liability-only policy.
**Implementation rule:** canonical=combined_average_premium
**Source-selection rule:** Newest NAIC Auto Insurance Database Report actually available.
**Required sensitivity:** ['average_expenditure', 'mandatory_liability_only_where_reproducible']
**Known evidence gaps:** ['State table extraction from the PDF is not yet a validated numeric series', 'redistribution_status=FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED']
**Numeric value currently available:** False
**Evidence status:** RETRIEVED_UNVALIDATED

## OD-007 — Maintenance / repairs / tires

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Canonical annual reserve is the weighted mean including zero-spend periods among single-person vehicle-owning consumer units using the documented BLS CE VQB/MTBI architecture. Prefer a multi-year pooled/averaged estimate if multiple reproducible recent CE vintages later become available. Do not wait indefinitely before a first candidate.
**Owner rationale:** Maintenance is lumpy. Positive-spender-only overstates frequency. Median including zeros can underfund expected cost.
**Implementation rule:** canonical=weighted_mean_including_zeros
**Source-selection rule:** Official Interview VQB (VQBCODE/VQBEXPX) joined to FMLI single-person vehicle-owning CUs; official MTBI VQBEXPX→UCC map. UCC 470212 excluded.
**Required sensitivity:** ['median_including_zeros', 'positive_spender_p25', 'positive_spender_p50', 'positive_spender_mean']
**Known evidence gaps:** ['Official BLS CE re-retrieve remains HTTP 403; cache INCOMPLETE_PROVENANCE']
**Numeric value currently available:** True
**Evidence status:** INCOMPLETE_PROVENANCE

## OD-008 — Social & recreation

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Empirical baseline is BLS CE weighted P25 among single-person positive spenders on the approved recreation/social allowlist. Canonical MSLC = MAX(empirical P25, $1,200/year). Preferred modest-life sensitivity = MAX(empirical P25, $2,400/year). Retain empirical P20/P25/P30. The $200/month case is PREFERRED MODEST-LIFE SOCIAL/RECREATION STANDARD, not a luxury case. Floors are consumption/social-participation standards, not emergency savings.
**Owner rationale:** Minimum sustainable life includes modest ordinary human/social participation. Empirical recreation must not fall below $100/month.
**Implementation rule:** canonical=max(ce_p25, 1200); preferred=max(ce_p25, 2400); transparency=P20,P25,P30
**Source-selection rule:** BLS CE Interview recreation/social allowlist; OD-010 if translating.
**Required sensitivity:** ['preferred_modest_life_2400', 'empirical_p20', 'empirical_p25', 'empirical_p30']
**Known evidence gaps:** ['Official BLS CE re-retrieve remains HTTP 403; empirical P25 may be unavailable']
**Numeric value currently available:** True
**Evidence status:** INCOMPLETE_PROVENANCE

## OD-009 — Connectivity

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Canonical minimum includes BOTH one mobile phone/data line AND one residential broadband connection. Mobile-only and broadband-only are sensitivities. Broadband target is the current ordinary FCC fixed-broadband benchmark (working standard 100/20 Mbps). Mobile is one ordinary low-cost unlimited or high-data smartphone line. ACS is not a price source. Do not invent a mobile price if no acceptable authoritative source exists.
**Owner rationale:** Normal functional modern participation, not the cheapest technically connected state and not a premium gigabit tier.
**Implementation rule:** canonical=mobile+broadband; broadband=100/20; mobile=ordinary_unlimited
**Source-selection rule:** Newest authoritative FCC evidence for broadband. Newest authoritative/reproducible mobile PRICE source; else SOURCE_GAP.
**Required sensitivity:** ['mobile_only', 'broadband_only']
**Known evidence gaps:** ['FCC Urban Rate Survey retrieve has been HTTP 403', 'No accepted authoritative mobile PRICE source (SOURCE_GAP)']
**Numeric value currently available:** False
**Evidence status:** SOURCE_GAP

## OD-010 — Source lag / current-dollar translation

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Hybrid component-specific system: structural quantities LATEST_AVAILABLE (do not inflate physical quantities); target-year laws RULE_YEAR; current high-frequency prices use actual target-year observations or YTD; lagged nominal dollar expenditure series CPI_UPDATED with the most component-specific authoritative price index; already-local current prices get no generic CPI on top. Every component stores project_cost_year, source_data_year, translation_method, price_index_series, translation_factor, original_value, translated_value. Never silently relabel old dollars. Lagged nominal dollars cannot use silent LATEST_AVAILABLE carry-forward.
**Owner rationale:** A single blanket LATEST_AVAILABLE rule is too coarse and silently relabels old dollars as current.
**Implementation rule:** translation_method_for_component + translate_lagged_nominal_dollars
**Source-selection rule:** Component-specific official CPI or better index: medical-care for MEPS; motor vehicle insurance for NAIC; motor vehicle maintenance/repair for CE maintenance; recreation CPI where defensible else CPI-U with disclosure.
**Required sensitivity:** ['unadjusted_LATEST_AVAILABLE_for_lagged_series']
**Known evidence gaps:** ['Component-specific index series not yet bound into a live translation table']
**Numeric value currently available:** True
**Evidence status:** RULE_FROZEN

## OD-011 — Municipal / local earned-income tax geography/overlay

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** Never apply a municipal tax to an entire county merely because one city inside the county levies it. Classify A coterminous municipality/county-equivalent; B true county-level tax; C municipality covering only part of modeled county; D unresolved. Apply A and B directly. For C, preferred method is place/subcounty calculation; else a transparent population-weighted municipal exposure only if legally and statistically defensible; else SOURCE_GAP/UNAVAILABLE. Do not silently ignore. Do not apply countywide. Do not construct statewide average local tax rates.
**Owner rationale:** NYC boroughs and Philadelphia are coterminous county-equivalents; a partial city inside a larger county is not.
**Implementation rule:** classify_municipal_tax_geography + local_tax_application_rule
**Source-selection rule:** Statutory geography first. Place/subcounty ACS population only if a reproducible join exists.
**Required sensitivity:** ['coterminous_overlay', 'place_level', 'unresolved_source_gap']
**Known evidence gaps:** ['Place-level calculation is not yet generally supported', 'Many local earned-income taxes remain SOURCE_GAP / unresolved']
**Numeric value currently available:** False
**Evidence status:** SOURCE_GAP

## OD-012 — Additional resilience reserve

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** No additional generic resilience reserve. Canonical extra reserve is $0. Do not add 5%, 10%, $1,200, $50/month, $100/month, or emergency savings. Annualize predictable irregular costs inside their actual component.
**Owner rationale:** The Bottom 30% benchmark is not a personal-finance-plan model. Generic savings double-count costs already annualized in components.
**Implementation rule:** canonical_resilience_reserve() == 0
**Source-selection rule:** None. Future uncovered necessities are researched and added to the real category.
**Required sensitivity:** []
**Known evidence gaps:** []
**Numeric value currently available:** True
**Evidence status:** RULE_FROZEN

## OD-013 — Connecticut HUD/ACS geography treatment

**Status:** ACCEPTED / FROZEN
**Effective date:** 2026-08-15
**Decision:** FY2024: keep HUD cost geography = legacy county; reconstruct ACS adult population from official town/county-subdivision data using the official Census Connecticut crosswalk; aggregate into the eight legacy counties; join to HUD FY2024 legacy-county FMR. Do not invent planning-region rents. FY2026: HUD publishes planning-region FIPS; join directly to current ACS Connecticut planning-region geography. Preserve raw Census geography count, Foundation join geography count, transformation metadata, source hashes, and population reconciliation.
**Owner rationale:** HUD and Census published different Connecticut geographies in FY2024. The validated reconstruction already exists and must stay year-specific.
**Implementation rule:** 2024=legacy_county_reconstructed_from_cousub; 2026=direct_planning_region_join
**Source-selection rule:** Official Census CT county-to-county-subdivision crosswalk; ACS B01001 cousub adults; HUD FMR vintage geography as published.
**Required sensitivity:** ['reconcile_reconstructed_2024_legacy_county_adult_pop_to_ACS_CT_total']
**Known evidence gaps:** []
**Numeric value currently available:** True
**Evidence status:** VALIDATED
