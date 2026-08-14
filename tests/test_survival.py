from foundation.survival import calculate_survival_floor


def test_survival_floor_rebuild_in_progress():
    result = calculate_survival_floor(population_anchor_annual=21800.0, reference_year=2024)
    assert result.status == "in_development"
    assert result.status_label == "METHODOLOGY REBUILD IN PROGRESS"
    assert result.single_adult_floor_annual == 0.0
    assert result.methodology_version == "0.2.0-draft"

    benchmarks = result.benchmark_comparisons
    assert "mit_living_wage" in benchmarks
    assert "united_way_alice" in benchmarks
    assert "official_poverty_measure" in benchmarks
