THE FOUNDATION — PRE-OWNER-FREEZE CORRECTION PASS
POST e497d45 AUDIT

Repository:
https://github.com/sumosizedginger/foundation

CURRENT AUDITED HEAD:
e497d451088a054d43fda9921aa699531077888a

PURPOSE:

Correct the remaining provenance, CMS platform-classification, CPS source-revision,
and BLS CE maintenance-detail issues discovered in independent post-closeout review.

DO NOT calculate or publish a Minimum Sustainable Living Cost.

DO NOT calculate:
- 2024 MSLC
- 2026 MSLC
- Gap
- Adequacy Ratio
- state rankings
- national median
- Composite

DO NOT mark any owner decision ACCEPTED.

Owner freeze occurs AFTER this correction pass.

==================================================
1. 2024 HUD ↔ ACS JOIN — FIX PROVENANCE
==================================================

Current:

data/metadata/living_cost_geo_join_2024.json

has:

"census_artifact_sha256": ""
"hud_artifact_sha256": ""

This is unacceptable.

The 2026 equivalent correctly carries both hashes.

Fix the 2024 join-generation path so the report receives and records:

- exact ACS source artifact SHA;
- exact HUD FY2024 source artifact SHA;
- actual source IDs;
- source reference periods;
- retrieval timestamps where appropriate.

Add a release-gate test:

A production geo-join report may not claim validated/full coverage if either required
source hash is blank.

==================================================
2. DISTINGUISH RAW CENSUS UNIVERSE FROM TRANSFORMED JOIN UNIVERSE
==================================================

The official 2024 ACS county/county-equivalent universe contains 3,144 geographies.

For the FY2024 HUD join, Connecticut is transformed:

9 ACS planning regions
→
8 reconstructed legacy counties

which produces a 3,143-geography JOIN universe.

Do not call 3,143:

census_county_universe_count

without qualification.

Preserve separately, for example:

raw_census_county_equivalent_count = 3144
join_geography_count = 3143
connecticut_raw_geographies = 9
connecticut_reconstructed_geographies = 8
connecticut_method = legacy_county_reconstructed_from_cousub

The exact schema may differ.

The principle:

Do not mutate history by making it appear that Census published only 3,143 county
equivalents.

The transformed geography is a Foundation join representation.

==================================================
3. CMS — FIX OREGON PLATFORM CLASSIFICATION
==================================================

Current code incorrectly defines Oregon as a standalone SBE for both 2024 and 2026
while also including Oregon in the federal-platform data.

This creates a platform overlap.

Official CMS evidence:

PLAN YEAR 2026:

CMS states there are:

21 SBEs
3 SBE-FPs

and explicitly lists:

Arkansas
Oregon
Oklahoma

as SBE-FPs.

Oregon therefore must NOT be counted as one of the 21 standalone individual-market
SBEs.

PLAN YEAR 2024:

CMS Open Enrollment reporting lists Oregon's individual-market platform as:

HealthCare.gov

not SBM.

Therefore Oregon must not be classified as a standalone individual-market SBE for
2024 either.

==================================================
4. SBE QHP ZIP EXISTENCE IS NOT PLATFORM CLASSIFICATION
==================================================

CMS's SBE QHP PUF page says SBE-FPs use the federal platform and are included in
the federal Exchange PUFs.

CMS also notes SHOP information can appear for SBE-FPs.

Therefore:

DO NOT infer:

"Oregon has an SBE ZIP"
→
"Oregon is standalone SBE individual-market coverage."

The Oregon SBE QHP archive may contain SHOP/SBE-related records while individual
QHP eligibility/enrollment remains federal-platform.

Separate concepts:

marketplace_platform_classification
individual_market_source
SHOP_source
SBE_archive_exists

They are not synonyms.

==================================================
5. CORRECT EXPECTED SBE INDIVIDUAL-MARKET COUNTS
==================================================

Rebuild the year-specific individual-market platform map from authoritative CMS
platform evidence.

Expected architecture should reconcile exactly to 50 states + DC without accidental
double-counting.

For 2024, current evidence implies:

32 HealthCare.gov / federal-platform jurisdictions
19 standalone SBM jurisdictions
= 51

NOT:

32 + 20 with Oregon appearing in both.

For 2026, CMS explicitly reports:

30 states using HealthCare.gov
21 standalone SBEs
= 51

with Oregon among the federal-platform/SBE-FP states, not among the 21 standalone
SBEs.

CMS additionally lists three SBE-FPs for PY2026:

Arkansas
Oregon
Oklahoma

Note that SBE-FP is a governance classification while federal Exchange PUF coverage
is the relevant data-source classification.

Create a machine-readable year-specific platform/source map.

Add tests ensuring:

- every state + DC has one individual-market primary data-source path;
- no jurisdiction is simultaneously treated as standalone-SBE individual market
  AND federal-platform individual market;
- SBE-FP states use federal Exchange PUFs for individual-market plan/rate data
  unless official documentation explicitly requires otherwise.

==================================================
6. DO NOT DISCARD OREGON SBE ARCHIVE BLINDLY
==================================================

Inspect the official Oregon SBE archive.

Determine what market/business records it actually contains.

If it contains SHOP-only or otherwise non-individual-market records:

retain the artifact with accurate provenance and market scope.

Do not feed it into the independent single-adult individual-market Silver-plan
selection.

Record:

market_scope
platform_scope
source_use

==================================================
7. CMS SBE — IMPLEMENT THE ACTUAL LOWEST-SILVER JOIN
==================================================

Current SBE status:

RETRIEVED_UNVALIDATED

because state ZIP parsing currently proves primarily:

archive integrity
+
CSV members exist.

That is not enough.

For each TRUE standalone SBE state/year, implement the real equivalent of the federal
PUF selection using:

- Rate PUF;
- Plan Attributes PUF;
- Service Area PUF;
- Benefits and Cost Sharing PUF;
- Business Rules if needed for valid rate interpretation.

Reference profile remains:

- individual market;
- ACA major medical;
- Silver;
- age 40;
- non-tobacco;
- single;
- no dependents;
- unsubsidized.

Validate actual geography availability.

Do not assume the SBE schemas/keys are identical to federal PUF schemas.

Use the official year-specific SBE data dictionaries.

For every standalone SBE state report:

- rows parsed by source file;
- individual-market rows retained;
- Silver plans retained;
- age-40 rates retained;
- service areas/rating areas represented;
- counties represented;
- final qualifying plan count;
- lowest-Silver output count;
- unmatched join keys;
- duplicate keys.

Only after all applicable states pass may:

health_premium

move from:

RETRIEVED_UNVALIDATED

toward VALIDATED / MODELED_FROM_MEASURED_INPUTS as appropriate.

==================================================
8. CPS 2025 ASEC SHA — RESOLVE, DON'T MERELY DOCUMENT
==================================================

Current repo still has two hashes for:

asecpub25csv.zip

CURRENT/CANONICAL:
318845a2b5e0034eb2973898de1738f4df0025727de38499e7669cb9c0deef0b

LEGACY HISTORICAL ARTIFACT:
318845a2b5e0034e357900b991196ce28ecdd0c99a0937b27ff77f8ea6497284

Current state:

src/foundation/historical.py
contains the canonical/current hash.

data/current/history.json
still contains the legacy hash.

data/current/latest.json
therefore contains both hashes for the same source/vintage.

data/metadata/cps_asec_2025_sha_revisions.json
labels this:

UNRECONCILED_PENDING_RETRIEVAL.

Current release-gate behavior merely permits this contradiction if the revision file
exists.

That is not the final desired state.

Re-retrieve the current official Census archive:

https://www2.census.gov/programs-surveys/cps/datasets/2025/march/asecpub25csv.zip

Record:

- retrieved_at;
- exact byte size;
- SHA-256;
- HTTP metadata.

Compare against both observed hashes.

If it matches the canonical/current hash:

- regenerate history.json with that hash;
- regenerate latest.json;
- keep the other hash only in the audit revision record as a legacy/unverified
  observation unless independent retrieval evidence proves it represented genuine
  Census bytes at an earlier time.

If it matches the legacy hash:

investigate why the current Population Anchor provenance differs.

If it matches neither:

STOP and investigate source revision.

Do not silently select a value.

==================================================
9. STRENGTHEN CPS RELEASE GATE
==================================================

After reconciliation, replace the permissive test:

"if old and new hashes coexist, revision record may explain them"

with canonical consistency requirements.

For the active/canonical source revision:

historical.py
history.json
latest.json history slice
population.json / latest population anchor
validation report

must all identify the SAME canonical artifact hash.

Historical publisher revisions may remain in a separate immutable revision ledger,
but cannot masquerade as the active source artifact.

==================================================
10. BLS CE MAINTENANCE — STOP USING FMLI AS THE SOLE DETAIL SOURCE
==================================================

Current:

parse_bls_ce_maintenance_candidates()

loops FMLI files and searches summary columns such as:

MAINRPCQ
TIRECQ

The current result reports all-zero tires because TIRECQ is absent.

Do NOT interpret this as measured zero tire spending.

Official BLS PUMD documentation distinguishes:

FMLI:
CU-level SUMMARY expenditure variables + household characteristics + weights.

MTBI:
MONTHLY expenditure records keyed by UCC.

BLS also documents detailed vehicle-maintenance/repair files with individual repair
expense records.

For a detailed maintenance/repair/tire basket, use the appropriate detailed/UCC
architecture.

Preferred architecture:

FMLI:
- NEWID;
- FAM_SIZE;
- vehicle ownership;
- FINLWT21;
- other CU characteristics.

MTBI and/or documented detailed vehicle expenditure files:
- NEWID;
- UCC;
- expenditure amount;
- appropriate reference period.

Join detailed expenditure records back to eligible FMLI consumer units.

==================================================
11. BUILD A DOCUMENTED VEHICLE UCC ALLOWLIST
==================================================

Using official BLS:

- Interview/Diary Dictionary;
- hierarchical UCC groupings;
- applicable CE documentation;

build an explicit vehicle-maintenance expenditure allowlist.

Separate where reproducible:

routine service / maintenance
repairs
tires

Potential categories must be derived from official UCC documentation, not guessed
column names.

Exclude:

fuel
insurance
vehicle purchase
finance charges
registration
parking/tolls

because those are separate Foundation components.

Document every included/excluded UCC.

==================================================
12. MAINTENANCE STATISTICS
==================================================

For single-person vehicle-owning consumer units calculate candidates:

- weighted annual mean including zero-spend CUs;
- weighted annual median including zero-spend CUs;
- positive-spender P25;
- positive-spender P50;
- positive-spender mean;
- sample size;
- positive-spender sample size;
- represented weighted population.

Where possible, build multi-year candidates because repair spending is lumpy.

Do not freeze the final owner choice.

OD-007 remains pending.

==================================================
13. BLS CE PROVENANCE
==================================================

Current BLS CE re-retrieval returns HTTP 403 and the existing cache is correctly
labeled:

INCOMPLETE_PROVENANCE.

Do not promote it merely because the parser works.

Investigate the official BLS documented download flow.

If a reproducible official retrieval route succeeds:

re-retrieve
hash
sidecar
validate.

If BLS continues to reject automated retrieval:

keep INCOMPLETE_PROVENANCE

and clearly separate:

content/schema validated from cached official artifact

from:

fully reproducible retrieval provenance.

Do not fabricate retrieval metadata.

==================================================
14. 2024 HUD UNMATCHED ROW CLASSIFICATION
==================================================

Current 2024 and 2026 joins report 85 unmatched HUD rows even while modeled U.S.
coverage is 100%.

Many of these are out-of-scope territories or HUD special/non-county records.

Classify unmatched HUD rows into explicit categories:

- excluded U.S. territories;
- special/non-county HUD geography;
- malformed/unrecognized FIPS;
- actual unmatched 50-state+DC county geography.

Do not let "85 unmatched rows" look like an unexplained county coverage defect when
the project's 50-state+DC universe has 100% matched population.

Preserve exact IDs.

==================================================
15. KEEP CURRENT TRUTHFUL GAPS
==================================================

Do not paper over:

FCC URS 403
mobile price source gap
registration source gap
state/local tax gaps
MEPS pending newer file
vehicle replacement owner decision.

These may remain truthful:

SOURCE_GAP
INCOMPLETE_PROVENANCE
ESTIMATED_OWNER_REVIEW
RETRIEVED_UNVALIDATED.

A truthful gap is acceptable.

==================================================
16. OWNER PACKET
==================================================

Regenerate:

living_cost_owner_decisions_pending.md
living_cost_owner_decisions_pending.json

after these corrections.

Keep:

OD-001 through OD-013

pending.

Do not mark any as ACCEPTED.

Update OD-006 / CMS-related supporting material as necessary to reflect corrected
platform classifications.

Update OD-007 to reference the detailed MTBI/UCC maintenance candidates rather than
an absent FMLI tire summary field.

==================================================
17. VALIDATION
==================================================

Add/strengthen tests for:

- 2024 geo-join hashes nonempty;
- raw ACS universe vs transformed join universe represented separately;
- no duplicate individual-market platform classification;
- Oregon 2024 individual-market source = federal platform / HealthCare.gov PUF;
- Oregon 2026 individual-market source = federal platform / SBE-FP;
- 2026 standalone SBE count = 21;
- all 50 states + DC represented exactly once in individual-market primary source
  coverage;
- SBE archive presence does not automatically imply standalone individual-market
  platform;
- SBE lowest-Silver join executes on real state files;
- canonical CPS same-vintage hash consistency;
- old CPS hash retained only in revision ledger if not current;
- BLS missing TIRECQ does not produce a false measured zero-tire conclusion;
- detailed maintenance UCC basket excludes gas/insurance/purchase/registration.

==================================================
18. CI
==================================================

Preserve:

actions/checkout@v7
actions/setup-python@v7
actions/setup-node@v6
Node 24.

All three workflows must be green:

Tests & Code Quality
Validate Living Cost Sources
Deploy Pages

Report exact GitHub result after push.

==================================================
19. STOP CONDITION
==================================================

DO NOT CALCULATE OR PUBLISH:

Minimum Sustainable Living Cost
Gap
Adequacy Ratio
state living-cost rankings
national living-cost median
Composite.

This is the final evidence-cleanup pass before OWNER DECISION FREEZE.

When complete, report:

- final SHA;
- CI results;
- corrected CMS platform map;
- standalone SBE counts;
- SBE lowest-Silver join coverage;
- CPS canonical SHA reconciliation;
- corrected 2024 geo-join provenance;
- BLS maintenance/UCC candidate results;
- remaining SOURCE_GAP / INCOMPLETE_PROVENANCE items.

Explicitly state:

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.