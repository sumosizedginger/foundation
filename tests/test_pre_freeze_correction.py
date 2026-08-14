"""Pre-owner-freeze correction tests."""

from __future__ import annotations

import csv
import io
import json
import zipfile
from pathlib import Path

from foundation.living_cost.geo_join import (
    classify_unmatched_hud_fips,
    execute_geo_join_audit,
)
from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.bls_ce import parse_bls_ce_maintenance_candidates
from foundation.sources.bls_ce_ucc import (
    EXCLUDED_UCCS,
    INCLUDED_UCCS,
    INCLUDED_VQB_CODES,
    TIRE_UCCS,
    TIRE_VQB_CODES,
)
from foundation.sources.cms_marketplace import (
    SBE_STANDALONE_STATES,
    SBE_STATE_ZIP_SLUGS,
    inspect_sbe_archive,
    parse_sbe_state_lowest_silver,
)
from foundation.sources.cms_platform import (
    ALL_JURISDICTIONS,
    SBE_FP_STATES,
    assert_platform_map_invariants,
    build_platform_map,
    individual_market_source,
)

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache"
METADATA = ROOT / "data" / "metadata"


def _obs(fips: str, year: int = 2024) -> LivingCostComponentObservation:
    return LivingCostComponentObservation(
        component_id="housing_1br_fmr",
        category="housing",
        geography_type="county",
        geography_id=fips,
        geography_name=fips,
        state=fips[:2],
        reference_year=year,
        value_annual=12000.0,
        value_monthly=1000.0,
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id=f"hud_fmr_{year}",
        source_variable="fmr_1br",
        source_url="https://www.huduser.gov/",
        source_release="test",
        source_reference_period=str(year),
        retrieved_at="2026-08-14T00:00:00+00:00",
        source_artifact_sha256="b" * 64,
        methodology_version="0.2.0-draft",
        notes="",
    )


def test_geo_join_separates_raw_census_from_join_universe():
    raw = {
        "06075": {"adult_population": 10, "county_name": "SF", "state": "CA"},
        "09110": {"adult_population": 2, "county_name": "Capitol", "state": "CT"},
        "09120": {"adult_population": 2, "county_name": "Greater Bridgeport", "state": "CT"},
        "09130": {"adult_population": 2, "county_name": "Lower CT", "state": "CT"},
        "09140": {"adult_population": 2, "county_name": "Naugatuck", "state": "CT"},
        "09150": {"adult_population": 2, "county_name": "Northeastern", "state": "CT"},
        "09160": {"adult_population": 2, "county_name": "Northwest Hills", "state": "CT"},
        "09170": {"adult_population": 2, "county_name": "South Central", "state": "CT"},
        "09180": {"adult_population": 2, "county_name": "Southeastern", "state": "CT"},
        "09190": {"adult_population": 2, "county_name": "Western CT", "state": "CT"},
    }
    join = {
        "06075": raw["06075"],
        "09001": {"adult_population": 8, "county_name": "Fairfield", "state": "CT"},
        "09003": {"adult_population": 2, "county_name": "Hartford", "state": "CT"},
        "09005": {"adult_population": 2, "county_name": "Litchfield", "state": "CT"},
        "09007": {"adult_population": 2, "county_name": "Middlesex", "state": "CT"},
        "09009": {"adult_population": 2, "county_name": "New Haven", "state": "CT"},
        "09011": {"adult_population": 2, "county_name": "New London", "state": "CT"},
        "09013": {"adult_population": 2, "county_name": "Tolland", "state": "CT"},
        "09015": {"adult_population": 2, "county_name": "Windham", "state": "CT"},
    }
    hud = [_obs(fips) for fips in join]
    hud.append(_obs("72001"))
    report = execute_geo_join_audit(
        join,
        hud,
        2024,
        census_artifact_sha256="c" * 64,
        hud_artifact_sha256="d" * 64,
        raw_census_county_universe=raw,
        census_source_id="census_acs5_2024",
        hud_source_id="hud_fmr_2024",
        census_reference_period="2024 ACS 5-Year",
        hud_reference_period="2024",
        census_retrieved_at="2026-08-14T20:18:18+00:00",
        hud_retrieved_at="2026-08-14T20:17:47+00:00",
    )
    assert report["raw_census_county_equivalent_count"] == 10
    assert report["join_geography_count"] == 9
    assert report["connecticut_raw_geographies"] == 9
    assert report["connecticut_reconstructed_geographies"] == 8
    assert report["connecticut_method"] == "legacy_county_reconstructed_from_cousub"
    assert "not the raw Census" in report["census_county_universe_count_note"]
    assert report["census_artifact_sha256"]
    assert report["hud_artifact_sha256"]
    assert report["provenance_complete"] is True
    classified = {
        row["fips"]: row["classification"] for row in report["unmatched_hud_rows_classified"]
    }
    assert classified["72001"] == "excluded_us_territory"
    assert report["unmatched_50_state_dc_county_count"] == 0


def test_production_geo_join_2024_hashes_are_nonempty():
    path = METADATA / "living_cost_geo_join_2024.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("matched_counties_count", 0) < 3000:
        return
    assert payload["census_artifact_sha256"]
    assert payload["hud_artifact_sha256"]
    assert payload.get("raw_census_county_equivalent_count") == 3144
    assert payload.get("join_geography_count") == 3143
    assert payload.get("coverage_claim_allowed") is True


def test_unmatched_hud_classification_categories():
    assert classify_unmatched_hud_fips("72001") == "excluded_us_territory"
    assert classify_unmatched_hud_fips("66010") == "excluded_us_territory"
    assert classify_unmatched_hud_fips("78010") == "excluded_us_territory"
    assert classify_unmatched_hud_fips("60999") == "excluded_us_territory"
    assert classify_unmatched_hud_fips("69999") == "excluded_us_territory"
    assert classify_unmatched_hud_fips("29056") == "special_non_county_hud_geography"
    assert classify_unmatched_hud_fips("12") == "malformed_unrecognized_fips"


def test_oregon_is_not_standalone_individual_sbe():
    for year in (2024, 2026):
        assert "OR" not in SBE_STANDALONE_STATES[year]
        assert "OR" in SBE_FP_STATES[year]
        assert individual_market_source(year, "OR") == "federal_exchange_puf"
        payload = build_platform_map(year, {"OR", "CA"})
        assert_platform_map_invariants(year, payload)
        assert payload["jurisdictions"]["OR"]["SBE_archive_exists"] is True
        assert payload["jurisdictions"]["OR"]["marketplace_platform_classification"] == "sbe_fp"
        assert (
            payload["jurisdictions"]["CA"]["marketplace_platform_classification"]
            == "standalone_sbm"
        )


def test_platform_map_partitions_fifty_states_and_dc():
    for year, sbe_n, fed_n in ((2024, 19, 32), (2026, 21, 30)):
        payload = build_platform_map(year)
        assert_platform_map_invariants(year, payload)
        assert payload["standalone_individual_sbe_count"] == sbe_n
        assert payload["federal_platform_individual_market_count"] == fed_n
        assert len(ALL_JURISDICTIONS) == 51
        assert "GA" in SBE_STANDALONE_STATES[2026]
        assert "GA" not in SBE_STANDALONE_STATES[2024]
        assert "IL" in SBE_STANDALONE_STATES[2026]


def test_closeout_od_labels_match_owner_packet():
    closeout = (METADATA / "living_cost_pre_owner_freeze_closeout.md").read_text(encoding="utf-8")
    assert "OD-011 — municipal earned-income tax geography/overlay" in closeout
    assert "OD-012 — additional resilience reserve" in closeout
    assert "OD-013 — Connecticut HUD/ACS geography treatment" in closeout
    assert "RPP geography" not in closeout
    stale = METADATA / "living_cost_deliverable_2a_report.md"
    archived = METADATA / "historical" / "living_cost_deliverable_2a_report.md"
    assert not stale.exists()
    assert "SUPERSEDED HISTORICAL DELIVERABLE 2A SNAPSHOT" in archived.read_text(encoding="utf-8")
    assert "NOT CURRENT PROJECT STATUS" in archived.read_text(encoding="utf-8")


def test_source_coverage_separates_maintenance_evidence_from_owner_review():
    coverage = json.loads(
        (METADATA / "living_cost_source_coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["headline_calculated"] is False
    for year in ("2024", "2026"):
        assert coverage["coverage_by_year"][year]["maintenance"] == "INCOMPLETE_PROVENANCE"
        dims = coverage["status_dimensions"]["by_year"][year]["maintenance"]
        assert dims["evidence_status"] == "INCOMPLETE_PROVENANCE"
        assert dims["methodology_status"] == "OWNER_REVIEW_PENDING"


def test_oklahoma_2024_is_not_sbe_fp():
    assert "OK" not in SBE_FP_STATES[2024]
    assert "OK" in SBE_FP_STATES[2026]
    for year in (2024, 2026):
        assert individual_market_source(year, "OK") == "federal_exchange_puf"
        payload = build_platform_map(year)
        assert_platform_map_invariants(year, payload)
        assert payload["jurisdictions"]["OK"]["individual_market_source"] == "federal_exchange_puf"
    assert (
        build_platform_map(2024)["jurisdictions"]["OK"]["marketplace_platform_classification"]
        == "healthcare_gov_ffm"
    )
    assert (
        build_platform_map(2026)["jurisdictions"]["OK"]["marketplace_platform_classification"]
        == "sbe_fp"
    )
    # Arkansas and Oregon remain SBE-FP in 2024; HealthCare.gov use is not enough.
    assert "AR" in SBE_FP_STATES[2024]
    assert "OR" in SBE_FP_STATES[2024]
    assert "OK" not in SBE_FP_STATES[2024]


def test_sbe_archive_is_not_platform_classification():
    payload = build_platform_map(2026, {"OR"})
    assert payload["jurisdictions"]["OR"]["SBE_archive_exists"] is True
    assert payload["jurisdictions"]["OR"]["individual_market_source"] == "federal_exchange_puf"
    assert "OR" not in payload["standalone_individual_sbe_states"]


def test_oregon_sbe_archive_is_shop_only():
    path = CACHE / f"cms_sbe_2024_or_{SBE_STATE_ZIP_SLUGS[2024]['OR']}"
    if not path.exists():
        return
    report = inspect_sbe_archive(path, 2024, "OR")
    assert report["SBE_archive_exists"] is True
    assert report["market_scope"] == "SHOP_only"
    assert "do_not_use_for_individual_silver" in report["source_use"]
    join = parse_sbe_state_lowest_silver(path, 2024, "OR")
    assert join["individual_market_rows_retained"] == 0
    assert join["lowest_silver_output_count"] == 0


def test_vermont_community_rated_blank_age_is_accepted():
    path = CACHE / f"cms_sbe_2024_vt_{SBE_STATE_ZIP_SLUGS[2024]['VT']}"
    if not path.exists():
        return
    report = parse_sbe_state_lowest_silver(path, 2024, "VT")
    assert report["individual_market_rows_retained"] > 0
    assert report["lowest_silver_output_count"] == 1
    assert report["observations"][0].state == "VT"


def test_sbe_lowest_silver_join_on_real_state_file():
    path = CACHE / f"cms_sbe_2024_ca_{SBE_STATE_ZIP_SLUGS[2024]['CA']}"
    if not path.exists():
        return
    report = parse_sbe_state_lowest_silver(path, 2024, "CA")
    assert report["rows_parsed_by_source_file"]["plan"] > 0
    assert report["rows_parsed_by_source_file"]["rate"] > 0
    assert report["individual_market_rows_retained"] > 0
    assert report["silver_plans_retained"] > 0
    assert report["lowest_silver_output_count"] > 0
    assert report["observations"][0].state == "CA"


def test_maintenance_allowlist_excludes_gas_insurance_purchase_registration():
    for code in ("470111", "470212", "510110", "450110", "520541", "520516"):
        assert code in EXCLUDED_UCCS
    assert "470212" not in INCLUDED_UCCS
    assert "470211" not in INCLUDED_UCCS
    assert "470220" not in INCLUDED_UCCS
    assert "480110" in INCLUDED_UCCS
    assert "490100" in INCLUDED_UCCS
    assert TIRE_UCCS == {"480110"}
    assert TIRE_VQB_CODES == {"140"}
    assert "140" in INCLUDED_VQB_CODES
    assert "190" in INCLUDED_VQB_CODES
    assert "420" not in INCLUDED_VQB_CODES


def test_missing_tirecq_is_not_measured_zero(tmp_path: Path):
    zip_path = tmp_path / "intrvw24.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        fmli = io.StringIO()
        writer = csv.DictWriter(fmli, fieldnames=["NEWID", "FAM_SIZE", "FINLWT21", "VEHQ"])
        writer.writeheader()
        writer.writerow({"NEWID": "1", "FAM_SIZE": "1", "FINLWT21": "10", "VEHQ": "1"})
        writer.writerow({"NEWID": "2", "FAM_SIZE": "1", "FINLWT21": "10", "VEHQ": "1"})
        zf.writestr("intrvw24/fmli241x.csv", fmli.getvalue())
        mtbi = io.StringIO()
        writer = csv.DictWriter(mtbi, fieldnames=["NEWID", "UCC", "COST", "EXPNAME"])
        writer.writeheader()
        writer.writerow({"NEWID": "1", "UCC": "470212", "COST": "25", "EXPNAME": "GASOILX"})
        writer.writerow({"NEWID": "1", "UCC": "470111", "COST": "80", "EXPNAME": "JGASOXQV"})
        writer.writerow({"NEWID": "2", "UCC": "510110", "COST": "200", "EXPNAME": "QADITR1X"})
        zf.writestr("intrvw24/mtbi241x.csv", mtbi.getvalue())
    result = parse_bls_ce_maintenance_candidates(zip_path, reference_year=2024)
    assert result["tirecq_interpreted_as_measured_zero"] is False
    assert result["tirecq_present"] is False
    assert result["status"] == "INCOMPLETE_PROVENANCE"
    assert result["candidates"]["tires"]["status"] == "UCC_ABSENT_NOT_MEASURED_ZERO"
    assert result["candidates"]["tires"]["n"] == 0
    assert result["candidates"]["routine_maintenance"]["status"] == "UCC_ABSENT_NOT_MEASURED_ZERO"
    assert result["candidates"]["routine_maintenance"]["n"] == 0
    combined = result["candidates"]["maintenance_repairs_tires_combined"]
    # Fuel residual 470212 and insurance must not enter the basket.
    assert combined["status"] == "UCC_ABSENT_NOT_MEASURED_ZERO"
    assert combined["n"] == 0


def test_vqb_file_is_used_for_maintenance_split(tmp_path: Path):
    zip_path = tmp_path / "intrvw24.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        fmli = io.StringIO()
        writer = csv.DictWriter(fmli, fieldnames=["NEWID", "FAM_SIZE", "FINLWT21", "VEHQ"])
        writer.writeheader()
        writer.writerow({"NEWID": "1", "FAM_SIZE": "1", "FINLWT21": "10", "VEHQ": "1"})
        writer.writerow({"NEWID": "2", "FAM_SIZE": "1", "FINLWT21": "10", "VEHQ": "1"})
        zf.writestr("intrvw24/fmli241x.csv", fmli.getvalue())
        vqb = io.StringIO()
        writer = csv.DictWriter(vqb, fieldnames=["NEWID", "VQBCODE", "VQBEXPX", "VQBMO"])
        writer.writeheader()
        writer.writerow({"NEWID": "1", "VQBCODE": "140", "VQBEXPX": "100", "VQBMO": "1"})
        writer.writerow({"NEWID": "1", "VQBCODE": "250", "VQBEXPX": "80", "VQBMO": "1"})
        writer.writerow({"NEWID": "2", "VQBCODE": "420", "VQBEXPX": "200", "VQBMO": "1"})
        zf.writestr("intrvw24/expn24/vqb24.csv", vqb.getvalue())
        mtbi = io.StringIO()
        writer = csv.DictWriter(mtbi, fieldnames=["NEWID", "UCC", "COST", "EXPNAME"])
        writer.writeheader()
        writer.writerow({"NEWID": "1", "UCC": "470212", "COST": "25", "EXPNAME": "GASOILX"})
        zf.writestr("intrvw24/mtbi241x.csv", mtbi.getvalue())
    result = parse_bls_ce_maintenance_candidates(zip_path, reference_year=2024)
    assert result["detail_source"] == "vqb"
    assert result["status"] == "INCOMPLETE_PROVENANCE"
    assert result["candidates"]["tires"]["status"] == "MEASURED_FROM_VQB"
    assert result["candidates"]["tires"]["n_positive"] == 1
    # Quarterly 100 * 4 = 400 annual; CU 2 is a zero-spend vehicle owner.
    assert result["candidates"]["tires"]["mean_incl_zero"] == 200.0
    assert result["candidates"]["routine_maintenance"]["status"] == "UCC_ABSENT_NOT_MEASURED_ZERO"
    combined = result["candidates"]["maintenance_repairs_tires_combined"]
    assert combined["n"] == 2
    assert combined["n_positive"] == 1
    # Registration (250) and warranties (420) must not enter the basket.
    assert combined["mean_incl_zero"] == 200.0


def test_official_cached_interview_uses_vqb_not_fuel_residual():
    zip_path = CACHE / "intrvw24.zip"
    if not zip_path.exists():
        return
    result = parse_bls_ce_maintenance_candidates(zip_path, reference_year=2024)
    assert result["detail_source"] == "vqb"
    assert result["status"] == "INCOMPLETE_PROVENANCE"
    assert result["fully_reproducible_retrieval_provenance"] is False
    assert result["tirecq_interpreted_as_measured_zero"] is False
    assert "140" in result["included_vqb_codes_present"]
    assert "190" in result["included_vqb_codes_present"]
    assert "470212" in result["excluded_uccs"]
    combined = result["candidates"]["maintenance_repairs_tires_combined"]
    assert combined["status"] == "MEASURED_FROM_VQB"
    assert combined["n"] > 1000
    assert combined["n_positive"] > 100
    assert combined["mean_incl_zero"] is not None
    assert combined["mean_incl_zero"] > 100
    tires = result["candidates"]["tires"]
    assert tires["status"] == "MEASURED_FROM_VQB"
    assert tires["n_positive"] > 0
    routine = result["candidates"]["routine_maintenance"]
    assert routine["status"] == "MEASURED_FROM_VQB"
    assert routine["mean_incl_zero"] != 0.0
