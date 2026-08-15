# Living-cost source/methodology correction

Started from audited HEAD `f2c0636690ac2408d0f537c9fd657225c75e63f3`.

Historical Deliverable 2A milestone `b2a30ef4b87a2db38eb5f7d982e0e8b5c9b63b4c`
is archived at `data/metadata/historical/living_cost_deliverable_2a_report.md`
and is **not** current project status. Current closeout:
`data/metadata/living_cost_pre_owner_freeze_closeout.md`.

Final pushed SHA: `1de6755978455a205bc759229415d71319518d59`.

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.

No 2024/2026 MSLC, state ranking, national median, Gap, Adequacy Ratio, or Composite Score was calculated.

Historical correction-pass notes. **Superseded for decision status by D-043 / living_cost_owner_decisions_frozen.md.** OD-001 through OD-013 are now ACCEPTED / FROZEN. Evidence gaps below remain.

## What this pass changed

1. **OD-002 / MEPS** — HC-251 (2023) remains the latest listed full-year file. AHRQ schedule lists 2024 Full Year Consolidated for August 2026. A listing refresh check runs before owner freeze. The 2024 file is not claimed until it appears in the official PUF listing.
2. **OD-003 / NHTS** — Person file is joined. Age 18-64 and DRIVER=1 are actually executed. Sample labeled observed travel behavior, not minimum-necessary mileage.
3. **OD-004 / EPA MPG** — Official EPA/DOE fueleconomy.gov vehicle file is retrieved. Canonical cohort is now frozen: used-car gasoline compact/midsize, median combined real-world MPG. 24/28/32 are not the empirical model.
4. **OD-006 / NAIC** — Official free 2022/2023 Auto Insurance Database Report is retrieved. Status is no longer LICENSING_REVIEW merely because a previous agent missed the free file. `redistribution_status = FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED`. The remaining decision is which insurance measure to use.
5. **OD-007 / maintenance** — Candidate statistics among single-person vehicle-owning CE units include zeros. P25-among-positive-spenders is not automatic.
6. **OD-009 / connectivity** — ACS removed as a PRICE source. FCC Urban Rate Survey is the broadband price research source. Mobile remains a separate gap.
7. **OD-010 / lag** — Hybrid translation: quantities LATEST_AVAILABLE; legal RULE_YEAR; monthly YTD; lagged nominal dollars CPI_UPDATED candidate. Unadjusted LATEST_AVAILABLE kept as sensitivity.
8. **OD-011 / municipal tax** — Classification A coterminous / B county-level / C partial municipality / D unresolved. No city tax applied countywide without geographic justification.
9. **OD-013 / Connecticut** — Planning-region FIPS corrected to 09110–09190 (nine). Architecture is keep HUD geography = legacy county and reconstruct adult weights from the official Census county-to-county-subdivision crosswalk. Leave unmatched if reconstruction cannot be reproduced.
10. **CMS SBE** — Official per-state SBE QHP PUF zips for 2024 and 2026. The national dictionary zip is not treated as missing plan data.
11. **Provenance** — VALIDATED requires retrieved_at, resolved URL, SHA-256, byte size, and cache identity. Cache hits without a sidecar are re-retrieved or downgraded to INCOMPLETE_PROVENANCE. retrieved_at is never invented from mtime.
12. **USDA 2026** — Exact `months_included`, `month_count`, `first_month`, `last_month` derived from source month labels, not row counts.
13. **GitHub Actions** — `actions/checkout@v7`, `actions/setup-python@v7`, `actions/setup-node@v6`. Node 24 kept.

OD-001, OD-005, OD-008, and OD-012 were preserved in substance.

## Unresolved owner decisions

OD-001 through OD-013 remain pending. None accepted.

## Headline

NO MINIMUM SUSTAINABLE LIVING COST HEADLINE WAS CALCULATED OR PUBLISHED.
