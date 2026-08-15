"""User-style tests for the freshness-control audit fix.

Does not calculate or publish an MSLC.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundation.living_cost.freshness import (
    REQUIRED_FRESHNESS_FAMILIES,
    FreshnessCheck,
    FreshnessGateError,
    _validate_candidate_checks,
    are_candidate_inputs_bound,
    assert_candidate_freshness_ready,
    assert_public_release_authorized,
    candidate_calculation_authorized,
    evaluate_freshness_readiness,
    is_translation_index_bound,
    living_cost_release_authorized,
    run_candidate_readiness_gate,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"
SRC = ROOT / "src"


def _ready_family(family: str, **overrides: object) -> FreshnessCheck:
    payload = {
        "source_id": family,
        "latest_checked_at": "2026-08-15T00:00:00Z",
        "latest_authoritative_vintage_found": "2024 official",
        "selected_vintage": "2024 official",
        "selected_artifact": f"{family}.bin",
        "newer_data_exists": False,
        "retrieval_validation_status": "VALIDATED",
        "freshness_check_status": "VERIFIED_CURRENT",
        "publisher": "official",
        "landing_url": f"https://example.test/{family}",
        "selected_artifacts": (
            {
                "artifact_id": f"{family}.bin",
                "sha256": "abc",
                "url": f"https://example.test/{family}",
            },
        ),
        "transformation_method": "none",
        "input_evidence_status": "VALIDATED",
        "listing_freshness_status": "VERIFIED_CURRENT",
        "artifact_currentness_status": "VERIFIED_CURRENT",
        "selected_artifact_matches_latest": True,
        "year_coverage": {
            "2024": {"covered": True, "note": "synthetic"},
            "2026": {"covered": True, "note": "synthetic"},
        },
    }
    payload.update(overrides)
    return FreshnessCheck(**payload)  # type: ignore[arg-type]


def _all_ready() -> dict[str, FreshnessCheck]:
    return {family: _ready_family(family) for family in REQUIRED_FRESHNESS_FAMILIES}


def test_authorization_reads_definitions_yml():
    from foundation.config import definitions

    living = definitions()["living_cost"]
    assert living["candidate_calculation_authorized"] is False
    assert living["release_authorized"] is False
    assert candidate_calculation_authorized() is False
    assert living_cost_release_authorized() is False
    src = (SRC / "foundation" / "living_cost" / "freshness.py").read_text(encoding="utf-8")
    assert "return False" not in src.split("def candidate_calculation_authorized")[1][:400]
    assert "definitions.yml" in src


def _patch_living_auth(monkeypatch: pytest.MonkeyPatch, *, candidate: bool, release: bool) -> None:
    from foundation.config import definitions as real_defs

    base = real_defs()
    living = dict(base["living_cost"])
    living["candidate_calculation_authorized"] = candidate
    living["release_authorized"] = release
    patched = {**base, "living_cost": living}
    monkeypatch.setattr("foundation.config.definitions", lambda: patched)


def test_public_gates_have_no_authorization_override():
    import inspect

    cand = inspect.signature(assert_candidate_freshness_ready)
    rel = inspect.signature(assert_public_release_authorized)
    assert "candidate_calculation_authorized" not in cand.parameters
    assert "living_cost_release_authorized" not in cand.parameters
    assert "living_cost_release_authorized" not in rel.parameters


def test_config_candidate_false_blocks_private_gate():
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()


def test_config_candidate_true_plus_freshness_fail_is_blocked(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    checks = _all_ready()
    checks["mobile_price"] = _ready_family(
        "mobile_price",
        retrieval_validation_status="SOURCE_GAP",
        freshness_check_status="SOURCE_GAP",
        newer_data_exists=None,
        selected_vintage=None,
        selected_artifact=None,
        selected_artifacts=(),
    )
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    with pytest.raises(FreshnessGateError, match="SOURCE_GAP"):
        _validate_candidate_checks(checks)


def test_config_candidate_true_plus_freshness_pass_may_proceed(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    live = _all_ready()
    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", lambda: live)
    _validate_candidate_checks(live)
    with pytest.raises(FreshnessGateError, match="NOT_BOUND"):
        assert_candidate_freshness_ready()


def test_release_false_blocks_publication_regardless_of_candidate():
    with pytest.raises(FreshnessGateError, match="living_cost_release_authorized"):
        assert_public_release_authorized()


def test_config_release_true_passes_release_gate_only(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=False, release=True)
    assert_public_release_authorized()
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()


def test_translation_index_bound_false_blocks_even_if_od010_validated(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    checks = _all_ready()
    checks["od010_price_index"] = _ready_family(
        "od010_price_index",
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
    )
    readiness = evaluate_freshness_readiness(checks)
    assert readiness["translation_index_bound"] is False
    assert "OD010_TRANSLATION_INDEX_NOT_BOUND" in readiness["blockers"]
    assert readiness["ready_for_private_candidate"] is False
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    with pytest.raises(FreshnessGateError, match="OD010_TRANSLATION_INDEX_NOT_BOUND"):
        _validate_candidate_checks(checks)


def test_not_checked_is_not_encoded_as_newer_data_false():
    check = _ready_family(
        "mobile_price",
        freshness_check_status="SOURCE_GAP",
        newer_data_exists=None,
        retrieval_validation_status="SOURCE_GAP",
        selected_vintage=None,
        selected_artifact=None,
        selected_artifacts=(),
    )
    assert check.newer_data_exists is None
    assert check.freshness_check_status == "SOURCE_GAP"


def test_modeled_evidence_requires_concrete_provenance(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    checks = _all_ready()
    checks["usda_food"] = _ready_family(
        "usda_food",
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        selected_vintage="target-year monthly reports / YTD",
        selected_artifact="usda food-plan monthly reports",
        selected_artifacts=(),
        freshness_check_status="VERIFIED_CURRENT",
    )
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    with pytest.raises(FreshnessGateError, match="concrete provenance"):
        _validate_candidate_checks(checks)


def test_pipeline_reads_canonical_authorization():
    pipeline = (SRC / "foundation" / "pipeline.py").read_text(encoding="utf-8")
    assert "from foundation.living_cost.freshness import" in pipeline
    assert "candidate_calculation_authorized()" in pipeline
    assert "living_cost_release_authorized()" in pipeline
    assert "candidate_calculation_authorized = False" not in pipeline
    assert "Public living-cost release engine is not implemented/approved." in pipeline
    assert "Living-cost publication is not authorized." not in pipeline
    assert "assert_candidate_freshness_ready({}," not in pipeline.replace(" ", "")
    assert "run_candidate_readiness_gate(" in (
        SRC / "foundation" / "living_cost" / "freshness.py"
    ).read_text(encoding="utf-8")


def test_production_artifact_still_fails_and_uses_discovery_fields():
    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    assert payload["ready_for_private_candidate"] is False
    assert payload["candidate_calculation_authorized"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["translation_index_bound"] is False
    assert "OD010_TRANSLATION_INDEX_NOT_BOUND" in payload["blockers"]
    assert payload["authorization_source"] == "config/definitions.yml"
    usda = payload["checks"]["usda_food"]
    assert usda["retrieval_validation_status"] == "MODELED_FROM_MEASURED_INPUTS"
    assert isinstance(usda.get("selected_artifacts"), list)
    extra = usda.get("extra") or {}
    assert "historical_2024" in extra
    assert "current_2026" in extra
    if extra["historical_2024"].get("month_count") == 12:
        assert extra["current_2026"].get("months_included") != extra["historical_2024"].get(
            "months_included"
        )
    cms = payload["checks"]["cms_marketplace_sbe"]
    assert isinstance(cms.get("selected_artifacts"), list)
    for family, check in payload["checks"].items():
        assert "freshness_check_status" in check, family
        assert check["freshness_check_status"] in {
            "VERIFIED_CURRENT",
            "NEWER_AVAILABLE",
            "CHECK_FAILED",
            "MANUAL_VERIFICATION_REQUIRED",
            "SOURCE_GAP",
        }
        if check["freshness_check_status"] in {"SOURCE_GAP", "CHECK_FAILED"}:
            assert check["newer_data_exists"] is None, family


def test_empirical_blockers_unchanged():
    coverage = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    for year in ("2024", "2026"):
        row = coverage["coverage_by_year"][year]
        assert row["health_oop"] == "RETRIEVED_UNVALIDATED"
        assert row["mpg"] == "RETRIEVED_UNVALIDATED"
        assert row["insurance"] == "RETRIEVED_UNVALIDATED"
        assert row["maintenance"] == "INCOMPLETE_PROVENANCE"
        assert row["essentials"] == "INCOMPLETE_PROVENANCE"
        assert row["recreation"] == "INCOMPLETE_PROVENANCE"
        assert row["registration"] == "SOURCE_GAP"
        assert row["replacement"] == "FORMULA_FROZEN_INPUTS_PENDING"
        assert row["connectivity"] == "SOURCE_GAP"
        assert row["federal_tax"] == "INVENTORY_NOT_VALIDATED"
        assert row["state_tax"] == "SOURCE_GAP"
        assert row["local_tax"] == "SOURCE_GAP"
    assert is_translation_index_bound() is False


def test_meps_scheduled_is_not_released_on_synthetic_listing():
    from foundation.sources.meps import check_meps_2024_full_year_listing

    html = "<html>HC-251 Full Year Consolidated 2023. Schedule AUGUST 2026.</html>"
    result = check_meps_2024_full_year_listing(listing_html=html)
    assert result["released"] is False
    assert result["listed_puf_id"] is None


def test_usda_2024_full_year_cannot_overwrite_2026_ytd():
    from foundation.living_cost.freshness_discovery import usda_year_month_records

    artifacts = [
        {
            "source_id": "usda_food_low_cost_2024",
            "notes": "months_included=['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']",
            "sha256": "aaaa",
        },
        {
            "source_id": "usda_food_low_cost_2026",
            "notes": "months_included=['January', 'February', 'March', 'April', 'May']",
            "sha256": "bbbb",
        },
    ]
    years = usda_year_month_records(artifacts)
    assert years[2024]["month_count"] == 12
    assert years[2026]["month_count"] == 5
    assert years[2026]["months_included"] != years[2024]["months_included"]
    assert years[2026]["last_month"] == "May"
    assert years[2024]["last_month"] == "December"


def test_usda_hrefs_are_parsed_not_constructed_fna():
    from foundation.living_cost.freshness_discovery import parse_usda_official_hrefs

    html = """
    <a href="/sites/default/files/resource-files/usda-lowcostplan-sept2007-present.xlsx">Low-Cost</a>
    <a href="https://www.fns.usda.gov/sites/default/files/resource-files/usda-thriftyplan-june2021-present.xlsx">Thrifty</a>
    """
    found = parse_usda_official_hrefs(
        html, page_url="https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"
    )
    assert "usda-lowcostplan-sept2007-present.xlsx" in found
    assert found["usda-lowcostplan-sept2007-present.xlsx"].startswith("https://www.fns.usda.gov/")
    assert "fna.usda.gov" not in found["usda-lowcostplan-sept2007-present.xlsx"]
    assert "fna.usda.gov" not in found["usda-thriftyplan-june2021-present.xlsx"]
    src = (SRC / "foundation" / "living_cost" / "freshness_discovery.py").read_text(
        encoding="utf-8"
    )
    assert "https://www.fna.usda.gov/sites/default/files/resource-files/" not in src
    usda_src = (SRC / "foundation" / "sources" / "usda_food.py").read_text(encoding="utf-8")
    manifest_src = (SRC / "foundation" / "living_cost" / "manifest.py").read_text(encoding="utf-8")
    assert "fna.usda.gov" not in usda_src
    assert "fna.usda.gov" not in manifest_src
    assert "research-actuarial-services/auto-insurance-database-report" not in manifest_src


def test_cms_federal_success_sbe_failure_is_not_verified(monkeypatch: pytest.MonkeyPatch):
    from foundation.living_cost import freshness_discovery as disc
    from foundation.sources.cms_marketplace import CMS_SBE_PUF_LANDING

    def fake_fetch(url: str, **_kwargs: object):
        if url == CMS_SBE_PUF_LANDING:
            raise RuntimeError("sbe listing unavailable")
        return (
            "<html>Health Insurance Exchange Public Use Files 2024 2026 rate-puf</html>",
            "2026-08-15T00:00:00Z",
        )

    monkeypatch.setattr(disc, "fetch_text", fake_fetch)
    check = disc.discover_cms()
    assert check.freshness_check_status != "VERIFIED_CURRENT"
    extra = check.extra or {}
    assert extra["federal_exchange"]["status"] == "VERIFIED_CURRENT"
    assert extra["sbe"]["status"] == "CHECK_FAILED"


def test_cms_federal_and_sbe_success_may_be_verified(monkeypatch: pytest.MonkeyPatch):
    from foundation.living_cost import freshness_discovery as disc

    def fake_fetch(url: str, **_kwargs: object):
        return (
            "<html>Health Insurance Exchange Public Use Files 2024 2026 PUF</html>",
            "2026-08-15T00:00:00Z",
        )

    monkeypatch.setattr(disc, "fetch_text", fake_fetch)
    check = disc.discover_cms()
    extra = check.extra or {}
    assert extra["federal_exchange"]["status"] == "VERIFIED_CURRENT"
    assert extra["sbe"]["status"] == "VERIFIED_CURRENT"
    assert check.listing_freshness_status == "VERIFIED_CURRENT"
    assert check.freshness_check_status != "VERIFIED_CURRENT" or (
        check.artifact_currentness_status == "VERIFIED_CURRENT"
    )
    assert check.artifact_currentness_status in {
        "CHECK_FAILED",
        "VERIFIED_CURRENT",
        "NEWER_AVAILABLE",
    }


def test_naic_does_not_use_obsolete_404_landing():
    from foundation.living_cost.freshness_discovery import NAIC_PUBLICATIONS_LANDING

    src = (SRC / "foundation" / "living_cost" / "freshness_discovery.py").read_text(
        encoding="utf-8"
    )
    assert "research-actuarial-services/auto-insurance-database-report" not in src
    assert "content.naic.org/publications" in NAIC_PUBLICATIONS_LANDING


def test_status_summary_cannot_label_bea_verified_when_artifact_says_failed():
    from foundation.living_cost.freshness import freshness_status_summary

    payload = {
        "ready_for_private_candidate": False,
        "empirical_blocker_family_count": 12,
        "gate_blocker_reason_count": 20,
        "checks": {
            "bea_rpp": {"freshness_check_status": "CHECK_FAILED"},
        },
    }
    text = freshness_status_summary(payload)
    assert "bea_rpp: CHECK_FAILED" in text
    assert "bea_rpp: VERIFIED_CURRENT" not in text


def test_blocker_counts_are_separated():
    readiness = evaluate_freshness_readiness(_all_ready())
    assert "empirical_blocker_family_count" in readiness
    assert "gate_blocker_reason_count" in readiness
    assert readiness["gate_blocker_reason_count"] == readiness["blocker_count"]
    assert readiness["empirical_blocker_family_count"] == 0


def test_public_gate_cannot_override_required_families_or_translation():
    import inspect

    params = inspect.signature(assert_candidate_freshness_ready).parameters
    assert "checks" not in params
    assert "required_families" not in params
    assert "translation_index_bound" not in params
    assert "silent_source_year_relabel" not in params
    assert "candidate_inputs_bound" not in params
    assert "project_cost_year" not in params
    public_params = inspect.signature(run_candidate_readiness_gate).parameters
    assert "checks" not in public_params
    eval_params = inspect.signature(evaluate_freshness_readiness).parameters
    assert "translation_index_bound" not in eval_params
    assert "candidate_inputs_bound" not in eval_params
    src = (SRC / "foundation" / "living_cost" / "freshness.py").read_text(encoding="utf-8")
    assert "del project_cost_year" not in src
    assert "REQUIRED_FRESHNESS_FAMILIES" in src.split("def _validate_candidate_checks")[1][:2500]
    assert "current_family_truth()" in src.split("def run_candidate_readiness_gate")[1][:1500]


def test_empty_required_family_bypass_is_impossible(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    with pytest.raises(FreshnessGateError, match="required freshness check was not performed"):
        _validate_candidate_checks({})
    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", dict)
    with pytest.raises(FreshnessGateError, match="required freshness check was not performed"):
        run_candidate_readiness_gate()


def test_candidate_inputs_bound_false_blocks_assertion_gate(
    monkeypatch: pytest.MonkeyPatch,
):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    assert are_candidate_inputs_bound() is False
    with pytest.raises(FreshnessGateError, match="REQUIRED_CANDIDATE_INPUTS_NOT_BOUND"):
        _validate_candidate_checks(_all_ready())


def test_project_year_bundle_is_validated_not_ignored(monkeypatch: pytest.MonkeyPatch):
    from foundation.living_cost.freshness import required_project_cost_years

    assert list(required_project_cost_years()) == [2024, 2026]
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    checks = _all_ready()
    checks["usda_food"] = _ready_family(
        "usda_food",
        year_coverage={"2024": {"covered": True}, "2026": {"covered": False}},
    )
    with pytest.raises(FreshnessGateError, match="required project cost year"):
        _validate_candidate_checks(checks)


def test_cached_usda_may_plus_official_june_is_newer_available():
    from foundation.living_cost.freshness_currentness import usda_currentness_status

    result = usda_currentness_status(
        official_latest=(2026, 6),
        selected_latest=(2026, 5),
        official_sha="aaa",
        selected_sha="aaa",
    )
    assert result["freshness_check_status"] == "NEWER_AVAILABLE"
    assert result["selected_artifact_matches_latest"] is False


def test_stable_usda_url_changed_bytes_cannot_stay_verified():
    from foundation.living_cost.freshness_currentness import usda_currentness_status

    result = usda_currentness_status(
        official_latest=(2026, 5),
        selected_latest=(2026, 5),
        official_sha="new-bytes",
        selected_sha="old-bytes",
    )
    assert result["freshness_check_status"] != "VERIFIED_CURRENT"
    assert result["freshness_check_status"] == "NEWER_AVAILABLE"


def test_stable_eia_url_newer_observation_cannot_stay_verified():
    from datetime import date

    from foundation.living_cost.freshness_currentness import eia_currentness_status

    result = eia_currentness_status(
        official_max_date=date(2026, 8, 10),
        selected_max_date=date(2026, 5, 1),
        official_sha="aaa",
        selected_sha="aaa",
    )
    assert result["freshness_check_status"] == "NEWER_AVAILABLE"
    assert result["freshness_check_status"] != "VERIFIED_CURRENT"


def test_generic_naic_title_without_year_cannot_be_verified_current(
    monkeypatch: pytest.MonkeyPatch,
):
    from foundation.living_cost import freshness_discovery as disc
    from foundation.living_cost.freshness_currentness import parse_naic_report_identifier

    ident = parse_naic_report_identifier("<html>Auto Insurance Database Report</html>")
    assert ident is None

    def fake_fetch(url: str, **_kwargs: object):
        return ("<html>Auto Insurance Database Report</html>", "2026-08-15T00:00:00Z")

    monkeypatch.setattr(disc, "fetch_text", fake_fetch)
    check = disc.discover_naic()
    assert check.freshness_check_status != "VERIFIED_CURRENT"
    assert check.freshness_check_status == "CHECK_FAILED"
    assert check.latest_authoritative_vintage_found in {
        None,
        "NAIC Auto Insurance Database Report",
    }


def test_naic_listing_selects_highest_ending_year():
    from foundation.living_cost.freshness_currentness import (
        parse_naic_report_identifiers,
        select_latest_naic_report,
    )

    html = """
    Auto Insurance Database Report 2021-2022
    AUT-PB 2022-2023
    2020/2021 Auto Insurance Database Report
    """
    reports = parse_naic_report_identifiers(html)
    latest = select_latest_naic_report(reports)
    assert latest is not None
    assert latest.end_year == 2023
    assert latest.start_year == 2022
    assert latest.display_identifier == "AUT-PB 2022-2023"


def test_duplicate_gate_reasons_are_counted_once():
    checks = _all_ready()
    checks["mobile_price"] = _ready_family(
        "mobile_price",
        freshness_check_status="SOURCE_GAP",
        retrieval_validation_status="SOURCE_GAP",
        newer_data_exists=None,
        selected_vintage=None,
        selected_artifact=None,
        selected_artifacts=(),
        year_coverage={
            "2024": {"covered": False},
            "2026": {"covered": False},
        },
    )
    readiness = evaluate_freshness_readiness(checks)
    reasons = [r for r in readiness["blockers"] if r == "mobile_price:SOURCE_GAP"]
    assert reasons == ["mobile_price:SOURCE_GAP"]
    assert readiness["gate_blocker_reason_count"] == len(set(readiness["blockers"]))
    assert readiness["blocker_count"] == len(readiness["blockers"])
