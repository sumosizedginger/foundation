"""Resilience / Irregular expense component calculator for Minimum Sustainable Living Cost.

Rule: Explicitly models unavoidable irregular replacements and emergency reserves
without double-counting items already represented in annualized auto maintenance,
depreciation, or MEPS out-of-pocket medical baselines.
"""

from __future__ import annotations

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.living_cost.owner_freeze import canonical_resilience_reserve


def calculate_resilience_reserve(
    annual_reserve: float,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "",
    retrieved_at: str = "2026-08-13T00:00:00Z",
) -> LivingCostComponentObservation:
    """Return a validated resilience component observation."""
    if annual_reserve < 0:
        raise ValueError("Resilience reserve cannot be negative")

    # OD-012: the generic extra reserve is $0. A caller-supplied positive
    # amount is not an identified uncovered necessity and is not applied.
    applied = canonical_resilience_reserve()

    return LivingCostComponentObservation(
        component_id="resilience",
        category="resilience",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=round(applied, 2),
        value_monthly=round(applied / 12.0, 2),
        unit="USD",
        status=ComponentStatus.ESTIMATED,
        source_id=f"resilience_model_{reference_year}",
        source_variable="emergency_irregular_expense_reserve",
        source_url="https://www.federalreserve.gov/consumerscommunities/shed.htm",
        source_release="Federal Reserve SHED / BLS Baseline",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            "OD-012 FROZEN: canonical extra resilience reserve is $0. "
            f"Generic emergency/savings buffers are forbidden. "
            f"canonical_resilience_reserve={canonical_resilience_reserve():.2f}. "
            "Predictable irregular costs must be annualized inside their component."
        ),
    )
