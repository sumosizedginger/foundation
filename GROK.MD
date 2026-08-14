THE FOUNDATION — FINAL PRE-OWNER-FREEZE CLEANUP

Current audited HEAD:
94362d8bcd7f4e9ef08a44cb436619c9b9647a6c

The substantive pre-owner-freeze correction pass is accepted.

Do NOT recalculate MSLC.

Do NOT alter OD choices.

Do NOT mark any OD ACCEPTED.

Fix only the remaining factual/metadata inconsistencies below, push, and verify CI.

==================================================
1. FIX OKLAHOMA 2024 CMS GOVERNANCE CLASSIFICATION
==================================================

Current:

src/foundation/sources/cms_platform.py

contains:

SBE_FP_STATES[2024] = {"AR", "OK", "OR"}

This is factually wrong for Oklahoma.

Official CMS says Oklahoma's SBE-FP status is effective May 1, 2026.

For Plan Year 2024 Oklahoma used HealthCare.gov and must not be labeled SBE-FP.

Correct 2024 Oklahoma classification to the appropriate federal/HealthCare.gov category.

IMPORTANT:

Its individual-market data source remains:

federal_exchange_puf

so this is a governance/platform metadata correction, not a reason to change its federal PUF premium data.

Audit Arkansas and Oregon 2024 governance labels against actual year-specific CMS evidence as well.

Do not infer SBE-FP governance merely because a state uses HealthCare.gov.

Use exact historical CMS evidence where available.

Add a test proving:

OK 2024 != sbe_fp
OK 2026 == sbe_fp

and preserve:

OK individual_market_source = federal_exchange_puf

for both years as applicable.

Regenerate:

data/metadata/cms_individual_market_platform_map.json
data/metadata/living_cost_cms_coverage.json
data/metadata/living_cost_cms_sbe_lowest_silver.json

if classification metadata are embedded in them.

==================================================
2. REGENERATE SOURCE COVERAGE FROM CURRENT STATE
==================================================

Current:

data/metadata/living_cost_source_coverage.json

has an old generated_at timestamp predating later CMS and BLS corrections.

Regenerate it from current HEAD.

Do not manually preserve a stale generated_at.

Also resolve the maintenance status semantics.

Current maintenance candidate report correctly says:

INCOMPLETE_PROVENANCE

because the cached official BLS CE artifact parses successfully but reproducible official re-retrieval still returns HTTP 403.

The source coverage currently says:

ESTIMATED_OWNER_REVIEW

Those represent two different dimensions.

Prefer separating them, e.g.:

evidence_status = INCOMPLETE_PROVENANCE
methodology_status = OWNER_REVIEW_PENDING

or an equivalent clean schema.

Do NOT imply the empirical maintenance candidate itself is merely a guessed estimate.

Do NOT promote it to VALIDATED while retrieval provenance remains incomplete.

Apply the same principle wherever source evidence state and owner-decision state are currently conflated.

==================================================
3. REMOVE OR CLEARLY ARCHIVE THE STALE DELIVERABLE 2A REPORT
==================================================

Current repo still contains:

data/metadata/living_cost_deliverable_2a_report.md

with obsolete claims including:

- exact SHA b2a30ef...
- checkout@v5 / setup-python@v6 / setup-node@v5
- 73 tests
- Connecticut unmatched
- outdated CMS SBE status
- outdated health_premium state

This file can no longer appear to describe current repository state.

Choose one:

A. Replace it with the current accurate closeout;

or

B. move/rename it into an explicitly historical/superseded location and put a prominent header:

SUPERSEDED HISTORICAL DELIVERABLE 2A SNAPSHOT
NOT CURRENT PROJECT STATUS

Prefer preserving historical auditability rather than deleting history.

Current project-status documentation must point to the new current closeout.

==================================================
4. FIX CLOSEOUT OD LABELS
==================================================

The latest closeout recap contains incorrect shorthand labels for:

OD-011
OD-012

The canonical current owner packet is authoritative.

Correct the closeout recap so it matches:

OD-011 — municipal earned-income tax geography/overlay

OD-012 — additional resilience reserve

OD-013 — Connecticut HUD/ACS geography treatment

Do not change the actual OD definitions.

==================================================
5. CURRENT CI REPORTING
==================================================

After push, report the actual GitHub CI result.

Current pre-fix CI baseline is:

94 passed
5 skipped
1 warning

The prior:

99 passed

was a local run and may remain documented specifically as LOCAL if useful.

Do not present local results as GitHub CI results.

==================================================
6. PRESERVE ALL ACCEPTED WORK
==================================================

Do not regress:

- canonical CPS SHA reconciliation;
- 2024 HUD/ACS source hashes;
- raw ACS 3144 vs transformed join 3143 distinction;
- 100% 50-state+DC 2024 housing population coverage;
- Oregon federal individual-market source;
- 19 standalone SBE individual markets for 2024;
- 21 standalone SBE individual markets for 2026;
- real SBE lowest-Silver joins;
- BLS VQB/MTBI maintenance candidates;
- CE INCOMPLETE_PROVENANCE truthfulness;
- living_cost_release_authorized = false;
- states_modeled = 0;
- all owner decisions pending.

==================================================
7. STOP CONDITION
==================================================

Do NOT calculate or publish:

MSLC
Gap
Adequacy
state rankings
national median
Composite

After this cleanup:

push;
verify Tests & Code Quality;
verify Validate Living Cost Sources;
verify Deploy Pages.

Return final SHA and exact CI result.

Then STOP.

The next task is OWNER FREEZE of OD-001 through OD-013.