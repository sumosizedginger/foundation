# Project Status

Updated: 2026-08-13

## Proven & Completed in V0.1

- [x] Product constitution & authority order (`AGENT.md`)
- [x] Canonical Bottom-30 definition locked (`household income / persons; person-weighted 30th percentile`)
- [x] 2025 CPS ASEC (2024 Income) Population Anchor reproduced: **$21,800.00**
- [x] Independent percentile cross-check passed (difference = 0.00)
- [x] Historical CPS ASEC vintages processed (2024 Survey: $20,688.00; 2023 Survey: $19,304.60)
- [x] Machine-readable validation reports generated for all 3 vintages (`data/metadata/`)
- [x] Implied MARSUPWT scaling audited (factor 100 -> ~337.7M represented population in 2025)
- [x] Multi-quantile ladder calculated (P10, P20, P30, P40, P50, P75, P90)
- [x] Second economic axis implemented: **Survival Floor** ($27,960/yr research estimate), **Survival Gap** (-$6,160), and **Adequacy Ratio** (0.78)
- [x] Independent household survival composition matrix (sizes 1–5) modeled with genuine economies of scale
- [x] Survival floor benchmark comparisons against MIT Living Wage, ALICE, and OPM documented
- [x] Historical nominal vs. CPI-U constant 2024 dollar series computed
- [x] Registered BLS National Economic Pressure Signals ingested with complete provenance metadata
- [x] Open-source licensing structure established (Apache 2.0 + CC BY 4.0 + trademark reservation)
- [x] Deterministic update pipeline & build scripts (`pipeline.py`, `build_site.py`, `update_foundation.py`)
- [x] Public static dashboard built according to 6-question hierarchy with provenance inspection
- [x] Automated test suite passing with 100% test coverage for calculations and schemas

## Explicit Prelaunch Locks

- [x] Composite Foundation Score remains locked in `PRELAUNCH / RESEARCH` (no fake 0–100 number)
- [x] Single-adult Survival Floor marked as `RESEARCH ESTIMATE` pending further validation

## Next Milestones

1. State/regional cost-of-living survival floor extensions (BEA RPP / HUD Small Area FMR integration).
2. Longitudinal microdata panel analysis for mobility pillar research.
3. Composite normalization framework review (sensitivity analysis & double-counting audit).
