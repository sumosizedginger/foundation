"""State and National Population-Weighted Aggregators.

Calculates P25, Median (P50), P75, weighted mean, min, and max across
all constituent localities using official adult population weights.
Never averages county values without population weights.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
import numpy as np

from foundation.living_cost.models import (
    LocalLivingCost,
    NationalLivingCostDistribution,
    StateLivingCostDistribution,
)
from foundation.percentiles import weighted_percentile


def aggregate_state_living_cost(
    state: str,
    state_name: str,
    localities: list[LocalLivingCost],
    reference_year: int,
) -> StateLivingCostDistribution:
    """Aggregate local county observations to state level using population weights."""
    if not localities:
        raise ValueError(f"No localities provided for state {state}")

    values = [loc.gross_required_income for loc in localities]
    weights = [float(loc.adult_population) for loc in localities]
    total_pop = sum(loc.adult_population for loc in localities)

    p25 = weighted_percentile(values, weights, 0.25)
    median = weighted_percentile(values, weights, 0.50)
    p75 = weighted_percentile(values, weights, 0.75)

    weighted_mean = float(np.average(values, weights=weights))
    min_val = min(values)
    max_val = max(values)

    net_needs_vals = [loc.net_needs_annual for loc in localities]
    median_net = weighted_percentile(net_needs_vals, weights, 0.50)
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    return StateLivingCostDistribution(
        state=state,
        state_name=state_name,
        reference_year=reference_year,
        profile_id="single_adult_independent",
        represented_adult_population=total_pop,
        locality_count=len(localities),
        weighted_p25_gross=p25,
        weighted_median_gross=median,
        weighted_p75_gross=p75,
        weighted_mean_gross=round(weighted_mean, 2),
        min_locality_gross=min_val,
        max_locality_gross=max_val,
        weighted_median_net_needs=median_net,
        methodology_version="0.2.0-draft",
        calculated_at=now_iso,
    )


def aggregate_national_living_cost(
    all_localities: list[LocalLivingCost],
    state_distributions: list[StateLivingCostDistribution],
    reference_year: int,
) -> NationalLivingCostDistribution:
    """Aggregate all local county observations to national distribution."""
    if not all_localities:
        raise ValueError("No localities provided for national aggregation")

    values = [loc.gross_required_income for loc in all_localities]
    weights = [float(loc.adult_population) for loc in all_localities]
    total_pop = sum(loc.adult_population for loc in all_localities)

    p25 = weighted_percentile(values, weights, 0.25)
    median = weighted_percentile(values, weights, 0.50)
    p75 = weighted_percentile(values, weights, 0.75)
    weighted_mean = float(np.average(values, weights=weights))

    # Find lowest and highest state medians
    sorted_states = sorted(state_distributions, key=lambda s: s.weighted_median_gross)
    lowest = {
        "state": sorted_states[0].state,
        "state_name": sorted_states[0].state_name,
        "median_gross": sorted_states[0].weighted_median_gross,
    }
    highest = {
        "state": sorted_states[-1].state,
        "state_name": sorted_states[-1].state_name,
        "median_gross": sorted_states[-1].weighted_median_gross,
    }
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    return NationalLivingCostDistribution(
        geography="United States",
        reference_year=reference_year,
        profile_id="single_adult_independent",
        represented_adult_population=total_pop,
        locality_count=len(all_localities),
        weighted_p25_gross=p25,
        weighted_median_gross=median,
        weighted_p75_gross=p75,
        weighted_mean_gross=round(weighted_mean, 2),
        lowest_state_median=lowest,
        highest_state_median=highest,
        status="research_estimate",
        methodology_version="0.2.0-draft",
        calculated_at=now_iso,
    )
