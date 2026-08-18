"""Owner-freeze tests for OD-001 through OD-013.

These tests exercise the frozen methodology the way a later candidate
calculation would: they call the selection/formula functions and the
public writers. They do not calculate or publish a headline MSLC.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundation.config import definitions
from foundation.living_cost.owner_freeze import (
    ADDITIONAL_FREEZES,
    FROZEN_DECISIONS,
    MINIMUM_SOCIAL_RECREATION_ANNUAL,
    PREFERRED_SOCIAL_RECREATION_ANNUAL,
    all_ods_frozen,
    apply_recreation_floor,
    canonical_connectivity_bundle,
    canonical_resilience_reserve,
    canonical_social_recreation_annual,
    classify_municipal_tax_geography,
    connecticut_geography_method,
    food_plan_selection,
    freshness_gate_checklist,
    health_premium_profile,
    housing_standard,
    living_cost_release_authorized,
    local_tax_application_rule,
    methodology_status_for_component,
    preferred_social_recreation_annual,
    public_states_modeled,
    recreation_output_pair,
    select_acs_weight_vintage,
    select_epa_mpg_cohort,
    select_maintenance_statistic,
    select_meps_oop_statistic,
    select_naic_insurance_measure,
    select_nhts_mileage_statistic,
    translate_lagged_nominal_dollars,
    translation_method_for_component,
    used_car_model_year_window,
    vehicle_replacement_reserve,
    write_owner_freeze_record,
)
from foundation.living_cost.owner_packet import write_owner_decision_packet
from foundation.living_cost.recreation import calculate_social_recreation
from foundation.living_cost.taxes import calculate_local_income_tax
from foundation.pipeline import run_full_pipeline
from foundation.sources.epa_mpg import build_mpg_candidates
from foundation.sources.fhwa_nhts import parse_fhwa_nhts_mileage

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"


def test_all_thirteen_ods_are_accepted_frozen():
    assert all_ods_frozen() is True
    assert {item["id"] for item in FROZEN_DECISIONS} == {f"OD-{i:03d}" for i in range(1, 14)}
    for item in FROZEN_DECISIONS:
        assert item["status"] == "ACCEPTED"
        assert item["methodology_status"] == "FROZEN"
        assert item["effective_date"]
        assert item["decision"]
        assert item["owner_rationale"]
        assert item["implementation_rule"]
        assert item["source_selection_rule"]
        assert "required_sensitivity" in item
        assert "known_evidence_gaps" in item
        assert "numeric_value_currently_available" in item
        assert item["evidence_status"] != "HEALTHY"


def test_od001_freshest_acs_and_fixed_2024_sensitivity():
    available_today = [2024]
    assert select_acs_weight_vintage(2024, available_today) == 2024
    assert select_acs_weight_vintage(2026, available_today) == 2024
    assert select_acs_weight_vintage(2026, available_today, mode="fixed_2024_sensitivity") == 2024
    # When a newer county vintage exists, current advances; historical 2024 does not.
    future = [2024, 2025]
    assert select_acs_weight_vintage(2024, future) == 2024
    assert select_acs_weight_vintage(2026, future) == 2025
    assert select_acs_weight_vintage(2026, future, mode="fixed_2024_sensitivity") == 2024


def test_od002_mean_primary_median_p75_sensitivity():
    spec = select_meps_oop_statistic()
    assert spec["canonical"] == "weighted_mean"
    assert "weighted_median" in spec["sensitivities"]
    assert "weighted_p75" in spec["sensitivities"]
    assert spec["newest_listed_at_freeze"] == "HC-251"
    assert spec["use_2024_if_listed"] is True


def test_od003_median_mileage_primary():
    selected = select_nhts_mileage_statistic(
        {
            "weighted_median": 10000.0,
            "weighted_mean": 19152.2,
            "weighted_p25": 5000.0,
            "weighted_p75": 17280.0,
        }
    )
    assert selected["canonical_statistic"] == "weighted_median"
    assert selected["canonical_value"] == 10000.0
    assert selected["canonical_label"] == "FOUNDATION MOBILITY STANDARD"
    assert selected["not_a_label"] == "MEASURED MINIMUM NECESSARY MILEAGE"
    assert selected["sensitivities"]["p25"] == 5000.0
    assert selected["sensitivities"]["mean"] == 19152.2
    assert selected["sensitivities"]["p75"] == 17280.0


def test_od004_no_hardcoded_mpg_cohort_derived():
    assert used_car_model_year_window(2024) == (2012, 2016)
    assert used_car_model_year_window(2026) == (2014, 2018)
    rows = [
        {
            "year": "2014",
            "VClass": "Compact Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "30",
        },
        {
            "year": "2014",
            "VClass": "Midsize Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "26",
        },
        {
            "year": "2014",
            "VClass": "Compact Cars",
            "fuelType": "Electricity",
            "atvType": "EV",
            "comb08": "110",
        },
        {
            "year": "2024",
            "VClass": "Compact Cars",
            "fuelType": "Regular",
            "atvType": "",
            "comb08": "34",
        },
    ]
    candidates = build_mpg_candidates(rows, 2024)
    chosen = select_epa_mpg_cohort(candidates, 2024)
    assert chosen["cohort_id"] == "used_compact_midsize_gasoline"
    assert chosen["statistic"] == "median_mpg"
    # Project percentile convention is first cumulative weight >= 0.50, so
    # equal-weight 26 and 30 yields 26, not the arithmetic midpoint 28.
    assert chosen["value"] == 26.0
    assert chosen["sensitivities"]["weighted_mean"] == 28.0
    assert chosen["hardcoded_mpg_forbidden"] is True
    assert chosen["n"] == 2


def test_od005_replacement_formula_no_retired_default():
    pending = vehicle_replacement_reserve(None, None, None)
    assert pending["numeric_value_currently_available"] is False
    assert pending["annual_reserve"] is None
    assert pending["retired_defaults_forbidden"]["annual"] == 1600.0
    computed = vehicle_replacement_reserve(9000.0, 1500.0, 6.0)
    assert computed["annual_reserve"] == 1250.0
    assert computed["annual_reserve"] != 1600.0
    with pytest.raises(ValueError):
        vehicle_replacement_reserve(9000.0, 1500.0, 0.0)


def test_od006_combined_naic_premium_primary():
    spec = select_naic_insurance_measure()
    assert spec["canonical"] == "combined_average_premium"
    assert "average_expenditure" in spec["sensitivities"]


def test_od007_mean_including_zero_primary():
    spec = select_maintenance_statistic(
        {
            "maintenance_repairs_tires_combined": {
                "mean_incl_zero": 781.22,
                "median_incl_zero": 0.0,
                "p25_positive": 276.0,
                "p50_positive": 560.0,
                "positive_spender_mean": 1728.47,
            }
        }
    )
    assert spec["canonical"] == "weighted_mean_including_zeros"
    assert spec["canonical_value"] == 781.22
    assert spec["sensitivities"]["median_including_zeros"] == 0.0
    assert spec["sensitivities"]["positive_spender_p25"] == 276.0
    assert spec["sensitivities"]["positive_spender_p50"] == 560.0
    assert spec["sensitivities"]["positive_spender_mean"] == 1728.47
    assert spec["evidence_status"] == "INCOMPLETE_PROVENANCE"
    assert spec["methodology_status"] == "FROZEN"
    assert spec["do_not_promote_to_validated_because_methodology_is_frozen"] is True


def test_od007_production_artifact_schema():
    artifact = json.loads(
        (METADATA / "living_cost_maintenance_candidates.json").read_text(encoding="utf-8")
    )
    spec = select_maintenance_statistic(artifact)
    assert spec["canonical_value"] == 781.22
    assert spec["sensitivities"]["median_including_zeros"] == 0.0
    assert spec["sensitivities"]["positive_spender_p25"] == 276.0
    assert spec["sensitivities"]["positive_spender_p50"] == 560.0
    assert spec["sensitivities"]["positive_spender_mean"] == 1728.47
    assert spec["evidence_status"] == "INCOMPLETE_PROVENANCE"
    assert spec["evidence_status"] != "VALIDATED"


def test_od008_recreation_floors_never_undercut():
    assert canonical_social_recreation_annual(400.0) == 1200.0
    assert canonical_social_recreation_annual(1800.0) == 1800.0
    assert preferred_social_recreation_annual(400.0) == 2400.0
    assert preferred_social_recreation_annual(3000.0) == 3000.0
    assert apply_recreation_floor(None, floor_annual=1200.0) == 1200.0
    pair = recreation_output_pair(500.0)
    assert pair["minimum_sustainable_annual"] >= MINIMUM_SOCIAL_RECREATION_ANNUAL
    assert pair["preferred_modest_life_annual"] >= PREFERRED_SOCIAL_RECREATION_ANNUAL
    low = calculate_social_recreation(400.0, 1.0, 2024, "06075")
    assert low.value_annual == 1200.0
    low_rpp = calculate_social_recreation(400.0, 0.85, 2024, "06075")
    assert low_rpp.value_annual == 1200.0
    high = calculate_social_recreation(2400.0, 1.15, 2024, "06075")
    assert high.value_annual == 2760.0


def test_od009_canonical_connectivity_requires_mobile_and_broadband():
    bundle = canonical_connectivity_bundle()
    assert bundle["requires_mobile"] is True
    assert bundle["requires_broadband"] is True
    assert bundle["canonical_components"] == ["mobile", "broadband"]
    assert bundle["mobile_only"] == "sensitivity_only"
    assert bundle["broadband_only"] == "sensitivity_only"
    assert bundle["mobile_price_evidence_status"] == "SOURCE_GAP"
    assert bundle["broadband_standard_mbps"]["downstream"] == 100
    assert bundle["broadband_standard_mbps"]["upstream"] == 20


def test_od010_unsupported_tax_year_fail_closed():
    from foundation.living_cost.taxes import (
        UnsupportedTaxYearError,
        calculate_federal_income_tax,
        calculate_fica_taxes,
        calculate_state_income_tax,
    )

    assert calculate_federal_income_tax(30000.0, year=2024) != calculate_federal_income_tax(
        30000.0, year=2026
    )
    assert calculate_state_income_tax(40000.0, "CA", year=2024) >= 0
    assert calculate_state_income_tax(40000.0, "CA", year=2026) >= 0
    for year in (2025, 2027, 2019):
        with pytest.raises(UnsupportedTaxYearError):
            calculate_federal_income_tax(30000.0, year=year)
        with pytest.raises(UnsupportedTaxYearError):
            calculate_fica_taxes(30000.0, year=year)
        with pytest.raises(UnsupportedTaxYearError):
            calculate_state_income_tax(40000.0, "CA", year=year)
        with pytest.raises(UnsupportedTaxYearError):
            calculate_state_income_tax(40000.0, "FL", year=year)


def test_od010_lagged_nominal_cannot_use_silent_latest_available():
    assert translation_method_for_component("structural_quantity") == "LATEST_AVAILABLE"
    assert translation_method_for_component("target_year_rule") == "RULE_YEAR"
    assert translation_method_for_component("high_frequency_price") == "YTD"
    assert translation_method_for_component("lagged_nominal_dollar") == "CPI_UPDATED"
    assert translation_method_for_component("already_local_current_price") == "NONE_ALREADY_LOCAL"
    with pytest.raises(ValueError, match="LATEST_AVAILABLE"):
        translate_lagged_nominal_dollars(
            100.0,
            project_cost_year=2026,
            source_data_year=2023,
            translation_method="LATEST_AVAILABLE",
            price_index_series="CPI-U",
            translation_factor=1.1,
        )
    rec = translate_lagged_nominal_dollars(
        100.0,
        project_cost_year=2026,
        source_data_year=2023,
        translation_method="CPI_UPDATED",
        price_index_series="CUSR0000SAM",
        translation_factor=1.1,
    )
    assert rec.translated_value == 110.0
    assert rec.original_value == 100.0
    assert rec.source_data_year == 2023
    assert rec.project_cost_year == 2026


def test_od011_partial_city_tax_cannot_apply_countywide():
    assert (
        classify_municipal_tax_geography(
            tax_applies_throughout_modeled_county=True,
            tax_is_county_level=False,
            municipality_covers_only_part_of_county=False,
        )
        == "A"
    )
    assert (
        classify_municipal_tax_geography(
            tax_applies_throughout_modeled_county=False,
            tax_is_county_level=True,
            municipality_covers_only_part_of_county=False,
        )
        == "B"
    )
    assert (
        classify_municipal_tax_geography(
            tax_applies_throughout_modeled_county=False,
            tax_is_county_level=False,
            municipality_covers_only_part_of_county=True,
        )
        == "C"
    )
    rule_c = local_tax_application_rule("C")
    assert rule_c["apply"] is False
    assert rule_c["status"] == "SOURCE_GAP"
    assert "entire county" in rule_c["reason"]
    from foundation.living_cost.taxes import (
        LOCAL_TAX_PARTIAL_CITY,
        LOCAL_TAX_UNRESOLVED,
        LOCAL_TAX_VERIFIED_NO_TAX,
        LOCAL_TAX_VERIFIED_RATE,
        LocalTaxUnresolvedError,
        evaluate_taxes_for_gross,
        solve_gross_required_income,
    )

    nyc = calculate_local_income_tax(10000.0, "36061")
    phl = calculate_local_income_tax(10000.0, "42101")
    md = calculate_local_income_tax(10000.0, "24005")
    assert nyc.amount is not None and nyc.amount > 0
    assert nyc.evidence_status == LOCAL_TAX_VERIFIED_RATE
    assert phl.amount is not None and phl.amount > 0
    assert md.geography_class == "B"
    none = calculate_local_income_tax(10000.0, "48201")
    assert none.amount == 0.0
    assert none.evidence_status == LOCAL_TAX_VERIFIED_NO_TAX
    unresolved = calculate_local_income_tax(10000.0, "06075")
    assert unresolved.amount is None
    assert unresolved.evidence_status == LOCAL_TAX_UNRESOLVED
    partial = calculate_local_income_tax(10000.0, "39049", geography_class="C")
    assert partial.evidence_status == LOCAL_TAX_PARTIAL_CITY
    assert partial.amount is None
    with pytest.raises(LocalTaxUnresolvedError):
        evaluate_taxes_for_gross(40000.0, "CA", "06075", 2024)
    with pytest.raises(LocalTaxUnresolvedError):
        solve_gross_required_income(30000.0, state="CA", fips_code="06075", year=2024)
    from foundation.living_cost.local import compute_local_living_cost

    with pytest.raises(LocalTaxUnresolvedError):
        compute_local_living_cost(
            geography_id="06075",
            geography_name="San Francisco County, CA",
            state="CA",
            reference_year=2024,
            adult_population=700000,
            housing_annual=28000.0,
            food_annual=4800.0,
            transportation_annual=8000.0,
            healthcare_annual=7000.0,
            connectivity_annual=1440.0,
            essentials_annual=2400.0,
            social_recreation_annual=2800.0,
            resilience_annual=0.0,
        )


def test_od012_generic_resilience_reserve_is_zero():
    assert canonical_resilience_reserve() == 0.0
    assert definitions()["living_cost"]["resilience"]["extra_reserve_annual"] == 0


def test_od013_connecticut_year_specific_join():
    assert connecticut_geography_method(2024) == "legacy_county_reconstructed_from_cousub"
    assert connecticut_geography_method(2026) == "direct_planning_region_join"


def test_owner_freeze_does_not_authorize_headline():
    from foundation.living_cost.freshness import candidate_calculation_authorized

    assert living_cost_release_authorized() is False
    assert candidate_calculation_authorized() is False
    assert public_states_modeled() == 0
    assert definitions()["living_cost"]["release_authorized"] is False
    assert definitions()["living_cost"]["candidate_calculation_authorized"] is False
    assert definitions()["living_cost"]["states_modeled"] == 0
    payload = write_owner_decision_packet(METADATA)
    assert payload["headline_calculated"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["candidate_calculation_authorized"] is False
    assert payload["states_modeled"] == 0
    assert payload["decisions_frozen"] is True
    assert payload["methodology_frozen_is_not_source_validated"] is True


def test_writer_emits_frozen_record(tmp_path: Path):
    payload = write_owner_freeze_record(tmp_path)
    assert (tmp_path / "living_cost_owner_decisions_frozen.json").exists()
    assert (tmp_path / "living_cost_owner_decisions_frozen.md").exists()
    text = (tmp_path / "living_cost_owner_decisions_frozen.md").read_text(encoding="utf-8")
    assert "ACCEPTED / FROZEN" in text
    assert "No Minimum Sustainable Living Cost headline" in text
    assert payload["all_ods_frozen"] is True


def test_food_health_housing_additional_freezes():
    assert food_plan_selection()["canonical"] == "usda_low_cost_food_plan"
    assert food_plan_selection()["sensitivity"] == "usda_thrifty_food_plan"
    profile = health_premium_profile()
    assert profile["age"] == 40
    assert profile["metal"] == "Silver"
    assert profile["subsidy"] is False
    assert profile["fake_deductible_or_rating_area_fallback"] is False
    housing = housing_standard()
    assert housing["unit"] == "independent_1_bedroom"
    assert housing["roommate"] is False
    assert housing["double_count_hud_tenant_utilities"] is False
    assert ADDITIONAL_FREEZES["food"]["canonical"] == "usda_low_cost_food_plan"


def test_freshness_gate_exists_and_does_not_authorize_headline():
    from foundation.living_cost.freshness import (
        REQUIRED_FRESHNESS_FAMILIES,
        FreshnessGateError,
        assert_candidate_freshness_ready,
    )

    gate = freshness_gate_checklist()
    required = gate["required_before_candidate_calculation"]
    for family in (
        "meps_full_year_consolidated",
        "usda_food",
        "cms_marketplace_sbe",
        "eia_gasoline",
        "federal_tax_law",
        "mobile_price",
        "bls_ce",
        "od010_price_index",
    ):
        assert family in required
    assert set(REQUIRED_FRESHNESS_FAMILIES) == set(required)
    assert "vehicle_replacement" in required
    assert "bea_rpp" in required
    assert gate["headline_authorized_by_this_gate"] is False
    assert gate["calculates_mslc"] is False
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()


def test_candidate_authorization_is_separate_from_public_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from foundation.living_cost.freshness import (
        REQUIRED_FRESHNESS_FAMILIES,
        FreshnessCheck,
        FreshnessGateError,
        assert_candidate_freshness_ready,
        assert_public_release_authorized,
        candidate_calculation_authorized,
        living_cost_release_authorized,
        write_candidate_freshness_report,
    )

    assert candidate_calculation_authorized() is False
    assert living_cost_release_authorized() is False
    assert candidate_calculation_authorized() is not True
    ready = {
        family: FreshnessCheck(
            source_id=family,
            latest_checked_at="2026-08-15T00:00:00Z",
            latest_authoritative_vintage_found="2026",
            selected_vintage="2026",
            selected_artifact="synthetic_test_only",
            newer_data_exists=False,
            retrieval_validation_status="VALIDATED",
            freshness_check_status="VERIFIED_CURRENT",
            publisher="synthetic",
            landing_url="https://example.test/synthetic",
            selected_artifacts=(
                {
                    "artifact_id": "synthetic_test_only",
                    "sha256": "abc",
                    "url": "https://example.test",
                },
            ),
            transformation_method="test",
            input_evidence_status="VALIDATED",
        )
        for family in REQUIRED_FRESHNESS_FAMILIES
    }
    # Methodology freeze + candidate auth false cannot calculate.
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()
    from foundation.config import definitions as real_defs

    base = real_defs()
    living = dict(base["living_cost"])
    living["candidate_calculation_authorized"] = True
    living["release_authorized"] = False
    monkeypatch.setattr("foundation.config.definitions", lambda: {**base, "living_cost": living})
    # Candidate true + freshness ready may allow a future PRIVATE candidate.
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    ready_with_years = {}
    for family, check in ready.items():
        payload = check.to_dict()
        payload["year_coverage"] = {
            "2024": {"covered": True},
            "2026": {"covered": True},
        }
        payload["listing_freshness_status"] = "VERIFIED_CURRENT"
        payload["artifact_currentness_status"] = "VERIFIED_CURRENT"
        payload["selected_artifact_matches_latest"] = True
        ready_with_years[family] = FreshnessCheck(**payload)
    monkeypatch.setattr(
        "foundation.living_cost.freshness.current_family_truth",
        lambda: ready_with_years,
    )
    from foundation.living_cost.freshness import _validate_candidate_checks

    _validate_candidate_checks(ready_with_years)
    # Public publication still blocked.
    with pytest.raises(FreshnessGateError, match="living_cost_release_authorized"):
        assert_public_release_authorized()
    monkeypatch.undo()

    def _committed_checks() -> dict[str, FreshnessCheck]:
        from dataclasses import fields

        payload = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "data"
                / "metadata"
                / "living_cost_candidate_freshness.json"
            ).read_text(encoding="utf-8")
        )
        allowed = {item.name for item in fields(FreshnessCheck)}
        checks: dict[str, FreshnessCheck] = {}
        for family, raw in payload["checks"].items():
            rec = {key: value for key, value in raw.items() if key in allowed}
            if rec.get("selected_artifacts") is not None:
                rec["selected_artifacts"] = tuple(rec["selected_artifacts"])
            if rec.get("months_included") is not None:
                rec["months_included"] = tuple(rec["months_included"])
            checks[family] = FreshnessCheck(**rec)
        return checks

    monkeypatch.setattr(
        "foundation.living_cost.freshness.current_family_truth",
        _committed_checks,
    )
    report = write_candidate_freshness_report(tmp_path)
    assert report["ready_for_private_candidate"] is False
    assert report["candidate_calculation_authorized"] is False
    assert report["living_cost_release_authorized"] is False
    assert report["calculates_mslc"] is False
    assert report["blocker_count"] > 0
    assert "vehicle_replacement" in report["checks"]
    assert "bea_rpp" in report["checks"]
    assert report["checks"]["vehicle_replacement"]["retrieval_validation_status"] == (
        "FORMULA_FROZEN_INPUTS_PENDING"
    )
    assert report["checks"]["meps_full_year_consolidated"]["retrieval_validation_status"] == (
        "MODELED_FROM_MEASURED_INPUTS"
    )
    assert report["checks"]["epa_vehicle"]["retrieval_validation_status"] == (
        "MODELED_FROM_MEASURED_INPUTS"
    )


def test_production_coverage_keeps_evidence_separate_from_frozen_methodology():
    coverage = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    assert coverage["headline_calculated"] is False
    assert coverage["living_cost_release_authorized"] is False
    assert coverage["candidate_calculation_authorized"] is False
    assert coverage["decisions_frozen"] is True
    assert coverage["coverage_by_year"]["2024"]["health_oop"] == "MODELED_FROM_MEASURED_INPUTS"
    assert coverage["coverage_by_year"]["2024"]["mpg"] == "MODELED_FROM_MEASURED_INPUTS"
    assert "MEPS HEALTH OOP DERIVATION" in coverage["blocker_notes"]["health_oop"]
    assert "MODELED_FROM_MEASURED_INPUTS" in coverage["blocker_notes"]["mpg"]
    blob = json.dumps(coverage)
    assert "unfrozen" not in blob.lower()
    assert "OD-004 not frozen" not in blob
    for year in ("2024", "2026"):
        maint = coverage["status_dimensions"]["by_year"][year]["maintenance"]
        assert maint["evidence_status"] == "INCOMPLETE_PROVENANCE"
        assert maint["methodology_status"] == "FROZEN"
        assert (
            coverage["status_dimensions"]["by_year"][year]["population_weights"][
                "methodology_status"
            ]
            == "FROZEN"
        )
        assert methodology_status_for_component("recreation") == "FROZEN"
    manifest = (METADATA / "living_cost_source_manifest.json").read_text(encoding="utf-8")
    assert "OD-006 remains unfrozen" not in manifest
    assert "OD-004 not frozen" not in manifest
    writer = (ROOT / "scripts" / "validate_living_cost_sources.py").read_text(encoding="utf-8")
    assert "OD-010 unfrozen" not in writer
    assert '"replacement": "ESTIMATED_OWNER_REVIEW"' not in writer


def test_nhts_parser_uses_median_as_canonical(tmp_path: Path):
    import csv
    import io
    import zipfile

    zip_path = tmp_path / "nhts_2022_csv.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        hh = io.StringIO()
        writer = csv.DictWriter(hh, fieldnames=["HOUSEID", "HHSIZE", "WRKCOUNT", "WTHHFIN"])
        writer.writeheader()
        writer.writerow({"HOUSEID": "1", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "1"})
        writer.writerow({"HOUSEID": "2", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "1"})
        writer.writerow({"HOUSEID": "3", "HHSIZE": "1", "WRKCOUNT": "1", "WTHHFIN": "1"})
        zf.writestr("hhv2pub.csv", hh.getvalue())
        per = io.StringIO()
        writer = csv.DictWriter(per, fieldnames=["HOUSEID", "R_AGE", "DRIVER"])
        writer.writeheader()
        for hid in ("1", "2", "3"):
            writer.writerow({"HOUSEID": hid, "R_AGE": "40", "DRIVER": "1"})
        zf.writestr("perv2pub.csv", per.getvalue())
        veh = io.StringIO()
        writer = csv.DictWriter(veh, fieldnames=["HOUSEID", "ANNMILES"])
        writer.writeheader()
        writer.writerow({"HOUSEID": "1", "ANNMILES": "5000"})
        writer.writerow({"HOUSEID": "2", "ANNMILES": "10000"})
        writer.writerow({"HOUSEID": "3", "ANNMILES": "30000"})
        zf.writestr("vehv2pub.csv", veh.getvalue())
    obs = parse_fhwa_nhts_mileage(tmp_path, reference_year=2024)
    assert obs.value_annual == 10000.0
    assert "FOUNDATION MOBILITY STANDARD" in obs.notes
    assert "MINIMUM NECESSARY" in obs.notes


def test_pipeline_still_refuses_headline_after_freeze():
    src = (ROOT / "src" / "foundation" / "pipeline.py").read_text(encoding="utf-8")
    assert "candidate_calculation_authorized()" in src
    assert "living_cost_release_authorized()" in src
    assert run_full_pipeline  # importable; do not flip the gate
