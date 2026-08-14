THE FOUNDATION — DELIVERABLE 2A
MINIMUM SUSTAINABLE LIVING COST
SOURCE CLOSURE + METHODOLOGY FREEZE

Repository:
https://github.com/sumosizedginger/foundation

CURRENT APPROVED BASELINE COMMIT:

98bdb23ead17512db8594e7ff385457d51428155

CURRENT STATE:

- Tests & Code Quality: GREEN
- Validate Living Cost Sources: GREEN
- Deploy Pages: GREEN
- 63 tests passed, 1 skipped
- Minimum Sustainable Living Cost remains unpublished
- states_modeled = 0
- Data Health = PARTIAL
- current source coverage report contains 38 blocking component/year combinations
- no Minimum Sustainable Living Cost headline is authorized yet

This is no longer a general integrity-repair pass.

The purpose of this deliverable is:

1. close as many real empirical source gaps as possible;
2. validate already-retrieved source artifacts;
3. identify the genuinely unavoidable remaining modeling assumptions;
4. freeze those methodology choices explicitly;
5. produce a complete OWNER DECISION PACKET;
6. STOP before calculating a national/state Minimum Sustainable Living Cost.

DO NOT CALCULATE OR PUBLISH A LIVING-COST HEADLINE DURING THIS DELIVERABLE.

==================================================
1. PRESERVE CURRENT SUCCESSFUL ARCHITECTURE
==================================================

Do not regress:

- verified $21,800 Population Anchor;
- fail-closed source architecture;
- source manifest;
- source coverage report;
- no test fixtures in production;
- no fabricated provenance;
- Data Health = PARTIAL while Axis 2 is unavailable;
- living-cost release lock;
- working CI;
- working Pages deployment;
- working source-validation workflow.

Do not resurrect retired:

$27,960
$51,220.16
$55,551.89
-$29,420.16
43%

except in explicitly historical documentation.

==================================================
2. GOAL FOR THIS PASS
==================================================

Move each required source/component toward one of:

VALIDATED
MODELED_FROM_MEASURED_INPUTS
ESTIMATED — OWNER REVIEW REQUIRED
UNAVAILABLE
SOURCE_GAP
LICENSING_REVIEW

Do not use:

"parser ready"

as the final state when a public official source is realistically obtainable.

==================================================
3. CENSUS ACS — CLOSE THIS GAP
==================================================

Current source report says Census requires an API key.

Implement secure support for:

CENSUS_API_KEY

Requirements:

- never commit the key;
- read from environment;
- support GitHub Actions secret;
- document local setup;
- fail closed when missing.

Use the official Census ACS 5-Year API.

For population weighting, propose and implement this methodology unless evidence shows a better approach:

Use one frozen ACS adult-population weighting vintage for BOTH the 2024 and 2026 cost distributions so changes in the cost vintages are not confounded by changing aggregation weights.

Preferred current candidate:

2024 ACS 5-Year adult population age 18+.

Clearly distinguish:

COST REFERENCE YEAR
from
POPULATION WEIGHT VINTAGE.

Calculate adult population deterministically from the approved B01001 age cells.

Generate the full 50-state + DC county/county-equivalent universe.

Generate:

data/metadata/census_county_universe.json

Include:

- ACS vintage;
- exact query;
- variables;
- county count;
- count by state;
- represented adult population;
- excluded territories;
- response hash;
- retrieval timestamp.

==================================================
4. HUD HOUSING — CLOSE THIS GAP
==================================================

The official HUD county XLSX artifacts exist.

The current CI downloader returned an empty body.

Fix acquisition rather than marking the dataset nonexistent.

For FY2024 use the appropriate official revised FY2024 County Level Data artifact.

For FY2026 use the current official revised County Level Data artifact, presently the revision effective May 21, 2026.

Acquisition may use:

- robust direct download;
- HUD API;
- official-link discovery from HUD landing page;

whichever proves most reproducible.

If the HUD API requires a token, support an environment secret rather than hardcoding it.

Validation requires:

- actual nonempty XLSX bytes;
- valid Excel workbook;
- correct HUD schema;
- 1BR FMR field;
- county/FMR area identifiers;
- SHA-256;
- byte size;
- retrieval timestamp;
- official effective date.

Then generate REAL:

living_cost_geo_join_2024.json
living_cost_geo_join_2026.json

using Census county weights.

Report all unmatched counties.

==================================================
5. HOUSING METHODOLOGY FREEZE
==================================================

Freeze:

Independent standard-quality 1-bedroom rental.

No roommates.

No room rental.

No homeownership assumption.

Use HUD 1-bedroom FMR.

HUD FMR is gross rent.

Do not separately add utilities already contained in HUD gross rent.

Internet/mobile remain separate.

==================================================
6. USDA FOOD — CLOSE THIS GAP
==================================================

Do not fabricate merged CSV files.

Discover and retrieve the actual official USDA Monthly Cost of Food reports / Excel archives.

For 2024:

use all 12 available months and calculate an annual average.

For 2026:

use all months actually available at execution time.

If fewer than 12 months:

label result:

2026 YTD FOOD COST

not annual average.

Primary:

USDA Low-Cost Food Plan.

Sensitivity:

USDA Thrifty Food Plan.

Profile:

male/female adult age-group midpoint
× official one-person household adjustment.

Document exact age group used.

Raw USDA observations:
MEASURED.

Foundation midpoint + household adjustment:
MODELED_FROM_MEASURED_INPUTS.

For Alaska and Hawaii:

use actual official USDA Alaska/Hawaii observations/methodology where applicable.

No hand-entered AK/HI multiplier.

==================================================
7. CMS HEALTH PREMIUM — VALIDATE RETRIEVED DATA
==================================================

2024 and 2026 CMS federal-platform PUF artifacts have already been retrieved.

Do not redownload merely for appearance.

Validate:

- hashes;
- archive integrity;
- schemas;
- documented CMS keys.

Implement real joins among:

Rate PUF
Plan Attributes PUF
Service Area PUF
Benefits and Cost Sharing PUF

as required.

Reference profile:

- age 40;
- single;
- nonsmoker;
- no dependents;
- individual market;
- ACA-compliant major medical;
- Silver;
- unsubsidized.

Selection:

lowest qualifying unsubsidized premium within the real service geography.

Do not default missing fields.

==================================================
8. CMS STATE-BASED EXCHANGES
==================================================

Implement separate SBE ingestion using the official CMS SBE QHP PUF datasets.

Marketplace platform/source mapping must be year-specific.

Do not infer 2024 mapping from 2026 or vice versa.

Generate a CMS coverage report showing:

- federal-platform states complete;
- SBE states complete;
- missing states;
- rating areas represented;
- counties represented.

No state may receive a premium from a plan not actually offered there.

==================================================
9. HEALTHCARE OOP — UPGRADE MEPS SOURCE
==================================================

The repository currently has MEPS HC-243 / 2022 data retrieved.

Do not automatically accept 2022 as the best available source.

Discover the newest currently available Full Year Consolidated MEPS file.

At execution time:

- if 2024 Full Year Consolidated is officially available and stable, use it;
- otherwise use the newest available full-year file and record the true source year.

For the OOP model derive:

adults 18–64
with private insurance
annual individual out-of-pocket medical expenditure.

Use the appropriate MEPS final person survey weight.

Report:

- source PUF;
- source year;
- variables;
- age filter;
- insurance filter;
- OOP variable;
- unweighted sample;
- represented population;
- weighted mean;
- weighted median if useful for validation;
- P75 if useful for sensitivity.

Do not automatically decide whether headline healthcare should use mean, median or another utilization standard.

Put that in OWNER DECISION PACKET.

==================================================
10. BLS CE — CLOSE ACQUISITION GAP
==================================================

Official 2024 Consumer Expenditure Public Use Microdata exists in CSV format.

Current CI received HTTP 403 from the guessed/direct path.

Resolve the official download through the BLS publication/download page.

Do not treat 403 as evidence the source is unavailable.

Validate actual archive bytes and schema.

Do not assume:

reference_year - 2

as source-vintage methodology.

Use actual 2024 CE data for the 2024 empirical basket where possible.

For 2026 current costs:

if 2026 CE does not exist, explicitly define a temporal update method instead of pretending 2024 CE is 2026 data.

==================================================
11. BLS ESSENTIALS BASKET
==================================================

Construct from actual documented CE/UCC variables.

Create explicit allowlist.

Candidate necessities include:

- apparel replacement;
- footwear;
- laundry;
- personal hygiene;
- cleaning supplies;
- ordinary household supplies;
- basic household replacement items.

Exclude:

- housing;
- food;
- healthcare;
- transportation;
- recreation;
- alcohol;
- tobacco;
- luxury goods;
- vacations.

Use one-person consumer units.

Use proper CE survey weights.

Do not default missing weights or household size.

Calculate weighted P25 among appropriate positive-spending units only if methodology and sample quality support it.

Foundation-created P25:
MODELED_FROM_MEASURED_INPUTS.

==================================================
12. SOCIAL & RECREATION
==================================================

Keep this component.

Do NOT set it to zero.

Create documented allowlist for modest:

- entertainment/admissions;
- reading;
- hobbies;
- social participation;
- limited meals away from home if included.

Prevent double-counting with Food.

Calculate a conservative weighted distribution among single-person consumer units.

Primary candidate:

P25 among positive spenders.

But produce sensitivity:

P20
P25
P30

for OWNER REVIEW.

Do not publish one until approved.

==================================================
13. BEA RPP — CLOSE THIS GAP
==================================================

Retrieve actual official BEA 2024 Regional Price Parity data.

Current official release contains 2024 RPP values.

Use actual source year = 2024.

Do not call it 2026 RPP.

For 2026 costs, it may serve as the latest available geographic price-parity source if documented as:

SOURCE VINTAGE 2024
PROJECT COST YEAR 2026.

No missing RPP -> 100 fallback.

Determine whether:

All Items RPP

is appropriate for the specific nationally-derived components being geographically adjusted.

Do NOT apply RPP to HUD housing or other already-local measured values.

==================================================
14. EIA GASOLINE
==================================================

Determine the actual geographic resolution available from EIA for regular retail gasoline prices.

Prefer:

EIA API v2
or official bulk download.

If using API:

support EIA_API_KEY environment secret.

If equivalent bulk data provide the required series, prefer bulk to avoid a required secret.

Do not label PADD/regional prices as state-measured.

If EIA does not provide all-state retail observations:

produce a methodology decision describing options:

A. use real regional/PADD measured price;
B. find another authoritative state-level source;
C. model state adjustment from documented components.

Do not silently choose.

==================================================
15. NHTS MILEAGE
==================================================

Resolve the official 2022 NHTS V2.1 public-use archive from the official download/documentation page.

Validate exact variables and weights.

Do not default missing weight to 1.

Produce measured travel-behavior statistics for the reference population.

Candidate reference population:

one-person household
working-age adult/driver
one vehicle/driver where variables permit.

But distinguish:

OBSERVED ANNUAL MILEAGE

from:

MINIMUM NECESSARY MILEAGE.

If the latter requires normative judgment, create OWNER DECISION.

Provide:

weighted mean;
weighted median;
P25/P75;
sample size;
filter definitions.

==================================================
16. VEHICLE MPG
==================================================

Do not keep 28 MPG simply because it was already in code.

Research a reproducible reference-vehicle methodology using primary public data where feasible.

Possible architecture:

a modest used compact/midsize vehicle standard with EPA combined MPG.

Do not cherry-pick an unusually efficient vehicle.

Return recommended reference methodology and alternatives for OWNER REVIEW.

Do not freeze without evidence.

==================================================
17. AUTO INSURANCE
==================================================

NAIC currently remains LICENSING_REVIEW.

Research whether a defensible public alternative can provide state-level personal-auto insurance costs.

Priority:

1. official public NAIC aggregate data if legally reusable;
2. state insurance regulator public sources;
3. another federal/state authoritative public source.

Do not use random commercial quote websites.

If no scalable authoritative source exists:

leave LICENSING_REVIEW / SOURCE_GAP

and present owner options.

==================================================
18. MAINTENANCE + TIRES
==================================================

Replace the current unsupported $1,200 assumption.

Research reproducible public data.

Consider BLS CE as empirical evidence/validation.

Separate:

ordinary maintenance
tires
repairs

if the data support it.

If a normative reserve is required:

label ESTIMATED.

Present alternatives and sensitivity.

==================================================
19. VEHICLE REPLACEMENT RESERVE
==================================================

Do not automatically use:

$10,000 acquisition
5 years
$2,000 salvage
= $1,600/year.

Research a defensible modest-used-vehicle replacement standard.

Model explicitly:

reference acquisition cost
minus expected terminal/salvage value
divided by usable replacement period.

Every assumption must be visible.

This is likely a normative/model component.

Return for OWNER REVIEW before freezing.

==================================================
20. REGISTRATION + MANDATORY VEHICLE FEES
==================================================

Delete reliance on uncited hand-entered 51-state fee constants.

For all 50 states + DC:

use primary state DMV/DOR/legislative sources.

Freeze a reference vehicle profile so value/weight/age-based fees can be calculated consistently.

Generate source coverage.

If exact county/local vehicle taxes cannot yet be reproduced:

mark separately.

==================================================
21. CONNECTIVITY
==================================================

Create a defensible minimum connectivity component:

- one mobile phone line;
- residential broadband sufficient for ordinary modern participation/work/services.

Research primary/authoritative sources.

Do not assume zero internet.

Do not use premium/high-end plans.

Separate:

measured price observations
from
Foundation minimum-service selection.

Return methodology for OWNER REVIEW.

==================================================
22. FEDERAL TAX
==================================================

Validate existing 2024 and 2026 tax tables against official IRS and SSA sources.

Current known 2026 values already corrected must remain correct.

Generate source provenance for every federal parameter.

Promote to VALIDATED only after deterministic boundary tests pass.

==================================================
23. STATE TAX
==================================================

Create a tax-source coverage matrix for:

50 states + DC
for 2024 and 2026.

For each:

- primary state source;
- brackets;
- rates;
- deductions;
- exemptions;
- ordinary relevant credits;
- unusual mechanics;
- implementation status.

Do not approximate a complex state with a fake flat bracket model.

SOURCE_GAP is acceptable.

==================================================
24. LOCAL TAX
==================================================

Do NOT require perfect municipal tax modeling merely to make progress.

Instead classify counties/localities:

A. no local earned-income tax;
B. county-level tax directly measurable;
C. municipal tax requiring additional geography;
D. unresolved.

Produce OWNER DECISION on how the county-level living-cost model should handle category C.

Do not silently choose.

==================================================
25. TIME UPDATE MODEL FOR 2026
==================================================

Some annual structural datasets will naturally lag 2026.

Create a formal source-lag framework.

Every component must separately record:

project_cost_year
source_data_year
translation_method

Translation methods may include:

NONE — direct same-year observation
LATEST_AVAILABLE — unchanged structural parameter
CPI_UPDATED — measured older price updated with explicit CPI series
RULE_YEAR — legal/tax rules for target year
YTD — current-year partial observations

Never simply relabel an older observation as 2026.

==================================================
26. OWNER DECISION PACKET
==================================================

At the end of this deliverable produce:

data/metadata/living_cost_owner_decisions_pending.json

and a readable Markdown report.

Include ONLY unresolved normative/methodological choices.

For each decision provide:

QUESTION
WHY IT MATTERS
OPTION A
OPTION B
OPTION C if applicable
RECOMMENDED OPTION
EXPECTED DIRECTIONAL EFFECT
SOURCE SUPPORT
SENSITIVITY PLAN

At minimum expect decisions around:

- population-weight vintage;
- healthcare OOP statistic;
- minimum-mileage definition;
- reference vehicle;
- vehicle replacement reserve;
- insurance fallback;
- maintenance standard;
- recreation percentile;
- connectivity standard;
- 2026 lag/update rules;
- local tax handling;
- resilience reserve.

Do NOT silently make these decisions merely to achieve completeness.

==================================================
27. SOURCE COVERAGE TARGET
==================================================

Regenerate:

living_cost_source_manifest.json
living_cost_source_coverage.json
census_county_universe.json
living_cost_geo_join_2024.json
living_cost_geo_join_2026.json
CMS coverage report
tax coverage report
transportation coverage report

The final source coverage must clearly distinguish:

VALIDATED
RETRIEVED_UNVALIDATED
MODELED_FROM_MEASURED_INPUTS
ESTIMATED_OWNER_REVIEW
SOURCE_GAP
LICENSING_REVIEW
UNAVAILABLE.

==================================================
28. CI + WORKFLOW REQUIREMENTS
==================================================

Preserve green:

Tests & Code Quality
Validate Living Cost Sources
Deploy Pages

Continue running real source validation.

A source gap may appear inside a successful audit workflow.

Programming/import/schema invariant failure must fail CI.

Do not weaken tests to keep green.

==================================================
29. SMALL ENGINEERING CLEANUP
==================================================

Current GitHub Actions still emit Node-20 deprecation warnings from older action generations.

Update to current official Node-24-compatible GitHub Actions versions after verifying current official releases.

Also fix the two remaining HTML heading-level warnings.

These are secondary to the empirical work but should leave the repo clean.

==================================================
30. NO ECONOMIC HEADLINE YET
==================================================

Even if every source becomes VALIDATED:

DO NOT calculate/publish:

Minimum Sustainable Living Cost
state rankings
national median
Gap
Adequacy Ratio
Composite Score

This deliverable ends with:

validated sources
+
frozen empirical methodology
+
owner decision packet.

==================================================
31. REQUIRED FINAL REPORT
==================================================

Report:

- exact final commit SHA;
- actual workflow conclusions;
- test count;
- source coverage before vs after;
- number of remaining blockers;
- exact validated source list;
- exact source gaps;
- exact licensing gaps;
- actual Census county count;
- HUD join coverage;
- CMS geography coverage;
- USDA month coverage;
- MEPS source vintage;
- BLS CE source vintage;
- NHTS source/sample;
- BEA RPP source vintage;
- EIA geographic coverage;
- tax coverage;
- transportation gaps;
- owner decisions required.

Explicitly state:

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.

==================================================
FINAL RULE
==================================================

This pass is successful when we know:

WHAT WE MEASURED,
WHAT WE CAN MODEL,
WHAT WE MUST CHOOSE,
AND WHAT WE STILL DO NOT KNOW.

Do not produce a number simply because the code is capable of arithmetic.

Close the evidence chain first.

Then STOP for owner review.