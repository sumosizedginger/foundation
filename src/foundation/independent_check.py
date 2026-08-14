from __future__ import annotations

from collections.abc import Iterable


def weighted_percentile_reference(
    values: Iterable[float],
    weights: Iterable[float],
    percentile: float,
) -> float:
    """Small independent implementation used as a cross-check in tests.

    Intentionally avoids NumPy/pandas percentile helpers.
    """
    if not 0 <= percentile <= 1:
        raise ValueError("percentile must be between 0 and 1")

    pairs = []
    for value, weight in zip(values, weights, strict=True):
        value = float(value)
        weight = float(weight)
        if weight > 0:
            pairs.append((value, weight))

    if not pairs:
        raise ValueError("no positive-weight records")

    pairs.sort(key=lambda pair: pair[0])
    total = sum(weight for _, weight in pairs)
    target = total * percentile

    if percentile == 0:
        return pairs[0][0]

    running = 0.0
    for value, weight in pairs:
        running += weight
        if running >= target:
            return value

    return pairs[-1][0]
