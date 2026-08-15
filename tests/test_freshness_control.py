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
    assert_candidate_freshness_ready,
    assert_public_release_authorized,
    candidate_calculation_authorized,
    evaluate_freshness_readiness,
    is_translation_index_bound,
    living_cost_release_authorized,
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


def test_config_candidate_false_blocks_private_gate():
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready(_all_ready(), project_cost_year=2026)


def test_explicit_candidate_true_plus_freshness_fail_is_blocked():
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
    with pytest.raises(FreshnessGateError, match="SOURCE_GAP"):
        assert_candidate_freshness_ready(
            checks,
            project_cost_year=2026,
            candidate_calculation_authorized=True,
            translation_index_bound=True,
        )


def test_explicit_candidate_true_plus_freshness_pass_may_proceed():
    assert_candidate_freshness_ready(
        _all_ready(),
        project_cost_year=2026,
        candidate_calculation_authorized=True,
        translation_index_bound=True,
    )


def test_release_false_blocks_publication_regardless_of_candidate():
    with pytest.raises(FreshnessGateError, match="living_cost_release_authorized"):
        assert_public_release_authorized()
    assert_public_release_authorized(living_cost_release_authorized=True)


def test_translation_index_bound_false_blocks_even_if_od010_validated():
    checks = _all_ready()
    checks["od010_price_index"] = _ready_family(
        "od010_price_index",
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
    )
    readiness = evaluate_freshness_readiness(checks, translation_index_bound=False)
    assert readiness["translation_index_bound"] is False
    assert "OD010_TRANSLATION_INDEX_NOT_BOUND" in readiness["blockers"]
    assert readiness["ready_for_private_candidate"] is False
    with pytest.raises(FreshnessGateError, match="OD010_TRANSLATION_INDEX_NOT_BOUND"):
        assert_candidate_freshness_ready(
            checks,
            project_cost_year=2026,
            candidate_calculation_authorized=True,
            translation_index_bound=False,
        )


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


def test_modeled_evidence_requires_concrete_provenance():
    checks = _all_ready()
    checks["usda_food"] = _ready_family(
        "usda_food",
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        selected_vintage="target-year monthly reports / YTD",
        selected_artifact="usda food-plan monthly reports",
        selected_artifacts=(),
        freshness_check_status="VERIFIED_CURRENT",
    )
    with pytest.raises(FreshnessGateError, match="concrete provenance"):
        assert_candidate_freshness_ready(
            checks,
            project_cost_year=2026,
            candidate_calculation_authorized=True,
            translation_index_bound=True,
        )


def test_pipeline_reads_canonical_authorization():
    pipeline = (SRC / "foundation" / "pipeline.py").read_text(encoding="utf-8")
    assert "from foundation.living_cost.freshness import" in pipeline
    assert "candidate_calculation_authorized()" in pipeline
    assert "living_cost_release_authorized()" in pipeline
    assert "candidate_calculation_authorized = False" not in pipeline


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
    assert usda.get("months_included")
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
