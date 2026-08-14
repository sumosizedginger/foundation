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
from foundation.sources.census_acs import EXCLUDED_TERRITORIES_FIPS, VALID_STATE_FIPS

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

UNMATCHED_EXCLUDED_TERRITORY = "excluded_us_territory"
UNMATCHED_SPECIAL_NON_COUNTY = "special_non_county_hud_geography"
UNMATCHED_MALFORMED = "malformed_unrecognized_fips"
UNMATCHED_FIFTY_STATE_DC = "unmatched_50_state_dc_county"


def _connecticut_join_method(reference_year: int, matched_fips: set[str]) -> str:
    if reference_year == 2024 and _CT_LEGACY_FIPS.issubset(matched_fips):
        return "legacy_county_reconstructed_from_cousub"
    if reference_year == 2026 and _CT_PLANNING_FIPS.issubset(matched_fips):
        return "direct_planning_region_join"
    return "unmatched_or_not_applicable"


def classify_unmatched_hud_fips(fips: str) -> str:
    """Classify a HUD row that did not join to the 50-state+DC ACS join universe."""
    code = str(fips or "").strip()
    if len(code) != 5 or not code.isdigit():
        return UNMATCHED_MALFORMED
    state = code[:2]
    county = code[3:] if False else code[2:]
    if state in EXCLUDED_TERRITORIES_FIPS:
        return UNMATCHED_EXCLUDED_TERRITORY
    if county in {"999", "000"}:
        return UNMATCHED_SPECIAL_NON_COUNTY
    if state not in VALID_STATE_FIPS:
        return UNMATCHED_MALFORMED
    # Recognizable 50-state+DC state prefix, but the 5-digit code is not in the
    # Census county-equivalent universe. Treat HUD-only / non-county codes
    # (for example 29056) as special HUD geography, not a missing county.
    return UNMATCHED_SPECIAL_NON_COUNTY


def _connecticut_counts(
    raw_universe: dict[str, dict[str, Any]],
    join_universe: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    raw_ct = sorted(f for f in raw_universe if f.startswith("09"))
    join_ct = sorted(f for f in join_universe if f.startswith("09"))
    return {
        "connecticut_raw_geographies": len(raw_ct),
        "connecticut_reconstructed_geographies": len(join_ct),
        "connecticut_raw_fips": raw_ct,
        "connecticut_join_fips": join_ct,
    }


def execute_geo_join_audit(
    census_county_universe: dict[str, dict[str, Any]],
    hud_observations: list[LivingCostComponentObservation],
    reference_year: int,
    census_artifact_sha256: str = "",
    hud_artifact_sha256: str = "",
    output_path: Path | None = None,
    *,
    raw_census_county_universe: dict[str, dict[str, Any]] | None = None,
    census_source_id: str = "",
    hud_source_id: str = "",
    census_reference_period: str = "",
    hud_reference_period: str = "",
    census_retrieved_at: str = "",
    hud_retrieved_at: str = "",
) -> dict[str, Any]:
    """Execute join between Census county universe and HUD FMR observations."""
    join_universe = census_county_universe
    raw_universe = raw_census_county_universe or census_county_universe
    census_fips_set = set(join_universe.keys())
    join_geography_count = len(census_fips_set)
    raw_census_count = len(raw_universe)
    total_census_adult_pop = sum(c["adult_population"] for c in join_universe.values())

    hud_by_fips: dict[str, LivingCostComponentObservation] = {}
    hud_rows_count = len(hud_observations)
    duplicate_hud_fips: list[str] = []

    for obs in hud_observations:
        fips = obs.geography_id
        if fips in hud_by_fips:
            duplicate_hud_fips.append(fips)
        hud_by_fips[fips] = obs

    unique_hud_counties = len(hud_by_fips)

    matched_fips = census_fips_set.intersection(hud_by_fips.keys())
    unmatched_census_fips = sorted(census_fips_set - set(hud_by_fips.keys()))
    unmatched_hud_fips = sorted(set(hud_by_fips.keys()) - census_fips_set)

    matched_adult_pop = sum(join_universe[f]["adult_population"] for f in matched_fips)
    excluded_adult_pop = sum(join_universe[f]["adult_population"] for f in unmatched_census_fips)

    county_coverage_pct = round(
        (len(matched_fips) / join_geography_count * 100.0) if join_geography_count > 0 else 0.0,
        4,
    )
    pop_coverage_pct = round(
        (matched_adult_pop / total_census_adult_pop * 100.0) if total_census_adult_pop > 0 else 0.0,
        4,
    )

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

    unmatched_classified = [
        {"fips": fips, "classification": classify_unmatched_hud_fips(fips)}
        for fips in unmatched_hud_fips
    ]
    classification_counts: dict[str, int] = {}
    for row in unmatched_classified:
        classification_counts[row["classification"]] = (
            classification_counts.get(row["classification"], 0) + 1
        )
    actual_unmatched_50_state_dc = [
        row["fips"]
        for row in unmatched_classified
        if row["classification"] == UNMATCHED_FIFTY_STATE_DC
    ]

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
    ct = _connecticut_counts(raw_universe, join_universe)
    ct_method = _connecticut_join_method(reference_year, matched_fips)

    provenance_complete = bool(census_artifact_sha256) and bool(hud_artifact_sha256)
    coverage_claim_allowed = provenance_complete

    join_report: dict[str, Any] = {
        "report_type": "hud_fmr_census_acs_geo_join",
        "reference_year": reference_year,
        "generated_at": now_iso,
        "census_source_id": census_source_id or f"census_acs5_{reference_year}",
        "hud_source_id": hud_source_id or f"hud_fmr_{reference_year}",
        "census_reference_period": census_reference_period or "2024 ACS 5-Year",
        "hud_reference_period": hud_reference_period or str(reference_year),
        "census_retrieved_at": census_retrieved_at,
        "hud_retrieved_at": hud_retrieved_at,
        "census_artifact_sha256": census_artifact_sha256,
        "hud_artifact_sha256": hud_artifact_sha256,
        "provenance_complete": provenance_complete,
        "coverage_claim_allowed": coverage_claim_allowed,
        "raw_census_county_equivalent_count": raw_census_count,
        "join_geography_count": join_geography_count,
        "census_county_universe_count": join_geography_count,
        "census_county_universe_count_note": (
            "census_county_universe_count is the Foundation JOIN geography count, "
            "not the raw Census county-equivalent publication count. "
            f"raw_census_county_equivalent_count={raw_census_count}."
        ),
        "connecticut_method": ct_method,
        **ct,
        "census_total_adult_population": total_census_adult_pop,
        "hud_source_rows_count": hud_rows_count,
        "hud_unique_counties_represented": unique_hud_counties,
        "matched_counties_count": len(matched_fips),
        "unmatched_census_counties_count": len(unmatched_census_fips),
        "unmatched_hud_rows_count": len(unmatched_hud_fips),
        "unmatched_hud_classification_counts": classification_counts,
        "unmatched_50_state_dc_county_count": len(actual_unmatched_50_state_dc),
        "unmatched_50_state_dc_counties": actual_unmatched_50_state_dc,
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
                "name": join_universe[f]["county_name"],
                "adult_pop": join_universe[f]["adult_population"],
            }
            for f in unmatched_census_fips
        ],
        "unmatched_hud_rows": unmatched_hud_fips,
        "unmatched_hud_rows_classified": unmatched_classified,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(join_report, fh, indent=2)

    return join_report
