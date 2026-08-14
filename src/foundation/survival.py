from __future__ import annotations

from datetime import UTC, datetime

from foundation.config import definitions
from foundation.models import (
    BenchmarkComparison,
    HouseholdSurvivalFloor,
    SurvivalComponent,
    SurvivalFloorResult,
)


def get_survival_floor_components(reference_year: int = 2024) -> list[SurvivalComponent]:
    """Retired component model from V0.1."""
    return []


def calculate_household_survival_matrix(
    population_anchor_per_person: float = 21800.0,
) -> list[HouseholdSurvivalFloor]:
    """Retired matrix from V0.1."""
    return []


def get_benchmark_comparisons() -> dict[str, BenchmarkComparison]:
    """Sourced benchmark comparison models for validation."""
    return {
        "mit_living_wage": BenchmarkComparison(
            name="MIT Living Wage Calculator",
            author="Dr. Amy Glasmeier / Massachusetts Institute of Technology",
            url="https://livingwage.mit.edu/",
            geography="United States (Population-weighted national aggregation)",
            reference_year=2024,
            retrieved_at="2026-08-13T00:00:00Z",
            estimated_single_adult_annual=42500.0,
            methodological_divergence=(
                "MIT Living Wage includes civic engagement expenses, unsubsidized commercial healthcare premiums, "
                "and county-level cost aggregation."
            ),
        ),
        "united_way_alice": BenchmarkComparison(
            name="United For ALICE Household Survival Budget",
            author="United Way",
            url="https://www.unitedforalice.org/",
            geography="United States (County-level weighted average)",
            reference_year=2024,
            retrieved_at="2026-08-13T00:00:00Z",
            estimated_single_adult_annual=31200.0,
            methodological_divergence=(
                "ALICE includes an explicit 10% miscellaneous contingency reserve and higher technology allowances."
            ),
        ),
        "official_poverty_measure": BenchmarkComparison(
            name="Official Poverty Measure (OPM)",
            author="U.S. Census Bureau / U.S. Dept. of Health & Human Services",
            url="https://aspe.hhs.gov/poverty-guidelines",
            geography="United States (National)",
            reference_year=2024,
            retrieved_at="2026-08-13T00:00:00Z",
            estimated_single_adult_annual=15650.0,
            methodological_divergence=(
                "The OPM is based on the 1963 food-to-income multiplier (3x food) indexed by headline CPI-U."
            ),
        ),
    }


def calculate_survival_floor(
    population_anchor_annual: float = 21800.0,
    reference_year: int = 2024,
) -> SurvivalFloorResult:
    """Return the migration transition status for Axis 2.

    The original $27,960 estimate is explicitly retired. A replacement Minimum Sustainable
    Living Cost model is being built bottom-up from local county/FMR data.
    """
    defs = definitions()
    methodology_version = defs["project"]["methodology_version"]
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    return SurvivalFloorResult(
        status="in_development",
        status_label="METHODOLOGY REBUILD IN PROGRESS",
        reference_year=reference_year,
        single_adult_floor_annual=0.0,
        single_adult_floor_monthly=0.0,
        population_anchor_annual=population_anchor_annual,
        survival_gap_annual=0.0,
        adequacy_ratio=0.0,
        adequacy_percent=0,
        components=[],
        household_matrix=[],
        methodology_version=methodology_version,
        calculated_at=now_iso,
        benchmark_comparisons=get_benchmark_comparisons(),
    )
