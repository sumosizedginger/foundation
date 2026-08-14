from __future__ import annotations

import json
from pathlib import Path

import openpyxl
import pytest

from foundation.living_cost.geo_join import execute_geo_join_audit
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.living_cost.validation import validate_component_provenance
from foundation.sources.auto_insurance import parse_naic_auto_insurance_csv
from foundation.sources.bea_rpp import parse_bea_rpp_csv
from foundation.sources.bls_ce import parse_bls_ce_microdata
from foundation.sources.census_acs import (
    compute_adult_population_from_b01001_row,
    generate_census_county_universe_report,
    parse_acs_county_population_json,
    parse_acs_summary_dat,
)
from foundation.sources.cms_marketplace import CMS_PUF_URLS
from foundation.sources.eia import parse_eia_gas_prices_csv
from foundation.sources.fhwa_nhts import parse_fhwa_nhts_mileage
from foundation.sources.hud_fmr import HUD_FMR_SOURCES, parse_hud_fmr_xlsx
from foundation.sources.meps import parse_meps_oop_csv
from foundation.sources.usda_food import parse_usda_monthly_food_csv

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _write_acs_json(path: Path) -> None:
    headers = [
        "NAME",
        "B01001_001E",
        "B01001_003E",
        "B01001_004E",
        "B01001_005E",
        "B01001_006E",
        "B01001_027E",
        "B01001_028E",
        "B01001_029E",
        "B01001_030E",
        "state",
        "county",
    ]
    # Harris County TX: total 4,780,000; under-18 1,230,000; adult 3,550,000
    harris = [
        "Harris County, Texas",
        "4780000",
        "153750",
        "153750",
        "153750",
        "153750",
        "153750",
        "153750",
        "153750",
        "153750",
        "48",
        "201",
    ]
    sf = [
        "San Francisco County, California",
        "810000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "10000",
        "06",
        "075",
    ]
    path.write_text(json.dumps([headers, harris, sf]), encoding="utf-8")


def _xlsx_from_hud_csv(csv_path: Path, dest: Path) -> Path:
    wb = openpyxl.Workbook()
    sheet = wb.active
    assert sheet is not None
    with csv_path.open(encoding="utf-8") as fh:
        for row_idx, line in enumerate(fh, start=1):
            for col_idx, cell in enumerate(line.strip().split(","), start=1):
                sheet.cell(row_idx, col_idx, cell)
    wb.save(dest)
    return dest


def test_census_acs_b01001_adult_derivation(tmp_path: Path):
    acs_json = tmp_path / "acs.json"
    _write_acs_json(acs_json)
    pop_map = parse_acs_county_population_json(acs_json, reference_year=2024)
    harris = pop_map["48201"]
    assert harris["adult_population"] == 3550000
    assert harris["total_population"] == 4780000
    assert harris["adult_population"] != harris["total_population"]
    assert harris["under18_population"] == 1230000
    assert harris["fips"] == "48201"


def test_census_acs_missing_adult_variables_fails_closed():
    with pytest.raises(ValueError, match="Cannot derive adult population"):
        compute_adult_population_from_b01001_row({"B01001_001E": "59000"})


def test_census_county_universe_generation(tmp_path: Path):
    acs_json = tmp_path / "acs.json"
    _write_acs_json(acs_json)
    pop_map = parse_acs_county_population_json(acs_json, reference_year=2024)
    out_file = tmp_path / "census_county_universe.json"
    rep = generate_census_county_universe_report(pop_map, out_file)
    assert rep["report_type"] == "census_county_geography_universe"
    assert rep["total_county_count"] == len(pop_map)
    assert "72" in rep["excluded_territories"]
    assert out_file.exists()


def test_hud_fmr_parsing_and_multi_county_handling(tmp_path: Path):
    xlsx = _xlsx_from_hud_csv(FIXTURES / "sample_hud_fmr_2024.csv", tmp_path / "hud.xlsx")
    obs_list = parse_hud_fmr_xlsx(
        xlsx,
        2024,
        retrieved_at="2026-01-01T00:00:00+00:00",
        file_sha256="a" * 64,
    )
    assert len(obs_list) >= 5
    sf_obs = next(o for o in obs_list if o.geography_id == "06075")
    assert sf_obs.value_monthly == 2490.00
    assert sf_obs.value_annual == 29880.00
    assert sf_obs.status == ComponentStatus.MEASURED
    assert sf_obs.source_id == "hud_fmr_2024"
    assert sf_obs.source_artifact_sha256 != ""


def test_acs_summary_dat_county_filter(tmp_path: Path):
    dat = tmp_path / "acsdt5y2024-b01001.dat"
    dat.write_text(
        "GEO_ID|B01001_E001|B01001_E003|B01001_E004|B01001_E005|B01001_E006|"
        "B01001_E027|B01001_E028|B01001_E029|B01001_E030\n"
        "0500000US48201|4780000|153750|153750|153750|153750|153750|153750|153750|153750\n"
        "0100000US|330000000|1|1|1|1|1|1|1|1\n",
        encoding="utf-8",
    )
    pop_map = parse_acs_summary_dat(dat, reference_year=2024)
    assert "48201" in pop_map
    assert pop_map["48201"]["adult_population"] == 3550000
    assert "01000" not in pop_map


def test_hud_official_filenames_are_current():
    assert HUD_FMR_SOURCES[2024]["expected_filename"] == "FMR2024_final_revised.xlsx"
    assert HUD_FMR_SOURCES[2026]["expected_filename"] == "FY26_FMRs_revised.xlsx"
    assert HUD_FMR_SOURCES[2026]["effective_date"] == "2026-05-21"
    assert "FY24_FMRs_revised" not in HUD_FMR_SOURCES[2024]["url"]


def test_cms_official_urls_are_zips():
    for year in (2024, 2026):
        for url in CMS_PUF_URLS[year].values():
            assert url.startswith("https://download.cms.gov/marketplace-puf/")
            assert url.endswith(".zip")
            assert "/public-use-files/" not in url or "download.cms.gov" in url


def test_hud_acs_geo_join_execution(tmp_path: Path):
    acs_json = tmp_path / "acs.json"
    _write_acs_json(acs_json)
    pop_map = parse_acs_county_population_json(acs_json, reference_year=2024)
    xlsx = _xlsx_from_hud_csv(FIXTURES / "sample_hud_fmr_2024.csv", tmp_path / "hud.xlsx")
    hud_obs = parse_hud_fmr_xlsx(
        xlsx, 2024, retrieved_at="2026-01-01T00:00:00+00:00", file_sha256="b" * 64
    )
    hud_obs = [o for o in hud_obs if o.geography_id in pop_map]
    out_file = tmp_path / "living_cost_geo_join_2024.json"
    join_rep = execute_geo_join_audit(pop_map, hud_obs, reference_year=2024, output_path=out_file)
    assert join_rep["report_type"] == "hud_fmr_census_acs_geo_join"
    assert join_rep["matched_counties_count"] == len(pop_map)
    assert join_rep["unmatched_census_counties_count"] == 0
    assert out_file.exists()


def test_meps_privately_insured_adult_oop_fail_closed(tmp_path: Path):
    meps_csv = tmp_path / "sample_meps.csv"
    meps_csv.write_text(
        "age_group,insurance_status,mean_oop_expenditure,sample_count,represented_population\n"
        "Adults 18-64,Privately Insured,1420.00,12500,165000000\n",
        encoding="utf-8",
    )
    obs = parse_meps_oop_csv(meps_csv, reference_year=2024)
    assert obs.status == ComponentStatus.MEASURED
    assert obs.value_annual == 1420.00

    bad_meps = tmp_path / "bad_meps.csv"
    bad_meps.write_text(
        "age_group,insurance_status,mean_oop_expenditure\nElderly 65+,Medicare,3500.00\n",
        encoding="utf-8",
    )
    unavail_obs = parse_meps_oop_csv(bad_meps, reference_year=2024)
    assert unavail_obs.status == ComponentStatus.UNAVAILABLE
    assert unavail_obs.value_annual is None


def test_usda_food_plans_monthly_aggregation():
    usda_fixture = FIXTURES / "sample_usda_food.csv"
    obs_list = parse_usda_monthly_food_csv(usda_fixture, reference_year=2024)
    assert len(obs_list) >= 1
    low_cost = next(o for o in obs_list if o.component_id == "food_low_cost")
    assert low_cost.value_monthly == 385.98
    assert low_cost.status == ComponentStatus.MEASURED


def test_fhwa_nhts_missing_file_unavailable(tmp_path: Path):
    obs = parse_fhwa_nhts_mileage(tmp_path, reference_year=2024)
    assert obs.status == ComponentStatus.UNAVAILABLE
    assert obs.value_annual is None


def test_eia_gas_price_measured_output(tmp_path: Path):
    eia_csv = tmp_path / "sample_eia.csv"
    eia_csv.write_text("state,regular_gas_price\nCA,4.850\nTX,3.050\n", encoding="utf-8")
    obs_list = parse_eia_gas_prices_csv(eia_csv, reference_year=2024)
    assert len(obs_list) == 2
    ca_gas = next(o for o in obs_list if o.geography_id == "CA")
    assert ca_gas.value_annual == 4.850
    assert ca_gas.unit == "USD_PER_GALLON"


def test_auto_insurance_combined_expenditure(tmp_path: Path):
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


def test_bls_ce_missing_zip_unavailable(tmp_path: Path):
    obs_list = parse_bls_ce_microdata(tmp_path, reference_year=2024)
    assert obs_list
    assert all(o.status == ComponentStatus.UNAVAILABLE for o in obs_list)


def test_bea_rpp_factors(tmp_path: Path):
    rpp_csv = tmp_path / "sample_rpp.csv"
    rpp_csv.write_text("state,rpp_all_items\nCA,112.5\nMS,85.5\n", encoding="utf-8")
    rpp_map = parse_bea_rpp_csv(rpp_csv, reference_year=2024)
    assert rpp_map["CA"] == 1.125
    assert rpp_map["MS"] == 0.855


def test_provenance_validator_strict_gates():
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
    assert validate_component_provenance(valid_obs) == []

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


def test_xlsx_xml_reader_ignores_broken_dimension(tmp_path: Path):
    from foundation.sources.xlsx_xml import rows_as_dicts

    official = (
        Path(__file__).resolve().parents[1]
        / "data"
        / "cache"
        / "usda-lowcostplan-sept2007-present.xlsx"
    )
    if not official.exists():
        pytest.skip("official USDA Low-Cost archive is not in data/cache")
    rows = rows_as_dicts(official)
    assert len(rows) > 100
    assert "year" in rows[0]
    assert "cost" in rows[0]


def test_usda_official_adult_filter_and_ytd_label():
    from foundation.sources.usda_food import build_usda_food_observations

    cache = Path(__file__).resolve().parents[1] / "data" / "cache"
    official = cache / "usda-lowcostplan-sept2007-present.xlsx"
    if not official.exists():
        pytest.skip("official USDA Low-Cost archive is not in data/cache")
    obs = build_usda_food_observations(cache, 2024)
    low = next(o for o in obs if o.component_id == "food_low_cost")
    assert low.value_monthly is not None and low.value_monthly > 0
    assert low.status.value == "MODELED_FROM_MEASURED_INPUTS"
    assert "19-50" in low.notes
    assert "1.20" in low.notes or "1.2" in low.notes


def test_bea_sarpp_zip_all_items_2024():
    zip_path = Path(__file__).resolve().parents[1] / "data" / "cache" / "SARPP.zip"
    if not zip_path.exists():
        pytest.skip("official BEA SARPP.zip is not in data/cache")
    rpp_map = parse_bea_rpp_csv(zip_path, reference_year=2024)
    assert rpp_map["CA"] > 1.05
    assert rpp_map["MS"] < 0.95
    assert "US" not in rpp_map
    assert len(rpp_map) >= 50


def test_bls_ce_uses_cached_official_zip_name():
    from foundation.sources.bls_ce import _existing_interview_zip

    cache = Path(__file__).resolve().parents[1] / "data" / "cache"
    found = _existing_interview_zip(cache, "24")
    if found is None:
        pytest.skip("official BLS CE Interview zip is not in data/cache")
    assert found.name in {"intrvw24.zip", "bls_ce_intrvw24.zip"}
    assert found.stat().st_size > 10_000_000
