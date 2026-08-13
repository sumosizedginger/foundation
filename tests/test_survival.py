import pytest
from foundation.survival import (
    calculate_household_survival_matrix,
    calculate_survival_floor,
    get_benchmark_comparisons,
    get_survival_floor_components,
)


def test_survival_floor_components_single_adult():
    comps = get_survival_floor_components(2024)
    total_annual = sum(c.annual_cost for c in comps)
    assert total_annual == 27960.0
    assert len(comps) == 6

    # Verify key categories exist
    categories = {c.category for c in comps}
    assert "housing" in categories
    assert "food" in categories
    assert "utilities_tech" in categories
    assert "transportation" in categories
    assert "healthcare" in categories
    assert "taxes_unavoidables" in categories


def test_household_survival_matrix_independent_modeling():
    # Matrix must NOT be a simple multiple of the single-adult floor
    matrix = calculate_household_survival_matrix(population_anchor_per_person=21800.0)
    assert len(matrix) == 5

    single_floor = matrix[0].survival_floor_annual
    assert single_floor == 27960.0

    # Test size 2 is NOT 2 * single_floor
    assert matrix[1].survival_floor_annual != 2 * single_floor
    assert matrix[1].survival_floor_annual == 39800.0

    # Test size 4 is NOT 4 * single_floor
    assert matrix[3].survival_floor_annual != 4 * single_floor
    assert matrix[3].survival_floor_annual == 68300.0

    # Verify survival gap and adequacy ratio math
    # Size 1: 21800 - 27960 = -6160
    assert matrix[0].survival_gap_annual == -6160.0
    assert round(matrix[0].adequacy_ratio, 2) == 0.78

    # Size 4: 87200 - 68300 = +18900
    assert matrix[3].survival_gap_annual == 18900.0
    assert round(matrix[3].adequacy_ratio, 2) == 1.28


def test_survival_floor_result_object():
    result = calculate_survival_floor(population_anchor_annual=21800.0, reference_year=2024)
    assert result.status == "research_estimate"
    assert result.single_adult_floor_annual == 27960.0
    assert result.survival_gap_annual == -6160.0
    assert round(result.adequacy_ratio, 2) == 0.78

    benchmarks = result.benchmark_comparisons
    assert "mit_living_wage" in benchmarks
    assert "united_way_alice" in benchmarks
    assert "official_poverty_measure" in benchmarks
