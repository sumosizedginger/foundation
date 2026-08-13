"""Connectivity and essentials component calculator for Minimum Sustainable Living Cost.

Rule: 1 mobile line + broadband connectivity + restricted necessity basket
(hygiene, cleaning supplies, toiletries, basic apparel/footwear replacement)
from BLS Consumer Expenditure single-person consumer units.
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import LivingCostComponentObservation


def calculate_connectivity_and_essentials(
    connectivity_annual: float,
    essentials_annual: float,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Return validated connectivity and essentials component observations."""
    conn_obs = LivingCostComponentObservation(
        component_id="connectivity",
        category="connectivity",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=round(connectivity_annual, 2),
        value_monthly=round(connectivity_annual / 12.0, 2),
        unit="USD",
        status="measured",
        source_id=f"connectivity_{reference_year}",
        source_variable="mobile_and_broadband_baseline",
        source_url="https://www.fcc.gov/reports-research/reports/measuring-broadband-america",
        source_release="FCC / BLS CE Telecommunications",
        source_reference_period=str(reference_year),
        retrieved_at="",
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes="1 mobile phone line (talk/text/data) + basic residential broadband connectivity.",
    )

    ess_obs = LivingCostComponentObservation(
        component_id="essentials",
        category="essentials",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=round(essentials_annual, 2),
        value_monthly=round(essentials_annual / 12.0, 2),
        unit="USD",
        status="measured",
        source_id=f"bls_ce_essentials_{reference_year}",
        source_variable="single_person_essentials_basket",
        source_url="https://www.bls.gov/cex/",
        source_release="BLS Consumer Expenditure Survey",
        source_reference_period=str(reference_year),
        retrieved_at="",
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes="Restricted necessities: hygiene, toiletries, cleaning supplies, basic apparel/footwear replacement.",
    )

    return [conn_obs, ess_obs]
