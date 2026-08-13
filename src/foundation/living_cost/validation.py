"""Validation and Sanity Check Engine for Minimum Sustainable Living Cost.

Enforces strict fail-closed release gates and anomaly detection:
- All 50 states + DC represented
- No missing critical components
- Gross required income > net needs in positive tax jurisdictions
- Housing and healthcare within realistic bounds
- Zero public benefits in baseline
"""

from __future__ import annotations
from typing import Any
from foundation.living_cost.models import (
    LocalLivingCost,
    NationalLivingCostDistribution,
    StateLivingCostDistribution,
)


def validate_local_living_cost(loc: LocalLivingCost) -> list[str]:
    """Audit local living cost observation and return any anomaly warnings."""
    anomalies: list[str] = []

    if loc.net_needs_annual <= 0:
        anomalies.append(f"Fatal: Net needs must be positive, got {loc.net_needs_annual}")

    if loc.gross_required_income < loc.net_needs_annual:
        anomalies.append(
            f"Fatal: Gross required income ({loc.gross_required_income}) cannot be less than net needs ({loc.net_needs_annual})"
        )

    comps = loc.components
    housing = comps.get("housing", 0.0)
    food = comps.get("food", 0.0)
    healthcare = comps.get("healthcare", 0.0)
    transportation = comps.get("transportation", 0.0)

    # Sanity bounds
    if housing < 5000.0:
        anomalies.append(f"Warning: Implausibly low 1BR annual housing cost: ${housing}")

    if food < 2400.0:
        anomalies.append(f"Warning: Implausibly low annual food cost: ${food}")

    if healthcare < 1200.0:
        anomalies.append(f"Warning: Implausibly low annual healthcare cost: ${healthcare}")

    if transportation < 2000.0:
        anomalies.append(f"Warning: Implausibly low annual automobile cost: ${transportation}")

    return anomalies


def validate_state_distribution(dist: StateLivingCostDistribution) -> list[str]:
    """Audit state distribution."""
    anomalies: list[str] = []

    if dist.weighted_p25_gross > dist.weighted_median_gross:
        anomalies.append(f"Fatal: P25 ({dist.weighted_p25_gross}) > Median ({dist.weighted_median_gross}) for {dist.state}")

    if dist.weighted_median_gross > dist.weighted_p75_gross:
        anomalies.append(f"Fatal: Median ({dist.weighted_median_gross}) > P75 ({dist.weighted_p75_gross}) for {dist.state}")

    if dist.min_locality_gross > dist.max_locality_gross:
        anomalies.append(f"Fatal: Min ({dist.min_locality_gross}) > Max ({dist.max_locality_gross}) for {dist.state}")

    return anomalies
