from pathlib import Path
import pytest

from foundation.living_cost.models import ComponentStatus
from foundation.sources.hud_fmr import parse_hud_fmr_csv
from foundation.sources.census_acs import parse_acs_county_population_csv
from foundation.sources.cms_marketplace import parse_cms_marketplace_rates_csv
from foundation.sources.usda_food import parse_usda_food_plan_csv
from foundation.living_cost.validation import validate_component_provenance

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_hud_fmr_parsing():
    hud_fixture = FIXTURES / "sample_hud_fmr_2024.csv"
    obs_list = parse_hud_fmr_csv(hud_fixture, reference_year=2024)
    assert len(obs_list) >= 5

    # Check San Francisco observation
    sf_obs = next(o for o in obs_list if o.geography_id == "06075")
    assert sf_obs.value_monthly == 2490.00
    assert sf_obs.value_annual == 29880.00
    assert sf_obs.status == ComponentStatus.MEASURED
    assert sf_obs.source_id == "hud_fmr_2024"
    assert sf_obs.source_artifact_sha256 != ""

    # Validate provenance gate
    errors = validate_component_provenance(sf_obs)
    assert len(errors) == 0


def test_census_acs_population_parsing():
    acs_fixture = FIXTURES / "sample_acs_county_pop.csv"
    pop_map = parse_acs_county_population_csv(acs_fixture, reference_year=2024)
    assert len(pop_map) >= 5

    # Check Harris County TX
    harris = pop_map.get("48201")
    assert harris is not None
    assert harris["adult_population"] == 3550000
    assert harris["fips"] == "48201"
    assert harris["sha256"] != ""


def test_cms_marketplace_parsing():
    cms_fixture = FIXTURES / "sample_cms_rates.csv"
    obs_list = parse_cms_marketplace_rates_csv(cms_fixture, reference_year=2024)
    assert len(obs_list) >= 5

    # Check CA rating area 4
    ca_obs = next(o for o in obs_list if o.state == "CA")
    assert ca_obs.value_monthly == 490.00
    assert ca_obs.value_annual == 5880.00
    assert ca_obs.status == ComponentStatus.MEASURED

    errors = validate_component_provenance(ca_obs)
    assert len(errors) == 0


def test_usda_food_plan_parsing():
    usda_fixture = FIXTURES / "sample_usda_food.csv"
    obs_list = parse_usda_food_plan_csv(usda_fixture, reference_year=2024)
    assert len(obs_list) == 2  # Low-Cost and Thrifty

    low_cost = next(o for o in obs_list if o.component_id == "food_low_cost")
    # (345.20 + 298.10) / 2 = 321.65 * 1.20 = 385.98 -> 386.00
    assert low_cost.value_monthly == 385.98
    assert low_cost.status == ComponentStatus.MEASURED

    errors = validate_component_provenance(low_cost)
    assert len(errors) == 0
