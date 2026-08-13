import pytest

from foundation.independent_check import weighted_percentile_reference
from foundation.percentiles import PercentileInputError, weighted_percentile


def test_weighted_percentile_equal_weights():
    values = [10, 20, 30, 40, 50]
    weights = [1, 1, 1, 1, 1]

    assert weighted_percentile(values, weights, 0.30) == 20


def test_weighted_percentile_respects_weights():
    values = [10, 20, 30]
    weights = [1, 8, 1]

    assert weighted_percentile(values, weights, 0.30) == 20


def test_boundary_uses_first_cumulative_weight_greater_or_equal():
    values = [10, 20, 30, 40]
    weights = [3, 3, 2, 2]
    # Target at 30% is exactly 3. First cumulative >= 3 is value 10.
    assert weighted_percentile(values, weights, 0.30) == 10


def test_zero_percentile_is_minimum():
    assert weighted_percentile([5, 10], [1, 1], 0) == 5


def test_invalid_percentile():
    with pytest.raises(PercentileInputError):
        weighted_percentile([1], [1], 1.1)


def test_nonpositive_weights_are_ignored():
    assert weighted_percentile([1, 2, 3], [0, -2, 1], 0.30) == 3


@pytest.mark.parametrize(
    "values,weights,p",
    [
        ([10, 20, 30, 40], [1, 1, 1, 1], 0.30),
        ([-50, 0, 10, 100], [2, 4, 1, 3], 0.30),
        ([1, 1, 2, 3], [1, 3, 2, 4], 0.50),
        ([100, 10, 50], [100, 1, 1], 0.30),
    ],
)
def test_primary_matches_independent_reference(values, weights, p):
    assert weighted_percentile(values, weights, p) == weighted_percentile_reference(
        values, weights, p
    )
