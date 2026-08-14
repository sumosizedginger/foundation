"""Transportation component calculator for Minimum Sustainable Living Cost.

Rule: Explicit automobile ownership model containing necessary mileage, fuel,
insurance, maintenance/tires, registration, and vehicle replacement reserve.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation


@dataclass(frozen=True)
class AutoCostBreakdown:
    annual_miles: float
    fuel_cost_annual: float
    insurance_cost_annual: float
    maintenance_tires_annual: float
    registration_fees_annual: float
    replacement_reserve_annual: float

    @property
    def total_annual(self) -> float:
        return round(
            self.fuel_cost_annual
            + self.insurance_cost_annual
            + self.maintenance_tires_annual
            + self.registration_fees_annual
            + self.replacement_reserve_annual,
            2,
        )


def calculate_transportation(
    breakdown: AutoCostBreakdown,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "verified_auto_sha",
    retrieved_at: str = "2026-08-13T00:00:00Z",
) -> LivingCostComponentObservation:
    """Return a validated transportation component observation."""
    total = breakdown.total_annual
    if total <= 0:
        raise ValueError(f"Transportation total must be positive, got {total}")

    return LivingCostComponentObservation(
        component_id="transportation_auto",
        category="transportation",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=total,
        value_monthly=round(total / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
        source_id=f"auto_model_{reference_year}",
        source_variable="single_adult_auto_ownership",
        source_url="https://www.fhwa.dot.gov/",
        source_release="FHWA / EIA / NAIC / BLS Synthesized Baseline",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"Auto model: {breakdown.annual_miles:,.0f} miles/yr; "
            f"Fuel: ${breakdown.fuel_cost_annual:,.0f}, Ins: ${breakdown.insurance_cost_annual:,.0f}, "
            f"Maint/Tires: ${breakdown.maintenance_tires_annual:,.0f}, Reg: ${breakdown.registration_fees_annual:,.0f}, "
            f"Replacement: ${breakdown.replacement_reserve_annual:,.0f}"
        ),
    )
