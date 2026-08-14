"""Housing component calculator for Minimum Sustainable Living Cost.

Rule: Independent 1-bedroom standard-quality rental housing using HUD Fair Market Rents (FMR).
HUD gross rent includes tenant-paid essential utilities; do NOT double-count them.
"""

from __future__ import annotations

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation


def calculate_local_housing(
    fips_code: str,
    fmr_1br_annual: float,
    reference_year: int,
    geography_name: str = "",
    state: str = "",
    source_url: str = "https://www.huduser.gov/portal/datasets/fmr.html",
    source_sha256: str = "",
    retrieved_at: str = "2026-08-13T00:00:00Z",
) -> LivingCostComponentObservation:
    """Return a validated 1BR housing component observation."""
    if fmr_1br_annual <= 0:
        raise ValueError(f"FMR 1BR value must be positive, got {fmr_1br_annual} for {fips_code}")

    return LivingCostComponentObservation(
        component_id="housing_1br",
        category="housing",
        geography_type="county",
        geography_id=fips_code,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=round(fmr_1br_annual, 2),
        value_monthly=round(fmr_1br_annual / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id=f"hud_fmr_{reference_year}",
        source_variable="fmr_1br",
        source_url=source_url,
        source_release=f"HUD FY {reference_year} Fair Market Rents",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes="40th percentile 1-bedroom Fair Market Rent including core tenant-paid utilities.",
    )
