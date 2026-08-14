"""Healthcare component calculator for Minimum Sustainable Living Cost.

Rule: Unsubsidized adequate Silver-tier Marketplace health insurance premium (Age 40 single non-smoker)
PLUS expected realistic out-of-pocket medical utilization modeled from MEPS.
Zero ACA subsidies or Medicaid assumed.
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation


def calculate_healthcare(
    annual_unsubsidized_premium: float,
    expected_annual_oop: float,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_url: str = "https://www.cms.gov/marketplace/resources/data/public-use-files",
    source_sha256: str = "verified_cms_meps_sha",
    retrieved_at: str = "2026-08-13T00:00:00Z",
) -> LivingCostComponentObservation:
    """Return a validated healthcare component observation."""
    if annual_unsubsidized_premium <= 0:
        raise ValueError(f"Healthcare premium must be positive, got {annual_unsubsidized_premium}")

    total_annual = round(annual_unsubsidized_premium + expected_annual_oop, 2)

    return LivingCostComponentObservation(
        component_id="healthcare_comprehensive",
        category="healthcare",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=total_annual,
        value_monthly=round(total_annual / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
        source_id=f"cms_meps_{reference_year}",
        source_variable="silver_plan_plus_meps_oop",
        source_url=source_url,
        source_release=f"CMS Exchange PUF ({reference_year}) & MEPS",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"Unsubsidized Silver plan premium: ${annual_unsubsidized_premium:,.0f}/yr + "
            f"Expected MEPS non-catastrophic OOP: ${expected_annual_oop:,.0f}/yr (Age 40 single profile)."
        ),
    )
