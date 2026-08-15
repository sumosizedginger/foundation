"""Social Participation and Recreation component calculator for Minimum Sustainable Living Cost.

Rule: Explicit, visible, non-zero component modeling modest social participation
and recreation based on BLS CE lower-quartile (P25) expenditure among single-person
positive spenders, adjusted regionally via BEA Regional Price Parities (RPP).
"""

from __future__ import annotations

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.living_cost.owner_freeze import (
    canonical_social_recreation_annual,
    preferred_social_recreation_annual,
    recreation_output_pair,
)


def calculate_social_recreation(
    base_annual_recreation: float,
    rpp_adjustment_factor: float,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "",
    retrieved_at: str = "2026-08-13T00:00:00Z",
    *,
    apply_canonical_floor: bool = True,
) -> LivingCostComponentObservation:
    """Return a social & recreation observation.

    OD-008: canonical amount is MAX(empirical P25, $1,200/year) before RPP.
    """
    from foundation.living_cost.owner_freeze import MINIMUM_SOCIAL_RECREATION_ANNUAL

    floored = (
        canonical_social_recreation_annual(base_annual_recreation)
        if apply_canonical_floor
        else float(base_annual_recreation)
    )
    if floored <= 0:
        raise ValueError("Social & recreation baseline must be non-zero and positive")

    adjusted_val = round(floored * rpp_adjustment_factor, 2)
    if apply_canonical_floor:
        # Target-year floor is in dollars. A sub-1.0 RPP must not push the
        # canonical local amount below $1,200/year.
        adjusted_val = max(adjusted_val, MINIMUM_SOCIAL_RECREATION_ANNUAL)

    return LivingCostComponentObservation(
        component_id="social_recreation",
        category="social_recreation",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=adjusted_val,
        value_monthly=round(adjusted_val / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
        source_id=f"social_rec_{reference_year}",
        source_variable="bls_ce_p25_recreation_rpp_adjusted",
        source_url="https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area",
        source_release="BLS Consumer Expenditure Survey / BEA Regional Price Parities",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"OD-008 FROZEN: MAX(empirical P25 ${base_annual_recreation:,.0f}, "
            f"$1,200 canonical floor) = ${floored:,.0f}; preferred modest-life "
            f"${preferred_social_recreation_annual(base_annual_recreation):,.0f}. "
            f"RPP factor {rpp_adjustment_factor:.3f}. "
            f"Pair={recreation_output_pair(base_annual_recreation)}."
        ),
    )
