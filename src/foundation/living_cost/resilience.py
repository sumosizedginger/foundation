"""Resilience / Irregular expense component calculator for Minimum Sustainable Living Cost.

Rule: Explicitly models unavoidable irregular replacements and emergency reserves
without double-counting items already represented in annualized auto maintenance,
depreciation, or MEPS out-of-pocket medical baselines.
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import LivingCostComponentObservation


def calculate_resilience_reserve(
    annual_reserve: float,
    reference_year: int,
    geography_id: str,
    geography_name: str = "",
    state: str = "",
    source_sha256: str = "",
) -> LivingCostComponentObservation:
    """Return a validated resilience component observation."""
    if annual_reserve < 0:
        raise ValueError("Resilience reserve cannot be negative")

    return LivingCostComponentObservation(
        component_id="resilience",
        category="resilience",
        geography_type="county",
        geography_id=geography_id,
        geography_name=geography_name,
        state=state,
        reference_year=reference_year,
        value_annual=round(annual_reserve, 2),
        value_monthly=round(annual_reserve / 12.0, 2),
        unit="USD",
        status="measured",
        source_id=f"resilience_model_{reference_year}",
        source_variable="emergency_irregular_expense_reserve",
        source_url="https://www.federalreserve.gov/consumerscommunities/shed.htm",
        source_release="Federal Reserve SHED / BLS Baseline",
        source_reference_period=str(reference_year),
        retrieved_at="",
        source_artifact_sha256=source_sha256,
        methodology_version="0.2.0-draft",
        notes="Unavoidable emergency irregular expense buffer (minor household replacements, unexpected non-auto emergencies).",
    )
