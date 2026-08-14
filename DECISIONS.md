# Decision Log

Entries marked ACCEPTED are binding until explicitly superseded.

## D-001 — Bottom-30 denominator

**Date:** 2026-08-13  
**Status:** ACCEPTED

Household money resources are divided by the number of humans supported in the household.
V0.1 operationalizes "supported" as persons in the CPS household.
No equivalence-scale fractional weighting of children/adults.

---

## D-002 — Ranking unit

**Date:** 2026-08-13  
**Status:** ACCEPTED

Rank persons, not households.
Each person receives household money income divided by household person count.
Use official person survey weights.

---

## D-003 — Reference population

**Date:** 2026-08-13  
**Status:** ACCEPTED

The bottom 30% is primarily a reference point for evaluating the economy, not a claim that everyone in the group is identical or permanently poor.

---

## D-004 — Site before show

**Date:** 2026-08-13  
**Status:** ACCEPTED

Current development focus is 100% the site/research instrument.
Daily-show format, production and distribution are deferred.

---

## D-005 — Zero-dollar core

**Date:** 2026-08-13  
**Status:** ACCEPTED

The core system should operate with free/open-source software, public data and free public-project hosting/automation where available.
No paid dependency may become necessary for reproducibility without explicit approval.

---

## D-006 — Agent-operated maintenance

**Date:** 2026-08-13  
**Status:** ACCEPTED

The intended workflow allows an Antigravity agent to research, download, validate, calculate, test, build and update the site when instructed.
The owner should not be required to manually write code.

---

## D-007 — Methodology authority

**Date:** 2026-08-13  
**Status:** ACCEPTED

Agents may implement and maintain methodology.
Agents may not silently change methodology.

---

## D-008 — Fail closed

**Date:** 2026-08-13  
**Status:** ACCEPTED

Broken/uncertain data produce stale/unavailable states, not guessed replacements.

---

## D-009 — Composite score

**Date:** 2026-08-13  
**Status:** ACCEPTED

Do not publish a composite Foundation score merely because one can be calculated.
It requires validation, sensitivity analysis and explicit release authorization.

---

## D-010 — Primary source preference

**Date:** 2026-08-13  
**Status:** ACCEPTED

Use original government/first-party data as production source wherever practical.
Aggregators are discovery/cross-check tools.

---

## D-011 — Second Economic Axis: Survival Floor (SUPERSEDED IN PART)

**Date:** 2026-08-13  
**Status:** SUPERSEDED IN PART BY D-015

Added conceptual Second Economic Axis alongside Population Anchor.
_Note: The numeric $27,960 national baseline, component values, and preliminary modeling assumptions of D-011 are explicitly superseded and retired by D-015. The conceptual dual-axis architecture (Population Anchor vs. Minimum Sustainable Living Cost) is preserved._

---

## D-012 — Open-Source Licensing Structure

**Date:** 2026-08-13  
**Status:** ACCEPTED

Software source code is licensed under Apache License 2.0.
Methodology and original documentation are licensed under Creative Commons Attribution 4.0 (CC BY 4.0).
Derived data use CC BY 4.0 where authorized.
The Foundation brand name, logo, and identity are explicitly reserved and excluded from public copyright grants.

---

## D-013 — Historical Constant-Dollar Translation

**Date:** 2026-08-13  
**Status:** ACCEPTED

Store both nominal dollars and CPI-U adjusted constant 2024 dollars for all historical Population Anchor vintages.
Historical displays default to real constant dollars to prevent nominal inflation from being mistaken for economic improvement.

---

## D-014 — National Economic Pressure Signals

**Date:** 2026-08-13  
**Status:** ACCEPTED

Registered BLS indicators (U-6, Labor Force Participation, Employment-Population Ratio, Want a Job, and CPI sub-indices) must be explicitly labeled as **National Economic Pressure Signals** and not misrepresented as Bottom-30 specific measures.

---

## D-015 — Minimum Sustainable Living Cost Methodology Migration

**Date:** 2026-08-13  
**Status:** ACCEPTED (Owner Authorized)

1. **Retirement of $27,960 Single-Adult Estimate:** The previous $27,960 national research estimate is rejected and retired from public display because its housing, healthcare, transportation, tax, benefit-treatment, and single-national-constant assumptions were insufficiently defensible.
2. **Methodology Version:** Initiates `0.2.0-draft`. The Population Anchor methodology ($21,800 for 2024 income year) remains unchanged.
3. **Canonical Definition:** The Minimum Sustainable Living Cost is the gross money income required for one independent adult to maintain a minimally sustainable life without means-tested public assistance, debt-financing ordinary necessities, financial support from another person, roommates, or shared household income.
4. **Geographic Architecture:** Rejects national constants. Builds from local geography upward (County / HUD FMR area level across all 50 states + DC) using Census ACS adult-population weights to produce weighted P25, median (P50), P75, min, and max for each state and the nation.
5. **Vintage Architecture:** Preserves distinct 2024 Time-Comparable and 2026 Current Living Cost vintages. 2024 Population Anchor is strictly compared only against the 2024 Living Cost vintage.
6. **No-Benefits Baseline:** Excludes SNAP, Medicaid, Medicare, ACA premium tax credits, housing subsidies, LIHEAP, and means-tested refundable credits from the baseline. Standard deductions and statutory tax tables apply normally.
7. **Explicit Components:** Independent 1-bedroom FMR housing (preventing double-counted utilities), USDA Low-Cost Food Plan (with Thrifty sensitivity), explicit automobile cost model (fuel, insurance, maintenance, replacement reserve), unsubsidized adequate Silver Marketplace health insurance plus MEPS expected OOP utilization, connectivity and restricted essential goods, explicit visible Social & Recreation component, and a deterministic gross-income tax solver.

---

## D-016 — Data Integrity Correction & Prototype Headline Retirement

**Date:** 2026-08-13  
**Status:** ACCEPTED (Owner Directive)

1. **Immediate Retirement of Prototype Living-Cost Headlines:** The preliminary outputs produced in commit `fff0cbb` ($51,220.16 2024 national median, $55,551.89 2026 national median, -$29,420.16 survival gap, 43% adequacy ratio, and synthetic state rankings) are rejected and retired. They used provisional state-level assumptions and synthetic locality tiers that did not meet the project's empirical county-level source standard.
2. **Deletion of Synthetic Locality Generation:** Prohibits the use of synthetic locality archetypes (e.g. 45/35/20 population shares, 1.22/0.98/0.78 FMR multipliers, manufactured FIPS codes). Production calculations must parse and join actual empirical county observations.
3. **Mandatory Fail-Closed Provenance Rule:** Components may not be marked `MEASURED` without verified source URLs, reference periods, retrieval timestamps, parsed field names, and artifact SHA-256 hashes. Empty provenance metadata fails validation.
4. **Transition State:** Axis 2 status is set to `DATA PIPELINE VALIDATION IN PROGRESS` until empirical county ingestion and join validation passes owner review.

---

## D-017 — Empirical source layer takeover rules

**Date:** 2026-08-14  
**Status:** ACCEPTED (Owner Directive via GROK.MD)

1. Deliverable 1 is an evidence/source-integrity rebuild, not authorization to publish Minimum Sustainable Living Cost, Gap, or Adequacy.
2. Production retrieve paths must be official landing pages or proven publisher artifacts. Guessed government filenames are forbidden.
3. `VALIDATED` requires byte verification from a retrieval sidecar. Filesystem mtime is not `retrieved_at`.
4. Fixture tests are not evidence of official file layout. Production code may not read `tests/`.
5. Data Health cannot be `HEALTHY` while Axis 2 is unpublished.
6. Shared ACS 2023 5-Year weights may be used for both 2024 and 2026 cost years if labeled as the weight source vintage, not as a 2026 Census file.
7. MEPS HC-243 (2022 data year) may be used as the OOP source vintage if labeled honestly and not called “2024 MEPS.”
8. 2025 ASEC SHA values `318845a2…c0deef0b` and `318845a2…ea6497284` remain dual-recorded until the archive is re-retrieved and hashed. Do not silently pick one.

---

## Pending decisions

### P-001 — Composite normalization

Historical percentile, adequacy scoring, hybrid, or other.

### P-002 — Composite weights

No final weights approved.
