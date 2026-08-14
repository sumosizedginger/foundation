"""Transportation component assembly.

Unsupported constants (28 MPG, $1,200 maintenance, $1,600 replacement,
hand-entered 51-state registration fees) are not used as measured inputs.
Those components remain ESTIMATED_OWNER_REVIEW / SOURCE_GAP until the
owner packet is resolved.
"""

from __future__ import annotations

from dataclasses import dataclass

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


def get_state_registration_fee(state: str) -> float:
    """Registration fees are a SOURCE_GAP until primary DMV sources are inventoried."""
    raise ValueError(
        f"State vehicle registration fee SOURCE_GAP for {state.upper()}: "
        "uncited 51-state constants were removed (GROK.MD §20)."
    )


def calculate_transportation(
    breakdown: AutoCostBreakdown,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "",
    retrieved_at: str = "",
) -> LivingCostComponentObservation:
    """Return a validated transportation component observation (ESTIMATED)."""
    total = breakdown.total_annual
    if total <= 0:
        raise ValueError(f"Transportation total must be positive, got {total}")

    if not retrieved_at:
        from datetime import UTC, datetime

        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

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
        status=ComponentStatus.ESTIMATED,
        source_id=f"transport_model_{reference_year}",
        source_variable="single_adult_auto_ownership_model",
        source_url="https://www.fhwa.dot.gov/",
        source_release=f"Transportation model assumptions ({reference_year})",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"Auto model (ESTIMATED_OWNER_REVIEW): {breakdown.annual_miles:,.0f} mi/yr; "
            f"Fuel: ${breakdown.fuel_cost_annual:,.2f}, Ins: ${breakdown.insurance_cost_annual:,.2f}, "
            f"Maint: ${breakdown.maintenance_tires_annual:,.2f}, Reg: ${breakdown.registration_fees_annual:,.2f}, "
            f"Replacement Reserve (ESTIMATED): ${breakdown.replacement_reserve_annual:,.2f}."
        ),
    )
