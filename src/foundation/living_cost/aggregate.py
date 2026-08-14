"""State and National Population-Weighted Aggregators.

Calculates P25, Median (P50), P75, weighted mean, min, and max across
all constituent localities using official adult population weights.
Never averages county values without population weights.
"""

from __future__ import annotations

from datetime import UTC, datetime

import numpy as np

from foundation.living_cost.models import (
    ComponentStatus,
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
    status: ComponentStatus = ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
) -> StateLivingCostDistribution:
    """Aggregate local county observations to state level using population weights."""
    if not localities:
        raise ValueError(f"No localities provided for state {state}")

    values = [
        loc.gross_required_income for loc in localities if loc.gross_required_income is not None
    ]
    weights = [
        float(loc.adult_population) for loc in localities if loc.gross_required_income is not None
    ]
    total_pop = sum(loc.adult_population for loc in localities)

    if not values:
        now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
        return StateLivingCostDistribution(
            state=state,
            state_name=state_name,
            reference_year=reference_year,
            profile_id="single_adult_independent",
            represented_adult_population=total_pop,
            locality_count=len(localities),
            status=ComponentStatus.UNAVAILABLE,
            weighted_p25_gross=None,
            weighted_median_gross=None,
            weighted_p75_gross=None,
            weighted_mean_gross=None,
            min_locality_gross=None,
            max_locality_gross=None,
            weighted_median_net_needs=None,
            methodology_version="0.2.0-draft",
            calculated_at=now_iso,
        )

    p25 = weighted_percentile(values, weights, 0.25)
    median = weighted_percentile(values, weights, 0.50)
    p75 = weighted_percentile(values, weights, 0.75)

    weighted_mean = float(np.average(values, weights=weights))
    min_val = min(values)
    max_val = max(values)

    net_needs_vals = [
        loc.net_needs_annual for loc in localities if loc.net_needs_annual is not None
    ]
    median_net = weighted_percentile(net_needs_vals, weights, 0.50)
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    return StateLivingCostDistribution(
        state=state,
        state_name=state_name,
        reference_year=reference_year,
        profile_id="single_adult_independent",
        represented_adult_population=total_pop,
        locality_count=len(localities),
        status=status,
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
    status: ComponentStatus = ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
) -> NationalLivingCostDistribution:
    """Aggregate all local county observations to national distribution."""
    if not all_localities:
        raise ValueError("No localities provided for national aggregation")

    values = [
        loc.gross_required_income for loc in all_localities if loc.gross_required_income is not None
    ]
    weights = [
        float(loc.adult_population)
        for loc in all_localities
        if loc.gross_required_income is not None
    ]
    total_pop = sum(loc.adult_population for loc in all_localities)

    if not values:
        now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()
        return NationalLivingCostDistribution(
            geography="United States",
            reference_year=reference_year,
            profile_id="single_adult_independent",
            represented_adult_population=total_pop,
            locality_count=len(all_localities),
            weighted_p25_gross=None,
            weighted_median_gross=None,
            weighted_p75_gross=None,
            weighted_mean_gross=None,
            lowest_state_median=None,
            highest_state_median=None,
            status=ComponentStatus.UNAVAILABLE,
            methodology_version="0.2.0-draft",
            calculated_at=now_iso,
        )

    p25 = weighted_percentile(values, weights, 0.25)
    median = weighted_percentile(values, weights, 0.50)
    p75 = weighted_percentile(values, weights, 0.75)
    weighted_mean = float(np.average(values, weights=weights))

    # Find lowest and highest valid state medians
    valid_states = [s for s in state_distributions if s.weighted_median_gross is not None]
    if valid_states:
        sorted_states = sorted(valid_states, key=lambda s: s.weighted_median_gross or 0.0)
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
    else:
        lowest = None
        highest = None

    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

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
        status=status,
        methodology_version="0.2.0-draft",
        calculated_at=now_iso,
    )
