# Project Status

**Updated:** 2026-08-14  
**Active Methodology Version:** `0.2.0-draft`  
**Current Milestone:** Deliverable 1 — empirical source layer + data integrity rebuild (in progress; not complete)

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

### Phases 2–11: Not complete

The $51,220.16 / $55,551.89 prototype headlines, 51-state rankings, -$29,420.16 gap, and 43% adequacy ratio are **retired**. They were produced from synthetic geography and are not current results.

Current work is the empirical source layer: official HUD/CMS/MEPS/BLS artifacts or explicit `SOURCE_GAP` / `LICENSING_REVIEW`. No living-cost headline is authorized.

---

## 3. Explicit Release Locks

- [x] Composite Foundation Score remains locked in `PRELAUNCH / RESEARCH`.
- [x] Minimum Sustainable Living Cost remains `DATA PIPELINE VALIDATION IN PROGRESS` / unpublished.
