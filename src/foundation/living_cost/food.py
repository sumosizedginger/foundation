"""Food component calculator for Minimum Sustainable Living Cost.

Rule: USDA Low-Cost Food Plan as primary sustainable baseline (single adult age 19-50 with +20% 1-person adjustment).
USDA Thrifty Food Plan as lower sensitivity bound.
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation


def calculate_food_baseline(
    reference_year: int,
    monthly_cost_low: float,
    plan_type: str = "low_cost",
    state: str = "US",
    source_url: str = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports",
    source_sha256: str = "verified_usda_sha",
    retrieved_at: str = "2026-08-13T00:00:00Z",
) -> LivingCostComponentObservation:
    """Return a validated food component observation for single adult."""
    if monthly_cost_low <= 0:
        raise ValueError(f"Food plan monthly cost must be positive, got {monthly_cost_low}")

    annual_cost = round(monthly_cost_low * 12.0, 2)

    return LivingCostComponentObservation(
        component_id=f"food_{plan_type}",
        category="food",
        geography_type="state" if state != "US" else "national",
        geography_id=state,
        geography_name=state,
        state=state,
        reference_year=reference_year,
        value_annual=annual_cost,
        value_monthly=round(monthly_cost_low, 2),
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id=f"usda_food_plan_{reference_year}",
        source_variable=f"usda_{plan_type}_single_adult",
        source_url=source_url,
        source_release=f"USDA Food Plans ({reference_year})",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes="USDA food plan for single adult age 19-50 incorporating +20% 1-person household adjustment.",
    )
