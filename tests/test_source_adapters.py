from __future__ import annotations

from pathlib import Path

import pytest

from foundation.living_cost.geo_join import execute_geo_join_audit
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.living_cost.validation import validate_component_provenance
from foundation.sources.auto_insurance import parse_naic_auto_insurance_csv
from foundation.sources.bea_rpp import parse_bea_rpp_csv
from foundation.sources.bls_ce import parse_bls_ce_microdata_csv
from foundation.sources.census_acs import (
    generate_census_county_universe_report,
    parse_acs_county_population_csv,
)
from foundation.sources.cms_marketplace import parse_cms_marketplace_rates_csv
from foundation.sources.eia import parse_eia_gas_prices_csv
from foundation.sources.fhwa_nhts import parse_fhwa_nhts_mileage_csv
from foundation.sources.hud_fmr import parse_hud_fmr_csv
from foundation.sources.meps import parse_meps_oop_csv
from foundation.sources.usda_food import parse_usda_monthly_food_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_census_acs_b01001_adult_derivation():
    """Prove that adult population is deterministically computed and != total population."""
    acs_fixture = FIXTURES / "sample_acs_county_pop.csv"
    pop_map = parse_acs_county_population_csv(acs_fixture, reference_year=2024)
    assert len(pop_map) >= 5

    # Check Harris County TX (FIPS 48201)
    harris = pop_map.get("48201")
    assert harris is not None
    assert harris["adult_population"] == 3550000
    assert harris["total_population"] == 4780000
    assert harris["adult_population"] != harris["total_population"]  # PROOF: adult != total
    assert harris["under18_population"] == 1230000
    assert harris["fips"] == "48201"
    assert harris["sha256"] != ""


def test_census_acs_missing_adult_variables_fails_closed(tmp_path: Path):
    """Prove that missing adult population variables fail closed and NEVER substitute total population."""
    bad_csv = tmp_path / "bad_acs.csv"
    bad_csv.write_text(
        "GEOID,NAME,total_population\n01001,Autauga County,59000\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="Cannot derive adult population"):
        parse_acs_county_population_csv(bad_csv, reference_year=2024)


def test_census_county_universe_generation(tmp_path: Path):
    """Verify machine-generated Census County Universe report."""
    acs_fixture = FIXTURES / "sample_acs_county_pop.csv"
    pop_map = parse_acs_county_population_csv(acs_fixture, reference_year=2024)

    out_file = tmp_path / "census_county_universe.json"
    rep = generate_census_county_universe_report(pop_map, out_file)

    assert rep["report_type"] == "census_county_geography_universe"
    assert rep["total_county_count"] == len(pop_map)
    assert "72" in rep["excluded_territories"]  # Puerto Rico excluded
    assert out_file.exists()


def test_hud_fmr_parsing_and_multi_county_handling():
    """Verify HUD FMR parsing, 1BR rent, and multi-county FMR area retention."""
    hud_fixture = FIXTURES / "sample_hud_fmr_2024.csv"
    obs_list = parse_hud_fmr_csv(hud_fixture, reference_year=2024)
    assert len(obs_list) >= 5

    # Check San Francisco observation (FIPS 06075)
    sf_obs = next(o for o in obs_list if o.geography_id == "06075")
    assert sf_obs.value_monthly == 2490.00
    assert sf_obs.value_annual == 29880.00
    assert sf_obs.status == ComponentStatus.MEASURED
    assert sf_obs.source_id == "hud_fmr_2024"
    assert sf_obs.source_artifact_sha256 != ""


def test_hud_acs_geo_join_execution(tmp_path: Path):
    """Execute real HUD ↔ ACS join audit and verify match metrics."""
    acs_fixture = FIXTURES / "sample_acs_county_pop.csv"
    hud_fixture = FIXTURES / "sample_hud_fmr_2024.csv"

    pop_map = parse_acs_county_population_csv(acs_fixture, reference_year=2024)
    hud_obs = parse_hud_fmr_csv(hud_fixture, reference_year=2024)

    out_file = tmp_path / "living_cost_geo_join_2024.json"
    join_rep = execute_geo_join_audit(pop_map, hud_obs, reference_year=2024, output_path=out_file)

    assert join_rep["report_type"] == "hud_fmr_census_acs_geo_join"
    assert join_rep["matched_counties_count"] == len(pop_map)
    assert join_rep["unmatched_census_counties_count"] == 0
    assert join_rep["county_coverage_percentage"] == 100.0
    assert join_rep["population_coverage_percentage"] == 100.0
    assert out_file.exists()


def test_cms_marketplace_lowest_cost_adequate_silver_selection():
    """Verify lowest-cost adequate Silver plan selection with deductible tie-breaking."""
    cms_fixture = FIXTURES / "sample_cms_rates.csv"
    obs_list = parse_cms_marketplace_rates_csv(cms_fixture, reference_year=2024)
    assert len(obs_list) >= 5

    # Check CA rating area
    ca_obs = next(o for o in obs_list if o.state == "CA")
    assert ca_obs.value_monthly == 490.00
    assert ca_obs.value_annual == 5880.00
    assert ca_obs.status == ComponentStatus.MEASURED
    assert "Lowest-Cost Adequate Silver Plan" in ca_obs.notes


def test_meps_privately_insured_adult_oop_fail_closed(tmp_path: Path):
    """Verify MEPS out-of-pocket healthcare parsing and fail-closed UNAVAILABLE behavior."""
    # Test valid MEPS CSV
    meps_csv = tmp_path / "sample_meps.csv"
    meps_csv.write_text(
        "age_group,insurance_status,mean_oop_expenditure,sample_count,represented_population\n"
        "Adults 18-64,Privately Insured,1420.00,12500,165000000\n",
        encoding="utf-8",
    )
    obs = parse_meps_oop_csv(meps_csv, reference_year=2024)
    assert obs.status == ComponentStatus.MEASURED
    assert obs.value_annual == 1420.00
    assert obs.value_monthly == round(1420.00 / 12.0, 2)

    # Test empty/unmatched MEPS file -> FAIL CLOSED (Status UNAVAILABLE, NO NUMERIC FALLBACK)
    bad_meps = tmp_path / "bad_meps.csv"
    bad_meps.write_text(
        "age_group,insurance_status,mean_oop_expenditure\nElderly 65+,Medicare,3500.00\n",
        encoding="utf-8",
    )
    unavail_obs = parse_meps_oop_csv(bad_meps, reference_year=2024)
    assert unavail_obs.status == ComponentStatus.UNAVAILABLE
    assert unavail_obs.value_annual is None
    assert unavail_obs.value_monthly is None


def test_usda_food_plans_monthly_aggregation():
    """Verify USDA food plan midpoint, +20% 1-person multiplier, and period labeling."""
    usda_fixture = FIXTURES / "sample_usda_food.csv"
    obs_list = parse_usda_monthly_food_csv(usda_fixture, reference_year=2024)
    assert len(obs_list) == 2  # Low-Cost and Thrifty

    low_cost = next(o for o in obs_list if o.component_id == "food_low_cost")
    # Male: 345.20, Female: 298.10 -> Midpoint: 321.65 * 1.20 = 385.98
    assert low_cost.value_monthly == 385.98
    assert low_cost.value_annual == round(385.98 * 12.0, 2)
    assert low_cost.status == ComponentStatus.MEASURED


def test_fhwa_nhts_mileage_parsing(tmp_path: Path):
    """Verify FHWA NHTS solo-driver mileage benchmark parsing."""
    nhts_csv = tmp_path / "sample_nhts.csv"
    nhts_csv.write_text(
        "driver_type,annual_vmt,sample_count\nsingle_driver_worker,11000,8500\n", encoding="utf-8"
    )
    obs = parse_fhwa_nhts_mileage_csv(nhts_csv, reference_year=2024)
    assert obs.status == ComponentStatus.MEASURED
    assert obs.value_annual == 11000.0


def test_eia_gas_price_measured_output(tmp_path: Path):
    """Verify EIA gas price connector outputs measured price_per_gallon only."""
    eia_csv = tmp_path / "sample_eia.csv"
    eia_csv.write_text("state,regular_gas_price\nCA,4.850\nTX,3.050\n", encoding="utf-8")
    obs_list = parse_eia_gas_prices_csv(eia_csv, reference_year=2024)
    assert len(obs_list) == 2

    ca_gas = next(o for o in obs_list if o.geography_id == "CA")
    assert ca_gas.value_annual == 4.850
    assert ca_gas.unit == "USD_PER_GALLON"
    assert ca_gas.status == ComponentStatus.MEASURED


def test_auto_insurance_combined_expenditure(tmp_path: Path):
    """Verify NAIC auto insurance parser records combined expenditure and source vintage."""
    naic_csv = tmp_path / "sample_naic.csv"
    naic_csv.write_text(
        "state,combined_expenditure,source_year\nCA,2180.00,2022\nTX,2180.00,2022\n",
        encoding="utf-8",
    )
    obs_list = parse_naic_auto_insurance_csv(naic_csv, reference_year=2024)
    assert len(obs_list) == 2

    ca_ins = next(o for o in obs_list if o.geography_id == "CA")
    assert ca_ins.value_annual == 2180.00
    assert ca_ins.source_reference_period == "2022"
    assert ca_ins.status == ComponentStatus.MEASURED


def test_bls_ce_weighted_p25_calculation(tmp_path: Path):
    """Verify BLS CE single-person consumer unit weighted P25 calculation."""
    ce_csv = tmp_path / "sample_ce.csv"
    ce_csv.write_text(
        "FAM_SIZE,FINLWT21,essentials_expenditure,recreation_expenditure\n"
        "1,100,1200,1000\n"
        "1,100,2400,2000\n"
        "1,100,3600,3000\n"
        "1,100,4800,4000\n"
        "2,100,9999,9999\n",  # Family size 2 excluded
        encoding="utf-8",
    )
    obs_list = parse_bls_ce_microdata_csv(ce_csv, reference_year=2024)
    assert len(obs_list) == 2

    ess = next(o for o in obs_list if o.component_id == "essentials_basket")
    assert ess.status == ComponentStatus.MEASURED
    assert ess.value_annual is not None
    assert ess.value_annual > 0


def test_bea_rpp_factors(tmp_path: Path):
    """Verify BEA Regional Price Parities parsing into decimal multipliers."""
    rpp_csv = tmp_path / "sample_rpp.csv"
    rpp_csv.write_text("state,rpp_all_items\nCA,112.5\nMS,85.5\n", encoding="utf-8")
    rpp_map = parse_bea_rpp_csv(rpp_csv, reference_year=2024)
    assert rpp_map["CA"] == 1.125
    assert rpp_map["MS"] == 0.855


def test_provenance_validator_strict_gates():
    """Verify that provenance validator strictly enforces 64-char hex SHA, ISO-8601, and valid URLs."""
    valid_obs = LivingCostComponentObservation(
        component_id="housing_1br",
        category="housing",
        geography_type="county",
        geography_id="06075",
        geography_name="San Francisco County, CA",
        state="CA",
        reference_year=2024,
        value_annual=29880.0,
        value_monthly=2490.0,
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id="hud_fmr_2024",
        source_variable="fmr_1",
        source_url="https://www.huduser.gov/portal/datasets/fmr.html",
        source_release="HUD FY 2024 Fair Market Rents",
        source_reference_period="2024",
        retrieved_at="2026-08-13T00:00:00Z",
        source_artifact_sha256="4b7b26e0e374596b6d51c14b62f928f8045958be2387114b304c4058d8393e87",
        methodology_version="0.2.0-draft",
        notes="Validated observation.",
    )
    errors = validate_component_provenance(valid_obs)
    assert len(errors) == 0

    # Test invalid SHA-256 (not 64 hex chars)
    invalid_sha_obs = LivingCostComponentObservation(
        component_id="housing_1br",
        category="housing",
        geography_type="county",
        geography_id="06075",
        geography_name="San Francisco County, CA",
        state="CA",
        reference_year=2024,
        value_annual=29880.0,
        value_monthly=2490.0,
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id="hud_fmr_2024",
        source_variable="fmr_1",
        source_url="https://www.huduser.gov/portal/datasets/fmr.html",
        source_release="HUD FY 2024 Fair Market Rents",
        source_reference_period="2024",
        retrieved_at="2026-08-13T00:00:00Z",
        source_artifact_sha256="not_a_valid_64_char_sha",
        methodology_version="0.2.0-draft",
        notes="Invalid SHA observation.",
    )
    errors_sha = validate_component_provenance(invalid_sha_obs)
    assert any("must be 64 hex characters" in e for e in errors_sha)
