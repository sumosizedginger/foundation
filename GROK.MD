THE FOUNDATION — OWNER DECISION PACKET REFRESH
POST-DELIVERABLE-2A SOURCE CORRECTION

Repository:
https://github.com/sumosizedginger/foundation

CURRENT AUDITED HEAD:
f2c0636690ac2408d0f537c9fd657225c75e63f3

PURPOSE:

Update the Living Cost owner-decision packet and supporting source coverage using
current official source information as of 2026-08-14.

DO NOT calculate or publish a Minimum Sustainable Living Cost.

DO NOT calculate Gap, Adequacy, state rankings, national median or Composite.

This is a SOURCE / METHODOLOGY CORRECTION pass before owner decisions are frozen.

==================================================
1. MEPS — UPDATE OD-002 STATUS
==================================================

HC-251 (2023 Full Year Consolidated) remains the latest actually listed full-year
MEPS file as of 2026-08-14.

However, AHRQ's official 2026 release schedule says the:

2024 Full Year Consolidated Data File

is scheduled for AUGUST 2026.

Update OD-002 to say this explicitly.

Do not claim the 2024 full-year file exists until it actually appears in the official
MEPS PUF listing.

Add a source-refresh check so that immediately before owner freeze / candidate
calculation the pipeline checks whether the 2024 Full Year Consolidated file has
been released.

If released:
retrieve, hash, parse and prefer it.

If not:
continue using HC-251 with true source year = 2023.

==================================================
2. NHTS — FIX SAMPLE DEFINITION
==================================================

Current fhwa_nhts.py documentation claims:

"single-adult working-age drivers (Age 18-64)"
and
"1-driver households"

but implementation currently filters:

HHSIZE == 1
WRKCOUNT == 1

and then sums vehicle ANNMILES.

That does NOT establish:

age 18-64
or
exactly one licensed driver.

Fix one of two ways:

A. Preferred:
join the appropriate NHTS person data and explicitly enforce:
- one-person household;
- age 18-64;
- driver/licensed-driver criterion if supported;
- one worker if that remains part of methodology.

OR

B:
rename the empirical sample everywhere to exactly what it is:

"one-person, one-worker households with valid annual vehicle mileage"

Do not call it working-age drivers unless the age/driver filter is actually executed.

Preserve:

P25
median
mean
P75
sample count

and clearly label all as OBSERVED TRAVEL BEHAVIOR, not MINIMUM NECESSARY MILEAGE.

Update OD-003 accordingly.

==================================================
3. EPA MPG — UPDATE OD-004
==================================================

EPA now publishes downloadable final Model Year 2024 Automotive Trends detailed
fuel-economy data.

Use official EPA data to construct candidate reference-vehicle MPG standards.

Do not simply retain 24 / 28 / 32 as the empirical model.

Research at minimum:

- final MY2024 EPA detailed data;
- passenger-car / compact / midsize distributions;
- non-BEV/non-PHEV gasoline vehicle fuel economy where appropriate;
- implications of using a used-car rather than new-car standard.

OD-004 should become a decision about the REFERENCE VEHICLE COHORT, not about
whether an EPA source exists.

Produce candidate:
- vehicle age/model-year window;
- class;
- fuel type;
- weighted/median combined real-world MPG;
- sensitivity alternatives.

Do not freeze without owner review.

==================================================
4. NAIC — REPLACE OD-006
==================================================

The current premise is obsolete.

NAIC's official publications site currently offers:

2022/2023 Auto Insurance Database Report

as a FREE DOWNLOAD.

NAIC states the report contains 2023 state-by-state:

- average expenditures;
- combined average premiums;
- other automobile insurance statistics.

Retrieve the official report.

Record actual:
- source URL;
- retrieved_at;
- byte size;
- SHA-256;
- publication year;
- data year;
- reuse/redistribution terms.

Do NOT assume raw-report redistribution rights merely because download is free.

Derived statistics with proper attribution may be handled separately from raw artifact
redistribution.

Replace OD-006 with:

"Which NAIC insurance measure should represent required auto insurance?"

Candidate options should include as actually supported by the report:

A. average expenditure per insured vehicle;
B. combined average premium;
C. coverage-specific / mandatory-coverage measure if the data permit.

Explain what each statistic actually represents.

Do not treat insurance as LICENSING_REVIEW merely because the previous agent failed
to discover the free report.

Use a separate redistribution/licensing field if necessary.

==================================================
5. MAINTENANCE — REVISE OD-007
==================================================

Do not automatically use:

P25 among positive spenders

for maintenance/repairs/tires.

Maintenance and repairs are lumpy annual expenditures.

Zero spending in a survey period does not necessarily mean zero long-run maintenance
need.

Calculate candidate statistics among appropriate single-person VEHICLE-OWNING
consumer units:

- weighted mean including zero-spend periods;
- weighted median including zero-spend periods;
- P25/P50 among positive spenders;
- multi-year annualized result if sufficient CE vintages can be reproduced.

Separate where possible:

routine maintenance
tires
repairs.

OD-007 should explicitly ask which long-run annualization approach best represents a
sustainable vehicle-maintenance reserve.

Do not freeze one until owner review.

==================================================
6. CONNECTIVITY — REVISE OD-009
==================================================

ACS internet tables measure:

subscription/access/type.

They are NOT a price source.

Remove ACS as a candidate source for connectivity PRICE.

ACS may remain supporting evidence for prevalence/normality of internet connectivity.

Research real price sources separately for:

A. residential broadband;
B. one mobile phone/data line.

For broadband, evaluate official FCC price/benchmark sources and any reproducible
Broadband Consumer Label data available at sufficient geographic scale.

For mobile, find a reproducible authoritative source.

The Foundation selection remains normative:

one modest mobile line
+
one modest residential broadband connection.

But the prices must come from real source evidence.

Update OD-009.

==================================================
7. REVISE OD-010 — SOURCE LAG
==================================================

Do not use one blanket LATEST_AVAILABLE rule.

Separate component types.

QUANTITIES / STRUCTURAL CHARACTERISTICS:
may use LATEST_AVAILABLE when appropriate.

Examples:
- NHTS mileage behavior;
- reference-population structure;
- RPP if latest geography measure is older and clearly labeled.

TARGET-YEAR LEGAL RULES:
RULE_YEAR.

Examples:
- federal taxes;
- state taxes;
- registration laws/fees.

CURRENT MONTHLY PRICES:
YTD or defined annual average.

Examples:
- USDA 2026 food;
- gasoline where applicable.

LAGGED NOMINAL DOLLAR EXPENDITURE SERIES:
must NOT simply carry old nominal dollars forward by default.

Examples:
- 2024 CE essentials used for 2026;
- 2024 CE recreation used for 2026;
- older insurance dollar observations;
- older OOP expenditure amounts where applicable.

For these, evaluate a suitable:

CPI_UPDATED
or component-specific official price index update.

Record:

project_cost_year
source_data_year
translation_method
price_index_series if applicable.

Update OD-010 to recommend this HYBRID approach.

Keep an unadjusted LATEST_AVAILABLE sensitivity if useful.

==================================================
8. MUNICIPAL TAX — REVISE OD-011
==================================================

Current Option A is too broad.

Do NOT apply a municipal tax to an entire county merely because the taxing city is
inside that county.

Classify:

A. geography is coterminous / tax applies throughout modeled county-equivalent;
B. tax is county-level;
C. municipality occupies only part of county;
D. unresolved.

For A/B:
direct overlay may be appropriate.

For C:
either:
- move tax calculation to place/subcounty geography;
- population-weight municipal exposure;
- or mark local tax unresolved.

Do not apply a city tax countywide without geographic justification.

Update OD-011.

==================================================
9. CONNECTICUT — REPLACE OD-013 METHOD
==================================================

Correct the planning-region FIPS range.

There are nine current Connecticut county equivalents:

09110
09120
09130
09140
09150
09160
09170
09180
09190.

The existing OD-013 text incorrectly says 09110-09170.

Census publishes an official:

Connecticut County to County Subdivision Crosswalk

for the transition from eight legacy counties to nine planning regions.

Do NOT default to allocating legacy HUD county rents into planning regions.

Investigate a cleaner approach:

KEEP HUD COST GEOGRAPHY = legacy HUD county.

Reconstruct adult population weights for the eight legacy Connecticut counties by:

1. retrieving 2024 ACS B01001 age data at county-subdivision / municipality geography;
2. using the official Census Connecticut county-to-county-subdivision crosswalk and/or
   official Connecticut municipality mapping;
3. assigning towns to legacy counties;
4. summing age-18+ population into the eight legacy counties;
5. joining those reconstructed weights to HUD's legacy-county FMR rows.

This avoids inventing planning-region rents.

Validate:
- all Connecticut population represented;
- no duplicate municipality;
- no missing town;
- eight legacy county totals;
- state adult-pop total reconciles to Connecticut total within expected statistical
  treatment.

If this cannot be reproduced from official sources:
leave CT unmatched rather than fabricate allocation.

Rewrite OD-013 around this architecture.

==================================================
10. CMS SBE COVERAGE — CURRENT CLOSEOUT IS WRONG
==================================================

Delete/update claims that:

"SBE 2024 official zip 404"
or
"SBE 2026 zip is documentation-only"

imply that SBE plan data are unavailable.

CMS currently publishes official PER-STATE SBE QHP PUF ZIP files for:

Plan Year 2024
and
Plan Year 2026.

The SBE QHP PUF architecture includes separate:

- Rate;
- Plan Attributes;
- Benefits and Cost Sharing;
- Service Area;
- Business Rules;
- Network

files as applicable.

Implement retrieval per state and per plan year from the official CMS SBE QHP PUF
downloads.

Do not assume one national SBE zip.

Join using the appropriate official keys.

Generate coverage report:

2024:
SBE states expected
SBE states retrieved
SBE states parsed
counties/rating areas covered
missing states

2026:
same.

Be careful with platform classification.

Use year-specific official CMS platform information.

Do not infer that the existence of a state-specific SBE file necessarily means the
same platform classification rules as the federal Exchange PUF.

After successful national coverage, health_premium can move toward validation.

==================================================
11. PROVENANCE — FIX INVALID FULL VALIDATION STATES
==================================================

Current source manifest/coverage contains artifacts marked:

VALIDATED

while:

retrieved_at = null

and in some cases:

local_cache_filename = null
resolved_url = null.

Examples include currently reported HUD, ACS, NHTS, BLS CE, BEA and other cached
artifacts.

This violates the Foundation provenance contract.

A hash + parse success is not complete retrieval provenance.

For every such artifact:

A. re-retrieve from the authoritative official source and generate a real sidecar;
OR
B. if re-retrieval cannot be performed, downgrade from full VALIDATED to an
appropriate incomplete-provenance status.

Prefer re-retrieval.

Required validated provenance:

- official landing/source;
- exact resolved URL;
- actual retrieval timestamp;
- byte size;
- SHA-256;
- immutable cache identity;
- parser/schema validation;
- source/reference year.

Do not invent retrieved_at for old cache hits.

==================================================
12. USDA 2026 — MAKE YTD PERIOD EXPLICIT
==================================================

The current reports show partial 2026 USDA data.

Do not merely say:

2026 YTD FOOD COST.

Emit exact:

months_included
month_count
first_month
last_month.

The current source data appear to cover five 2026 months for Alaska/Hawaii and a
corresponding partial national plan period.

Derive the exact covered months from the actual source observations.

Do not infer them from row counts alone.

==================================================
13. WORKFLOW ACTION VERSIONS
==================================================

Current repo still uses:

actions/checkout@v5
actions/setup-python@v6
actions/setup-node@v5.

Current official documentation now uses:

actions/checkout@v7
actions/setup-python@v7
actions/setup-node@v6.

Upgrade consistently across all workflows after verifying the current official
major releases at implementation time.

Keep Node 24.

Run all workflows afterward.

==================================================
14. CLOSEOUT METADATA
==================================================

The pasted Deliverable 2A closeout SHA:

b2a30ef4b87a2db38eb5f7d982e0e8b5c9b63b4c

is historical.

Current audited main at start of this correction is:

f2c0636690ac2408d0f537c9fd657225c75e63f3

Preserve b2a30ef as a historical Deliverable 2A milestone if desired.

Do NOT label it current HEAD.

Generate final closeout from the final pushed SHA.

==================================================
15. TEST REPORTING
==================================================

Do not report the old local:

73 passed

as current repository CI status.

Current audited GitHub CI before this correction reports:

68 passed
5 skipped
1 warning.

After changes, report the exact GitHub Actions result, not a stale local run.

All three workflows must remain green:

Tests & Code Quality
Validate Living Cost Sources
Deploy Pages

==================================================
16. OWNER DECISIONS THAT DO NOT REQUIRE MATERIAL CHANGE
==================================================

Preserve the core direction of:

OD-001 ACS fixed-weight-vintage concept
OD-005 vehicle replacement formula decision
OD-008 nonzero Social & Recreation percentile decision
OD-012 no arbitrary resilience buffer

unless new empirical evidence during this correction requires an explicit amendment.

==================================================
17. DO NOT FREEZE OWNER DECISIONS YET
==================================================

Regenerate:

living_cost_owner_decisions_pending.md
living_cost_owner_decisions_pending.json

after the above source corrections.

The owner will review the corrected decision packet afterward.

Do NOT silently mark any OD as ACCEPTED.

==================================================
18. STOP CONDITION
==================================================

DO NOT calculate or publish:

Minimum Sustainable Living Cost
2024 MSLC
2026 MSLC
state MSLC rankings
national median
Gap
Adequacy Ratio
Composite Score.

This pass fixes the evidence and decision packet.

When complete:

push;
verify actual GitHub Actions;
report exact final SHA;
report all unresolved owner decisions.

Explicitly state:

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.