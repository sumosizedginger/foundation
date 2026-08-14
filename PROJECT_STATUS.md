# Project Status

**Updated:** 2026-08-13  
**Active Methodology Version:** `0.2.0-draft`  
**Current Milestone:** Minimum Sustainable Living Cost Methodology Migration (Complete & Verified)

---

## 1. Verified & Operational Components

- [x] Canonical Bottom-30 Population Anchor definition locked (`household money income / persons; person-weighted P30`)
- [x] 2025 CPS ASEC (2024 Income Year) Population Anchor reproduced: **$21,800.00**
- [x] Multi-vintage Population Anchors reproduced (2024 Survey: $20,688.00; 2023 Survey: $19,304.60)
- [x] Machine-readable validation reports generated with SHA-256 integrity checks
- [x] Full Income Quantile Ladder (P10, P20, P30, P40, P50, P75, P90)
- [x] Historical real constant 2024 dollar series computed using BLS CPI-U
- [x] National Economic Pressure Signals (9 monthly BLS series with rate-of-change computations)
- [x] Fast deterministic CI test suite (36 tests passing)
- [x] Open-source licensing (Apache 2.0 software, CC BY 4.0 methodology/data, reserved trademarks)
- [x] GitHub Pages automated CI/CD workflow

---

## 2. Completed Migration: Minimum Sustainable Living Cost (`0.2.0-draft`)

### Phase 0: Retirement of V0.1 Survival Floor

- [x] **Retired $27,960 Single-Adult National Figure:** Superseded by D-015 due to insufficiently defensible local, healthcare, benefit, and tax assumptions.
- [x] **Audit Trail Preserved:** Historical methodology records documented in `METHODOLOGY.md` and `DECISIONS.md`.

### Phase 1: Methodology Specification & Architecture Freeze

- [x] **Decision D-015 Recorded:** Formal authorization of Minimum Sustainable Living Cost.
- [x] **Methodology Frozen (`0.2.0-draft`):** Canonical definition, local county architecture, no-benefits rule, independent auto model, unsubsidized healthcare, explicit social/recreation, and deterministic tax engine.
- [x] **Data Models Frozen:** `LivingCostComponentObservation`, `LocalLivingCost`, `StateLivingCostDistribution`, `NationalLivingCostDistribution`.
- [x] **Data Sources Registry Updated:** HUD FMR, USDA Food Plans, CMS Marketplace PUFs, MEPS, FHWA, NAIC, BLS CE, Census ACS, IRS/State tax schedules.
- [x] **Implementation Plan Deliverable:** Full production source specification, fields, geographic resolution, licensing, and methodological risk analysis.

### Phases 2–11: Implementation, Calculation & Public Deployment

- [x] **Phase 2 & 3: Source Adapters & Component Calculators:** Implemented modular housing (HUD 1BR), food (USDA Low-Cost & Thrifty), transportation (EIA gas + NAIC insurance + BLS CE auto reserve), healthcare (CMS Silver + MEPS OOP), connectivity & essentials (FCC & BLS CE), recreation (BLS CE P25 & BEA RPP), and resilience reserve.
- [x] **Phase 4: Deterministic Tax Engine:** Solves `G - Taxes(G) = NetNeeds` using interval bisection for FICA (Social Security & Medicare), Federal single statutory brackets, 50-State + DC tax schedules, and local income taxes.
- [x] **Phase 5: Local County Engine:** Evaluated local living costs across 50 states + DC.
- [x] **Phase 6 & 7: State & National Aggregators:** Computed adult-population-weighted P25, Median (P50), P75, weighted mean, min, and max across all 50 states + DC.
- [x] **Phase 8 & 9: Time-Comparable & Current Vintages:** Built 2024 Comparable Living Cost (National Weighted Median: **$51,220.16**) and 2026 Current Living Cost (National Weighted Median: **$55,551.89**).
- [x] **Phase 10: Validation, Sensitivities & Benchmark Comparisons:** Sensitivity analysis (Food Thrifty, Health OOP Low/High, Transit Mileage Low/High) and external benchmark divergence analyses (MIT Living Wage, United For ALICE, Official Poverty Measure).
- [x] **Phase 11: Public Dashboard & Presentation:** Interactive 50-state + DC sortable table, state detail provenance inspection, dual-axis cards, Time-Comparable Survival Gap (**-$29,420.16**), and Adequacy Ratio (**0.43 / 43%**).

---

## 3. Explicit Release Locks

- [x] Composite Foundation Score remains locked in `PRELAUNCH / RESEARCH`.
- [x] Minimum Sustainable Living Cost is fully implemented and labeled `RESEARCH ESTIMATE (0.2.0-draft)` until formal promotion gates.
