"""HUD FMR ⨝ Census ACS County Join Verification Engine.

Executes and audits the geographic join between official HUD Fair Market Rent datasets
and Census ACS 5-Year adult population counts across the 50 States + DC county universe.

Outputs machine-auditable verification artifacts:
- data/metadata/living_cost_geo_join_2024.json
- data/metadata/living_cost_geo_join_2026.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import LivingCostComponentObservation

_CT_LEGACY_FIPS = {
    "09001",
    "09003",
    "09005",
    "09007",
    "09009",
    "09011",
    "09013",
    "09015",
}
_CT_PLANNING_FIPS = {
    "09110",
    "09120",
    "09130",
    "09140",
    "09150",
    "09160",
    "09170",
    "09180",
    "09190",
}


def _connecticut_join_method(reference_year: int, matched_fips: set[str]) -> str:
    if reference_year == 2024 and _CT_LEGACY_FIPS.issubset(matched_fips):
        return "legacy_county_reconstructed_from_cousub"
    if reference_year == 2026 and _CT_PLANNING_FIPS.issubset(matched_fips):
        return "direct_planning_region_join"
    return "unmatched_or_not_applicable"


def execute_geo_join_audit(
    census_county_universe: dict[str, dict[str, Any]],
    hud_observations: list[LivingCostComponentObservation],
    reference_year: int,
    census_artifact_sha256: str = "",
    hud_artifact_sha256: str = "",
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Execute join between Census county universe and HUD FMR observations."""
    census_fips_set = set(census_county_universe.keys())
    total_census_counties = len(census_fips_set)
    total_census_adult_pop = sum(c["adult_population"] for c in census_county_universe.values())

    hud_by_fips: dict[str, LivingCostComponentObservation] = {}
    hud_rows_count = len(hud_observations)
    duplicate_hud_fips: list[str] = []

    for obs in hud_observations:
        fips = obs.geography_id
        if fips in hud_by_fips:
            duplicate_hud_fips.append(fips)
        hud_by_fips[fips] = obs

    unique_hud_counties = len(hud_by_fips)

    # Calculate matched and unmatched
    matched_fips = census_fips_set.intersection(hud_by_fips.keys())
    unmatched_census_fips = sorted(census_fips_set - set(hud_by_fips.keys()))
    unmatched_hud_fips = sorted(set(hud_by_fips.keys()) - census_fips_set)

    matched_adult_pop = sum(census_county_universe[f]["adult_population"] for f in matched_fips)
    excluded_adult_pop = sum(
        census_county_universe[f]["adult_population"] for f in unmatched_census_fips
    )

    county_coverage_pct = round(
        (len(matched_fips) / total_census_counties * 100.0) if total_census_counties > 0 else 0.0, 4
    )
    pop_coverage_pct = round(
        (matched_adult_pop / total_census_adult_pop * 100.0) if total_census_adult_pop > 0 else 0.0,
        4,
    )

    # Multi-county FMR area inspection
    metro_counties: dict[str, list[str]] = {}
    for obs in hud_observations:
        metro_name = (
            obs.notes.split("FMR Area: ")[-1].rstrip(").")
            if "FMR Area: " in obs.notes
            else "Non-Metro"
        )
        metro_counties.setdefault(metro_name, []).append(obs.geography_id)

    multi_county_fmr_areas = {
        k: v for k, v in metro_counties.items() if len(v) > 1 and k != "Non-Metro"
    }

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    join_report: dict[str, Any] = {
        "report_type": "hud_fmr_census_acs_geo_join",
        "reference_year": reference_year,
        "generated_at": now_iso,
        "census_artifact_sha256": census_artifact_sha256,
        "hud_artifact_sha256": hud_artifact_sha256,
        "census_county_universe_count": total_census_counties,
        "census_total_adult_population": total_census_adult_pop,
        "hud_source_rows_count": hud_rows_count,
        "hud_unique_counties_represented": unique_hud_counties,
        "matched_counties_count": len(matched_fips),
        "unmatched_census_counties_count": len(unmatched_census_fips),
        "unmatched_hud_rows_count": len(unmatched_hud_fips),
        "duplicate_hud_fips_count": len(duplicate_hud_fips),
        "duplicate_hud_fips": duplicate_hud_fips,
        "represented_adult_population": matched_adult_pop,
        "excluded_adult_population": excluded_adult_pop,
        "county_coverage_percentage": county_coverage_pct,
        "population_coverage_percentage": pop_coverage_pct,
        "multi_county_fmr_areas_count": len(multi_county_fmr_areas),
        "unmatched_census_counties": [
            {
                "fips": f,
                "name": census_county_universe[f]["county_name"],
                "adult_pop": census_county_universe[f]["adult_population"],
            }
            for f in unmatched_census_fips
        ],
        "unmatched_hud_rows": unmatched_hud_fips,
        "connecticut_method": _connecticut_join_method(reference_year, matched_fips),
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(join_report, fh, indent=2)

    return join_report
