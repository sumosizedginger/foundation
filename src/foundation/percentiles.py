from __future__ import annotations

import numpy as np
import pandas as pd


class PercentileInputError(ValueError):
    """Raised when weighted percentile inputs are unusable."""


def weighted_percentile(
    values: pd.Series | np.ndarray | list[float],
    weights: pd.Series | np.ndarray | list[float],
    percentile: float,
) -> float:
    """Return the first value whose cumulative positive weight reaches percentile.

    This is the weighted inverse empirical CDF convention documented in METHODOLOGY.md.
    """
    if not 0 <= percentile <= 1:
        raise PercentileInputError("percentile must be between 0 and 1 inclusive")

    value_arr = np.asarray(values, dtype=float)
    weight_arr = np.asarray(weights, dtype=float)

    if value_arr.shape != weight_arr.shape:
        raise PercentileInputError("values and weights must have the same shape")
    if value_arr.ndim != 1:
        raise PercentileInputError("values and weights must be one-dimensional")

    mask = np.isfinite(value_arr) & np.isfinite(weight_arr) & (weight_arr > 0)
    value_arr = value_arr[mask]
    weight_arr = weight_arr[mask]

    if value_arr.size == 0:
        raise PercentileInputError("no valid positive-weight observations")

    order = np.argsort(value_arr, kind="mergesort")
    sorted_values = value_arr[order]
    sorted_weights = weight_arr[order]

    total_weight = sorted_weights.sum()
    if not np.isfinite(total_weight) or total_weight <= 0:
        raise PercentileInputError("total weight must be finite and positive")

    if percentile == 0:
        return float(sorted_values[0])

    target = total_weight * percentile
    cumulative = np.cumsum(sorted_weights)
    index = int(np.searchsorted(cumulative, target, side="left"))
    index = min(index, len(sorted_values) - 1)
    return float(sorted_values[index])


def weighted_percentiles(
    values: pd.Series | np.ndarray | list[float],
    weights: pd.Series | np.ndarray | list[float],
    percentiles: list[float],
) -> dict[float, float]:
    return {p: weighted_percentile(values, weights, p) for p in percentiles}
