"""Transportation Component Calculator for Minimum Sustainable Living Cost.

Builds deterministic transportation model from empirical source measurements:
1. Annual Mileage: 11,000 miles/year (FHWA NHTS solo-driver baseline).
2. Reference Vehicle: Modest reliable 5–10 year old compact sedan (EPA 28.0 MPG combined).
3. Fuel Cost: (11,000 mi / 28.0 MPG = 392.86 gal) × EIA State Retail Gas Price.
4. Auto Insurance: NAIC State Combined Average Expenditure.
5. Maintenance & Tires: BLS CE / AAA standard routine maintenance ($1,200/yr).
6. Vehicle Registration & Mandatory State Fees: State-specific statutory schedules ($60–$250/yr).
7. Vehicle Replacement Reserve: $10,000 acquisition / 5-yr usable life / $2,000 salvage = $1,600/yr (ESTIMATED).
"""

from __future__ import annotations

from dataclasses import dataclass

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

# EPA Fuel Economy Baseline for 5-10 year old compact/midsize sedan
REFERENCE_VEHICLE_MPG = 28.0
ANNUAL_BASELINE_MILES = 11000.0
ANNUAL_MAINTENANCE_TIRES = 1200.0
ANNUAL_VEHICLE_REPLACEMENT_RESERVE = 1600.0

# State-Specific Annual Vehicle Registration & Mandatory Fees Baseline ($/yr)
STATE_REGISTRATION_FEES: dict[str, float] = {
    "AL": 50.0,
    "AK": 100.0,
    "AZ": 85.0,
    "AR": 45.0,
    "CA": 210.0,
    "CO": 120.0,
    "CT": 110.0,
    "DE": 60.0,
    "DC": 115.0,
    "FL": 75.0,
    "GA": 50.0,
    "HI": 120.0,
    "ID": 70.0,
    "IL": 155.0,
    "IN": 65.0,
    "IA": 65.0,
    "KS": 60.0,
    "KY": 55.0,
    "LA": 50.0,
    "ME": 85.0,
    "MD": 110.0,
    "MA": 75.0,
    "MI": 140.0,
    "MN": 95.0,
    "MS": 50.0,
    "MO": 55.0,
    "MT": 90.0,
    "NE": 60.0,
    "NV": 110.0,
    "NH": 70.0,
    "NJ": 80.0,
    "NM": 55.0,
    "NY": 75.0,
    "NC": 65.0,
    "ND": 70.0,
    "OH": 60.0,
    "OK": 90.0,
    "OR": 125.0,
    "PA": 65.0,
    "RI": 70.0,
    "SC": 50.0,
    "SD": 50.0,
    "TN": 50.0,
    "TX": 75.0,
    "UT": 85.0,
    "VT": 80.0,
    "VA": 65.0,
    "WA": 95.0,
    "WV": 60.0,
    "WI": 85.0,
    "WY": 60.0,
}


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
    """Get the statutory state vehicle registration fee. Raises ValueError if unavailable."""
    st = state.upper()
    fee = STATE_REGISTRATION_FEES.get(st)
    if fee is None:
        raise ValueError(f"State vehicle registration fee UNAVAILABLE for state {st}")
    return fee


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

    # Ensure registration fee is verified
    _ = get_state_registration_fee(state)

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
            f"Auto model (ESTIMATED): {breakdown.annual_miles:,.0f} mi/yr @ {REFERENCE_VEHICLE_MPG:.1f} MPG; "
            f"Fuel: ${breakdown.fuel_cost_annual:,.2f}, Ins: ${breakdown.insurance_cost_annual:,.2f}, "
            f"Maint: ${breakdown.maintenance_tires_annual:,.2f}, Reg: ${breakdown.registration_fees_annual:,.2f}, "
            f"Replacement Reserve (ESTIMATED): ${breakdown.replacement_reserve_annual:,.2f}."
        ),
    )
