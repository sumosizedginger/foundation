from foundation.living_cost.aggregate import (
    aggregate_national_living_cost,
    aggregate_state_living_cost,
)
from foundation.living_cost.essentials import calculate_connectivity_and_essentials
from foundation.living_cost.food import calculate_food_baseline
from foundation.living_cost.healthcare import calculate_healthcare
from foundation.living_cost.housing import calculate_local_housing
from foundation.living_cost.local import compute_local_living_cost
from foundation.living_cost.recreation import calculate_social_recreation
from foundation.living_cost.resilience import calculate_resilience_reserve
from foundation.living_cost.taxes import (
    calculate_federal_income_tax,
    calculate_fica_taxes,
)
from foundation.living_cost.transportation import AutoCostBreakdown, calculate_transportation
from foundation.living_cost.validation import (
    validate_local_living_cost,
    validate_state_distribution,
)


def test_housing_calculation():
    obs = calculate_local_housing("06075", 28680.0, 2024, "San Francisco County, CA", "CA")
    assert obs.value_annual == 28680.0
    assert obs.value_monthly == 2390.0
    assert obs.category == "housing"
    assert obs.methodology_version == "0.2.0-draft"


def test_food_calculation():
    obs = calculate_food_baseline(2024, 386.00, "low_cost")
    assert obs.value_annual == 4632.00
    assert obs.value_monthly == 386.00
    assert obs.category == "food"


def test_transportation_model():
    breakdown = AutoCostBreakdown(
        annual_miles=11000.0,
        fuel_cost_annual=1800.0,
        insurance_cost_annual=2200.0,
        maintenance_tires_annual=1400.0,
        registration_fees_annual=300.0,
        replacement_reserve_annual=2500.0,
    )
    assert breakdown.total_annual == 8200.0
    obs = calculate_transportation(breakdown, 2024, "06075", "San Francisco County, CA", "CA")
    assert obs.value_annual == 8200.0


def test_healthcare_unsubsidized_silver():
    obs = calculate_healthcare(5400.0, 1600.0, 2024, "06075", "San Francisco County, CA", "CA")
    assert obs.value_annual == 7000.0
    assert obs.value_monthly == 583.33


def test_connectivity_and_essentials():
    conn, ess = calculate_connectivity_and_essentials(1440.0, 2400.0, 2024, "06075")
    assert conn.value_annual == 1440.0
    assert ess.value_annual == 2400.0


def test_social_recreation_rpp():
    obs = calculate_social_recreation(2400.0, 1.15, 2024, "06075", "San Francisco County, CA", "CA")
    assert obs.value_annual == 2760.0


def test_resilience_reserve():
    obs = calculate_resilience_reserve(1200.0, 2024, "06075", "San Francisco County, CA", "CA")
    assert obs.value_annual == 0.0


def test_federal_tax_brackets_boundary_tests():
    # 2024 boundary tests
    assert calculate_federal_income_tax(0.0, year=2024) == 0.0
    assert calculate_federal_income_tax(14600.0, year=2024) == 0.0  # Exactly std deduction
    assert calculate_federal_income_tax(14601.0, year=2024) == 0.10  # $1 taxable at 10%
    # First bracket boundary: $14,600 + $11,600 = $26,200
    assert round(calculate_federal_income_tax(26200.0, year=2024), 2) == 1160.00
    assert (
        round(calculate_federal_income_tax(26201.0, year=2024), 2) == 1160.12
    )  # $1 into 12% bracket

    # 2024 FICA SSA Wage Cap: $168,600
    ss_below, med_below = calculate_fica_taxes(168600.0, year=2024)
    ss_above, med_above = calculate_fica_taxes(200000.0, year=2024)
    assert round(ss_below, 2) == round(168600.0 * 0.062, 2)
    assert round(ss_above, 2) == round(168600.0 * 0.062, 2)  # SS capped at $168,600
    assert med_above > med_below  # Medicare uncapped

    # 2026 boundary tests (IRS Rev. Proc. 2025-32 & SSA 2026 Baseline)
    assert calculate_federal_income_tax(0.0, year=2026) == 0.0
    assert calculate_federal_income_tax(16100.0, year=2026) == 0.0  # Exactly 2026 std deduction
    assert calculate_federal_income_tax(16101.0, year=2026) == 0.10  # $1 taxable at 10%
    # First bracket boundary: $16,100 + $12,400 = $28,500
    assert round(calculate_federal_income_tax(28500.0, year=2026), 2) == 1240.00
    assert round(calculate_federal_income_tax(28501.0, year=2026), 2) == 1240.12

    # 2026 FICA SSA Wage Cap: $184,500
    ss_2026_cap, _ = calculate_fica_taxes(184500.0, year=2026)
    ss_2026_above, _ = calculate_fica_taxes(250000.0, year=2026)
    assert round(ss_2026_cap, 2) == round(184500.0 * 0.062, 2)
    assert round(ss_2026_above, 2) == round(184500.0 * 0.062, 2)  # SS capped at $184,500


def test_local_living_cost_and_aggregation():
    loc1 = compute_local_living_cost(
        geography_id="24005",
        geography_name="Baltimore County, MD",
        state="MD",
        reference_year=2024,
        adult_population=700000,
        housing_annual=28000.0,
        food_annual=4800.0,
        transportation_annual=8000.0,
        healthcare_annual=7000.0,
        connectivity_annual=1440.0,
        essentials_annual=2400.0,
        social_recreation_annual=2800.0,
        resilience_annual=1200.0,
    )
    loc2 = compute_local_living_cost(
        geography_id="24003",
        geography_name="Anne Arundel County, MD",
        state="MD",
        reference_year=2024,
        adult_population=800000,
        housing_annual=14000.0,
        food_annual=4800.0,
        transportation_annual=8000.0,
        healthcare_annual=6500.0,
        connectivity_annual=1440.0,
        essentials_annual=2400.0,
        social_recreation_annual=2200.0,
        resilience_annual=1200.0,
    )

    anomalies1 = validate_local_living_cost(loc1)
    assert len(anomalies1) == 0

    state_dist = aggregate_state_living_cost("MD", "Maryland", [loc1, loc2], reference_year=2024)
    assert state_dist.locality_count == 2
    assert state_dist.represented_adult_population == 1500000
    assert (
        state_dist.weighted_p25_gross
        <= state_dist.weighted_median_gross
        <= state_dist.weighted_p75_gross
    )

    state_anomalies = validate_state_distribution(state_dist)
    assert len(state_anomalies) == 0

    nat_dist = aggregate_national_living_cost([loc1, loc2], [state_dist], reference_year=2024)
    assert nat_dist.locality_count == 2
    assert nat_dist.lowest_state_median["state"] == "MD"
