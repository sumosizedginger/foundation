"""Local County Living Cost Engine.

Combines Housing, Food, Transportation, Healthcare, Connectivity, Essentials,
Social & Recreation, and Resilience, then applies the deterministic Tax Solver.
"""

from __future__ import annotations

from datetime import UTC, datetime

from foundation.living_cost.models import ComponentStatus, LocalLivingCost
from foundation.living_cost.taxes import solve_gross_required_income


def compute_local_living_cost(
    geography_id: str,
    geography_name: str,
    state: str,
    reference_year: int,
    adult_population: int,
    housing_annual: float,
    food_annual: float,
    transportation_annual: float,
    healthcare_annual: float,
    connectivity_annual: float,
    essentials_annual: float,
    social_recreation_annual: float,
    resilience_annual: float,
    status: ComponentStatus = ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
) -> LocalLivingCost:
    """Compute local county net needs and gross required income."""
    components = {
        "housing": round(housing_annual, 2),
        "food": round(food_annual, 2),
        "transportation": round(transportation_annual, 2),
        "healthcare": round(healthcare_annual, 2),
        "connectivity": round(connectivity_annual, 2),
        "essentials": round(essentials_annual, 2),
        "social_recreation": round(social_recreation_annual, 2),
        "resilience": round(resilience_annual, 2),
    }

    net_needs = round(sum(components.values()), 2)
    tax_result = solve_gross_required_income(
        net_needs,
        state=state,
        fips_code=geography_id,
        year=reference_year,
    )
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    return LocalLivingCost(
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        profile_id="single_adult_independent",
        adult_population=adult_population,
        components=components,
        net_needs_annual=net_needs,
        net_needs_monthly=round(net_needs / 12.0, 2),
        gross_required_income=tax_result.gross_income,
        gross_required_monthly=round(tax_result.gross_income / 12.0, 2),
        taxes=tax_result.to_dict(),
        status=status,
        validation_state="validated",
        methodology_version="0.2.0-draft",
        calculated_at=now_iso,
    )
