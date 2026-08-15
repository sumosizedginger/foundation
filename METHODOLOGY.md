# Methodology Specification

**Version:** `0.2.0-draft`  
**Status:** In Progress (Owner Authorized Methodology Migration)  
**Supersedes:** `0.1.0-draft` (Survival Floor numeric modeling superseded by D-015; Population Anchor preserved)

---

## 1. Executive Summary & Dual-Axis Economic Framework

The Foundation is a public, deterministic, auditable economic research instrument designed to measure the economic health of the bottom 30% of Americans.

The framework operates on two distinct, un-conflated economic axes:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                                AXIS 1                                  │
│                       POPULATION ANCHOR                                │
│                     "Who are the Bottom 30%?"                          │
│                                                                        │
│   • Ranked by per-person household money income (HTOTVAL / H_NUMPER)   │
│   • Weighted 30th percentile using Census CPS ASEC person weights      │
│   • Verified 2024 Income Reference Value: $21,800.00 / person / year   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                       COMPARED DETERMINISTICALLY (2024)
                                    │
┌───────────────────────────────────┴────────────────────────────────────┐
│                                AXIS 2                                  │
│                  MINIMUM SUSTAINABLE LIVING COST                       │
│              "What does basic independent life cost?"                  │
│                                                                        │
│   • Gross income required for 1 independent adult to maintain a        │
│     minimally sustainable life without public benefits or debt         │
│   • Built bottom-up from county/local housing, food, auto, health,     │
│     essentials, social participation, and local/state/federal taxes    │
│   • Aggregated using ACS adult population weights (P25, Median, P75)   │
└────────────────────────────────────────────────────────────────────────┘
```

- **Survival Gap (2024 Time-Comparable):** `2024 Population Anchor − 2024 Minimum Sustainable Living Cost`
- **Adequacy Ratio (2024 Time-Comparable):** `2024 Population Anchor / 2024 Minimum Sustainable Living Cost`

---

## 2. Historical Audit Trail & Retirement of V0.1 Survival Floor

|    Methodology Version    |         Status         | Effective Dates | Survival Floor / Living Cost Status                                                                                                                                                                                                                                                               | Population Anchor Status                                                                                      |
| :-----------------------: | :--------------------: | :-------------: | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------ |
|       `0.1.0-draft`       |  Retired / Superseded  |   2026-08-13    | **$27,960 Single-Adult Floor (RETIRED)**<br>Constructed as a national synthesized constant with ACA subsidies ($140/mo health), simplified $320/mo transit, and $3,000 national tax constant. Rejected under D-015 for insufficiently defensible local, healthcare, benefit, and tax assumptions. | **$21,800.00 (VERIFIED)**<br>Canonical person-weighted P30 of per-person household income from 2025 CPS ASEC. |
| `0.2.0-draft (prototype)` |   Rejected / Retired   |   2026-08-13    | **$51,220.16 / $55,551.89 Prototypes (RETIRED under D-016)**<br>Initial prototype used provisional state-level assumptions and synthetic locality tiers (45/35/20 population shares, 1.22/0.98/0.78 multipliers). Rejected under Owner Directive for failing empirical county source standards.   | **$21,800.00 (VERIFIED)**<br>Preserved unchanged.                                                             |
| `0.2.0-draft (empirical)` | Validation in Progress |     Active      | **Minimum Sustainable Living Cost (DATA PIPELINE VALIDATION IN PROGRESS)**<br>Empirical county-level HUD FMR ingestion, Census ACS adult population joins across all ~3,143 real U.S. counties, CMS Marketplace PUFs, MEPS OOP tables, and deterministic tax engine.                              | **$21,800.00 (VERIFIED)**<br>Preserved unchanged.                                                             |

---

## 3. Axis 1 · Canonical Bottom-30 Population Anchor

### 3.1 Formula

For each person $i$ residing in household $h$:

$$\text{per\_person\_income}_{i} = \frac{\text{HTOTVAL}_{h}}{\text{H\_NUMPER}_{h}}$$

where:

- $\text{HTOTVAL}_{h}$ is the total money income of the household from all survey-defined cash sources before taxes.
- $\text{H\_NUMPER}_{h}$ is the total number of persons living in household $h$.

### 3.2 Ranking & Quantile Calculation

Every individual in the civilian noninstitutional population is ranked in ascending order by their assigned $\text{per\_person\_income}_{i}$ and weighted by their official CPS ASEC person supplement weight $\text{MARSUPWT}_{i}$ (scaled by $\frac{1}{100}$).

The Population Anchor $P_{30}$ is the income cutoff where cumulative represented population weight reaches 30%:

$$P_{30} = \inf \left\{ y \in \mathbb{R} : \frac{\sum_{i: \text{income}_i \le y} \text{MARSUPWT}_i}{\sum_{i} \text{MARSUPWT}_i} \ge 0.30 \right\}$$

### 3.3 Strict Rules

1. **Person Unit:** We rank human beings, not households.
2. **Negative Incomes Retained:** Negative cash incomes (e.g. self-employment or farm losses) are valid economic positions and are never clamped to zero.
3. **No Equivalence Scale:** We do not treat children or secondary adults as fractional humans. One supported human equals one human.

---

## 4. Axis 2 · Minimum Sustainable Living Cost

### 4.1 Canonical Definition

> The **Minimum Sustainable Living Cost** is the gross money income required for one independent adult to maintain a minimally sustainable life without means-tested public assistance, debt-financing ordinary necessities, financial support from another person, roommates, or shared household income.

### 4.2 Excluded Benefits (Benefit-Neutral Baseline)

The baseline represents independent economic self-sufficiency and strictly **excludes**:

- SNAP (Food Stamps)
- Medicaid / Medicare
- Affordable Care Act (ACA) Premium Tax Credits / Cost-Sharing Subsidies
- Housing vouchers / Section 8 / public housing subsidies
- Low Income Home Energy Assistance Program (LIHEAP)
- Cash welfare assistance (TANF / General Assistance)
- Refundable means-tested tax credits (e.g., EITC, Additional Child Tax Credit)
- Private charity, food pantries, or family financial transfers
- Credit card or personal debt used to finance recurring consumption

_Note: Standard statutory tax deductions (e.g. federal standard deduction) and statutory marginal tax brackets are standard tax law, not means-tested benefits, and apply normally._

### 4.3 What is Included (Minimally Sustainable Life)

- Independent standard-quality housing (1-bedroom rental)
- Adequate, nutritious food (100% home meal preparation baseline)
- Reliable automobile transportation (mileage, fuel, insurance, maintenance, replacement reserve)
- Unsubsidized comprehensive health insurance (adequate Silver Marketplace plan) plus realistic out-of-pocket medical utilization
- Mobile phone and broadband connectivity
- Essential clothing, footwear, laundry, personal hygiene, and household cleaning supplies
- Ordinary household replacement items
- Modest, visible social participation and recreation (nonzero)
- All mandatory federal, state, and local taxes required to generate the necessary disposable income.

---

## 5. Geographic & Time Architecture

### 5.1 Local Resolution & Population Weighting

- **Primary Geographic Unit:** County / HUD Fair Market Rent (FMR) Area across all 50 states plus the District of Columbia.
- **State Aggregation:** Local county living costs are aggregated to the state level using Census ACS adult-population weights ($w_c$):
  - **State P25:** 25th percentile of local living costs.
  - **State Median (Primary Reference):** Population-weighted 50th percentile.
  - **State P75:** 75th percentile of local living costs.
  - **State Minimum & Maximum:** Lowest and highest observed county floors in the state.
- **National Aggregation:** National P25, Median, and P75 are calculated by aggregating all local county observations weighted by national adult population. No single national "average rent" or national basket is ever used.

### 5.2 Vintage Architecture

1. **2024 Time-Comparable Vintage:** Built from 2024 source inputs (or translated using the OD-010 hybrid rules) to provide an exact temporal match for the 2024 Population Anchor ($21,800). Historical 2024 costs are not rewritten with later-year prices or later ACS population vintages.
2. **2026 Current Living Cost Vintage:** Built from the newest authoritative sources actually available at calculation time (FY2026 FMR, current USDA months / YTD, current CMS Marketplace rates, newest ACS 5-Year county weights).
   _The 2026 Current Living Cost is never subtracted from the 2024 Population Anchor._

**OD-001 (FROZEN):** Geographic weights use the newest appropriate ACS 5-Year county adult 18+ vintage. As of the owner freeze that vintage is 2024, so both years currently share it. Current-cost calculations advance when a newer ACS 5-Year county vintage exists. A fixed-2024-weight sensitivity is retained for longitudinal comparison.

**OD-010 (FROZEN):** Structural quantities use `LATEST_AVAILABLE` and are not inflation-adjusted. Target-year laws use `RULE_YEAR`. High-frequency prices use actual target-year observations or YTD. Lagged nominal dollar series use `CPI_UPDATED` with the most component-specific official index. Already-local current prices receive no extra generic CPI. Every component stores `project_cost_year`, `source_data_year`, `translation_method`, `price_index_series`, `translation_factor`, `original_value`, and `translated_value`. Silent `LATEST_AVAILABLE` nominal carry-forward is forbidden.

**OD-013 (FROZEN):** FY2024 Connecticut keeps HUD legacy-county geography and reconstructs ACS adult weights from the official town/county-subdivision crosswalk. FY2026 joins HUD planning-region FIPS directly to ACS planning-region geography.

---

## 6. Component Model Specifications

### 6.1 Housing Model

- **Unit Type:** Independent standard-quality 1-Bedroom rental apartment.
- **Primary Source:** HUD Fair Market Rents (FMR) at the 40th percentile.
- **Gross-Rent Utility Accounting:** HUD FMR includes shelter rent plus tenant-paid essential utilities (water, sewer, trash, heating, electricity). Utility expenses covered by FMR are not added separately to avoid double-counting.

### 6.2 Food Model

- **Primary Sustainable Baseline:** USDA Low-Cost Food Plan (Single adult age 19–50 with official +20% 1-person size adjustment).
- **Sensitivity Bound:** USDA Thrifty Food Plan.
- **Profile:** Transparent midpoint between adult male and adult female monthly expenditure baselines. Alaska and Hawaii adjusted via USDA regional reports.

### 6.3 Transportation Model (Automobile Baseline)

- **Model Structure:** Independent automobile ownership model:
  $$\text{AutoCost} = \text{Fuel} + \text{Auto Insurance} + \text{Routine Maintenance/Tires} + \text{Registration/Fees} + \text{Vehicle Replacement Reserve}$$
- **OD-003 mileage (FROZEN):** Canonical is the NHTS weighted median for one-person, one-worker, age 18–64 licensed-driver households with valid annual miles. Label: **Foundation Mobility Standard** derived from observed NHTS median. Not “measured minimum necessary mileage.” Sensitivities: P25, mean, P75. Current measured median candidate ≈ 10,000 miles/year.
- **OD-004 MPG (FROZEN):** Modest used gasoline compact+midsize passenger-car cohort, model years approximately 8–12 years before the project cost year. Canonical MPG is the cohort median estimated real-world combined MPG. 24 / 28 / 32 are not hardcoded.
- **OD-005 replacement (FROZEN formula):** \((\text{acquisition} - \text{residual}) / \text{remaining usable years}\). Numeric inputs are not frozen. Retired $10,000 / $2,000 / 5 years / $1,600 are not defaults.
- **OD-006 insurance (FROZEN):** NAIC combined average premium where the state statistic is available. Sensitivities: average expenditure; liability-only where reproducible. 2023 NAIC dollars are not labeled as later-year dollars.
- **OD-007 maintenance (FROZEN methodology):** Weighted mean including zeros among single-person vehicle-owning CE units using the documented VQB/MTBI architecture. Evidence remains `INCOMPLETE_PROVENANCE` until the official BLS retrieve is reproducible.

### 6.4 Healthcare Model

- **Profile:** Unsubsidized adult (age 40, single, non-smoker, no dependents).
- **Plan Tier:** Lowest-cost adequate Silver-level Marketplace plan (CMS Exchange Public Use Files / State Exchange PUFs). Bronze plans with catastrophic deductibles that render ordinary care unusable are rejected. No subsidy, Medicaid, employer contribution, or fake deductible/rating-area fallback.
- **OD-002 OOP (FROZEN):** Weighted mean annual OOP among adults 18–64 with private insurance. Sensitivities: weighted median and weighted P75. Use the newest Full Year Consolidated MEPS file actually released (HC-251 / 2023 at freeze time unless a later file is listed).

### 6.5 Connectivity & Essentials

- **OD-009 connectivity (FROZEN):** Canonical minimum is **both** one ordinary mobile phone/data line **and** one residential broadband connection meeting the current ordinary FCC fixed-broadband benchmark (working standard 100 Mbps down / 20 Mbps up). Mobile-only and broadband-only are sensitivities. ACS internet tables are not a price source. If no acceptable authoritative mobile **price** source exists, methodology stays frozen and mobile evidence stays `SOURCE_GAP`.
- **Essentials:** Restrictive basket of personal hygiene, toiletries, cleaning products, laundry, and basic apparel/footwear replacement using BLS CE single-person consumer unit microdata.

### 6.6 Social & Recreation

- **OD-008 (FROZEN):** Empirical baseline is BLS CE weighted P25 among single-person positive spenders on the approved recreation/social allowlist, adjusted regionally via BEA RPP.
- **Canonical MSLC:** \(\max(\text{empirical P25}, \$1{,}200/\text{year})\).
- **Preferred modest-life sensitivity:** \(\max(\text{empirical P25}, \$2{,}400/\text{year})\).
- Empirical P20 / P25 / P30 are retained for transparency. The $200/month case is the **preferred modest-life social/recreation standard**, not a luxury case. These floors are consumption/social-participation standards, not emergency savings.

### 6.7 Resilience & Irregular Expenses

- **OD-012 (FROZEN):** No additional generic resilience reserve. Canonical extra reserve is **$0**. Do not add 5%, 10%, $1,200, $50/month, $100/month, or generic emergency savings.
- Predictable irregular costs are annualized inside their actual component (vehicle repairs and replacement in transportation, clothing in essentials, healthcare utilization in healthcare). Newly discovered uncovered necessities are researched and added to the real category — not sneaked in as miscellaneous resilience.

---

## 7. Deterministic Tax Engine

Taxes are solved dynamically. For any geography $g$ and reference year $y$, core required net disposable income is:

$$\text{NetNeeds}(g, y) = \text{Housing} + \text{Food} + \text{Transportation} + \text{Healthcare} + \text{Connectivity/Essentials} + \text{Social/Recreation} + \text{Resilience}$$

The Minimum Sustainable Living Cost is the minimum gross income $G$ satisfying:

$$G - \text{Taxes}(G, g, y) \ge \text{NetNeeds}(g, y)$$

where $\text{Taxes}(G, g, y)$ computes:

1. Employee Social Security FICA (6.2% up to statutory cap)
2. Employee Medicare FICA (1.45%)
3. Federal Statutory Income Tax (incorporating federal standard deduction and marginal brackets)
4. State Statutory Income Tax (incorporating state standard deductions, personal exemptions, and state marginal brackets)
5. Local Income/Earnings Taxes (where applicable), classified under **OD-011**:
   - A coterminous municipality/county-equivalent — apply directly;
   - B true county-level tax — apply directly;
   - C municipality covering only part of the modeled county — place/subcounty or defensible population-weighted exposure, else `SOURCE_GAP` / `UNAVAILABLE`;
   - D unresolved — do not invent a rate.
     A partial-city tax is never applied automatically to an entire county. Statewide average local tax rates are forbidden.

---

## 8. Validation Gates (Release Criteria)

Before any Minimum Sustainable Living Cost estimate is promoted to `VERIFIED`:

1. All 50 states plus DC fully modeled from local county/FMR data.
2. Complete provenance artifacts (URL, retrieval timestamp, SHA-256 hash, parser version).
3. Independent reproduction of tax root-finding solver.
4. Independent reproduction of county-to-state and state-to-national population weighting.
5. Strict temporal separation between 2024 and 2026 vintages.
6. Benchmark comparisons documented against MIT Living Wage and United For ALICE.
7. Sensitivity analysis completed across food plans, healthcare utilization tiers, and mileage baselines.
8. Explicit owner review and authorization.
