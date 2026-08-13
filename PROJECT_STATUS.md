# Project Status

**Updated:** 2026-08-13  
**Active Methodology Version:** `0.2.0-draft`  
**Current Milestone:** Minimum Sustainable Living Cost Methodology Migration (Owner Authorized)

---

## 1. Verified & Operational Components
- [x] Canonical Bottom-30 Population Anchor definition locked (`household money income / persons; person-weighted P30`)
- [x] 2025 CPS ASEC (2024 Income Year) Population Anchor reproduced: **$21,800.00**
- [x] Multi-vintage Population Anchors reproduced (2024 Survey: $20,688.00; 2023 Survey: $19,304.60)
- [x] Machine-readable validation reports generated with SHA-256 integrity checks
- [x] Full Income Quantile Ladder (P10, P20, P30, P40, P50, P75, P90)
- [x] Historical real constant 2024 dollar series computed using BLS CPI-U
- [x] National Economic Pressure Signals (9 monthly BLS series with rate-of-change computations)
- [x] Fast deterministic CI test suite (29 tests passing)
- [x] Open-source licensing (Apache 2.0 software, CC BY 4.0 methodology/data, reserved trademarks)
- [x] GitHub Pages automated CI/CD workflow

---

## 2. In-Progress Migration: Minimum Sustainable Living Cost (`0.2.0-draft`)

### Phase 0: Retirement of V0.1 Survival Floor
- [x] **Retired $27,960 Single-Adult National Figure:** Superseded by D-015 due to insufficiently defensible local, healthcare, benefit, and tax assumptions.
- [x] **Public Interface Updated:** Axis 2 set to `METHODOLOGY REBUILD IN PROGRESS` with clear public explanation.
- [x] **Audit Trail Preserved:** Historical methodology records documented in `METHODOLOGY.md` and `DECISIONS.md`.

### Phase 1: Methodology Specification & Architecture Freeze
- [x] **Decision D-015 Recorded:** Formal authorization of Minimum Sustainable Living Cost.
- [x] **Methodology Frozen (`0.2.0-draft`):** Canonical definition, local county architecture, no-benefits rule, independent auto model, unsubsidized healthcare, explicit social/recreation, and deterministic tax engine.
- [x] **Data Models Frozen:** `LivingCostComponentObservation`, `LocalLivingCost`, `StateLivingCostDistribution`, `NationalLivingCostDistribution`.
- [x] **Data Sources Registry Updated:** HUD FMR, USDA Food Plans, CMS Marketplace PUFs, MEPS, FHWA, NAIC, BLS CE, Census ACS, IRS/State tax schedules.
- [x] **Source & Module Directory Architecture Initialized:** `src/foundation/living_cost/` and `src/foundation/sources/`.
- [x] **Implementation Plan Deliverable:** Full production source specification, fields, geographic resolution, licensing, and methodological risk analysis.

### Upcoming Implementation Phases
- [ ] **Phase 2:** Implement and test individual source connectors.
- [ ] **Phase 3:** Implement component cost calculators.
- [ ] **Phase 4:** Implement deterministic gross-income tax solver.
- [ ] **Phase 5:** Build local county living cost engine.
- [ ] **Phase 6 & 7:** Build state and national population-weighted aggregators.
- [ ] **Phase 8 & 9:** Build 2024 Comparable and 2026 Current living cost vintages.
- [ ] **Phase 10:** Validation gates, sensitivity analysis, and benchmark comparisons (MIT Living Wage, ALICE).
- [ ] **Phase 11:** Rebuild public UI for State/National Minimum Sustainable Living Cost after validation.

---

## 3. Explicit Release Locks
- [x] Composite Foundation Score remains locked in `PRELAUNCH / RESEARCH`.
- [x] Minimum Sustainable Living Cost remains in `IN_PROGRESS / RESEARCH` until validation gates pass.
