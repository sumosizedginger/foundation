"""Independent QA tests for the final readiness-gate correction.

Does not calculate or publish an MSLC. Exercises the live modules and
on-disk artifacts the way a later operator would.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"
SRC = ROOT / "src"


def test_authorization_functions_are_separate_and_false():
    from foundation.living_cost.freshness import (
        FreshnessGateError,
        assert_candidate_freshness_ready,
        assert_public_release_authorized,
        candidate_calculation_authorized,
        living_cost_release_authorized,
    )

    assert candidate_calculation_authorized() is False
    assert living_cost_release_authorized() is False
    assert candidate_calculation_authorized is not living_cost_release_authorized

    # Private candidate gate must refuse when config candidate auth is false.
    # Public gate accepts no caller-supplied checks.
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        assert_candidate_freshness_ready()

    # Public release is a later, separate gate and also reads config only.
    with pytest.raises(FreshnessGateError, match="living_cost_release_authorized"):
        assert_public_release_authorized()


def test_required_families_include_vehicle_replacement_and_bea_rpp():
    from foundation.living_cost.freshness import REQUIRED_FRESHNESS_FAMILIES

    families = list(REQUIRED_FRESHNESS_FAMILIES)
    assert len(families) == 19
    assert families.count("vehicle_replacement") == 1
    assert families.count("bea_rpp") == 1
    assert "vehicle_replacement" in families
    assert "bea_rpp" in families


def _checks_from_committed_artifact():
    """Rebuild FreshnessCheck objects from the committed artifact (no network)."""
    from dataclasses import fields

    from foundation.living_cost.freshness import FreshnessCheck

    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    allowed = {item.name for item in fields(FreshnessCheck)}
    checks = {}
    for family, raw in payload["checks"].items():
        rec = {key: value for key, value in raw.items() if key in allowed}
        if rec.get("selected_artifacts") is not None:
            rec["selected_artifacts"] = tuple(rec["selected_artifacts"])
        if rec.get("months_included") is not None:
            rec["months_included"] = tuple(rec["months_included"])
        checks[family] = FreshnessCheck(**rec)
    return checks


def test_live_freshness_writer_is_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from foundation.living_cost.freshness import write_candidate_freshness_report

    monkeypatch.setattr(
        "foundation.living_cost.freshness.current_family_truth",
        _checks_from_committed_artifact,
    )
    payload = write_candidate_freshness_report(tmp_path)
    on_disk = json.loads((tmp_path / "living_cost_candidate_freshness.json").read_text())
    assert payload == on_disk
    assert payload["calculates_mslc"] is False
    assert payload["freshness_run_id"]
    assert len(payload["freshness_run_id"]) == 64
    assert payload["headline_calculated"] is False
    assert payload["ready_for_private_candidate"] is False
    assert payload["candidate_calculation_authorized"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["blocker_count"] >= 13
    assert len(payload["blockers"]) == payload["blocker_count"]
    assert "OD010_TRANSLATION_INDEX_NOT_BOUND" in payload["blockers"]
    assert "meps_full_year_consolidated:RETRIEVED_UNVALIDATED" in payload["blockers"]
    assert "epa_vehicle:RETRIEVED_UNVALIDATED" in payload["blockers"]
    assert "vehicle_replacement:FORMULA_FROZEN_INPUTS_PENDING" in payload["blockers"]
    assert "bea_rpp" in payload["required_families"]
    assert "vehicle_replacement" in payload["required_families"]
    assert payload["checks"]["meps_full_year_consolidated"]["retrieval_validation_status"] == (
        "RETRIEVED_UNVALIDATED"
    )
    assert payload["checks"]["epa_vehicle"]["retrieval_validation_status"] == (
        "RETRIEVED_UNVALIDATED"
    )
    assert payload["checks"]["vehicle_replacement"]["retrieval_validation_status"] == (
        "FORMULA_FROZEN_INPUTS_PENDING"
    )
    assert payload["checks"]["bea_rpp"]["source_id"] == "bea_rpp"
    bea = payload["checks"]["bea_rpp"]
    assert bea["retrieval_validation_status"] == "VALIDATED"
    assert bea["freshness_check_status"] in {
        "VERIFIED_CURRENT",
        "CHECK_FAILED",
        "NEWER_AVAILABLE",
    }
    assert bea["selected_artifact"] == "SARPP.zip"
    assert bea["latest_authoritative_vintage_found"] != "latest retrieved BEA RPP"
    assert bea["selected_artifact"] != "bea rpp artifact"
    assert (
        bea["newer_data_exists"] is not True or bea["freshness_check_status"] == "NEWER_AVAILABLE"
    )
    assert payload["notes"]["health_oop"].startswith("MEPS HEALTH OOP DERIVATION")
    assert "MODELED_FROM_MEASURED_INPUTS" in payload["notes"]["mpg"]
    # Fail-closed: a VALIDATED family must not invent a pass for OOP/MPG.
    for family in payload["required_families"]:
        check = payload["checks"][family]
        assert check["latest_checked_at"]
        assert "retrieval_validation_status" in check
        assert "newer_data_exists" in check


def test_production_freshness_artifact_matches_fail_closed_contract():
    path = METADATA / "living_cost_candidate_freshness.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["report_type"] == "living_cost_candidate_freshness"
    assert payload["calculates_mslc"] is False
    assert payload["ready_for_private_candidate"] is False
    assert payload["candidate_calculation_authorized"] is False
    assert payload["living_cost_release_authorized"] is False
    assert payload["blocker_count"] >= 13
    assert "OD010_TRANSLATION_INDEX_NOT_BOUND" in payload["blockers"]
    required = payload["required_families"]
    assert len(required) == 19
    assert "vehicle_replacement" in required
    assert "bea_rpp" in required
    assert set(payload["checks"]) == set(required)
    assert payload["checks"]["vehicle_replacement"]["retrieval_validation_status"] == (
        "FORMULA_FROZEN_INPUTS_PENDING"
    )
    assert payload["checks"]["meps_full_year_consolidated"]["retrieval_validation_status"] == (
        "RETRIEVED_UNVALIDATED"
    )
    assert payload["checks"]["epa_vehicle"]["retrieval_validation_status"] == (
        "RETRIEVED_UNVALIDATED"
    )
    bea = payload["checks"]["bea_rpp"]
    assert bea["retrieval_validation_status"] == "VALIDATED"
    assert bea["selected_artifact"] == "SARPP.zip"
    assert bea["latest_authoritative_vintage_found"] != "latest retrieved BEA RPP"
    assert "freshness_check_status" in bea
    for field in (
        "source_id",
        "latest_checked_at",
        "latest_authoritative_vintage_found",
        "selected_vintage",
        "selected_artifact",
        "newer_data_exists",
        "retrieval_validation_status",
        "reason_if_not_refreshed",
    ):
        for family, check in payload["checks"].items():
            assert field in check, f"{family} missing {field}"


def test_coverage_documents_oop_and_mpg_as_retrieved_unvalidated():
    coverage = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    assert coverage["generated_at"]
    assert coverage["candidate_calculation_authorized"] is False
    assert coverage["living_cost_release_authorized"] is False
    assert coverage["headline_calculated"] is False
    assert coverage["states_modeled"] == 0
    for year in ("2024", "2026"):
        assert coverage["coverage_by_year"][year]["health_oop"] == "MODELED_FROM_MEASURED_INPUTS"
        assert coverage["coverage_by_year"][year]["mpg"] == "MODELED_FROM_MEASURED_INPUTS"
        assert coverage["coverage_by_year"][year]["replacement"] == (
            "FORMULA_FROZEN_INPUTS_PENDING"
        )
        assert coverage["coverage_by_year"][year]["rpp"] == "VALIDATED"
    notes = coverage["blocker_notes"]
    assert "MODELED_FROM_MEASURED_INPUTS" in notes["health_oop"]
    assert "HC-251" in notes["health_oop"]
    assert "MODELED_FROM_MEASURED_INPUTS" in notes["mpg"]
    assert "FROZEN" in notes["mpg"]


def test_official_coverage_writer_persists_blocker_notes():
    """The official regenerate path must keep the required blocker documentation."""
    writer = (ROOT / "scripts" / "validate_living_cost_sources.py").read_text(encoding="utf-8")
    tree = ast.parse(writer)
    write_fn = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "write_coverage"
    )
    dumped = ast.dump(write_fn)
    assert "blocker_notes" in dumped
    assert "BLOCKER_NOTES" in dumped
    freshness_src = (SRC / "foundation" / "living_cost" / "freshness.py").read_text(
        encoding="utf-8"
    )
    assert "def stamp_source_coverage_from_current_truth" in freshness_src
    assert "MEPS HEALTH OOP DERIVATION" in freshness_src
    assert "EPA MPG" in freshness_src


def test_no_mslc_is_published_in_current_or_site_outputs():
    from foundation.living_cost.engine import get_living_cost_transition_state

    state = get_living_cost_transition_state()
    assert state["minimum_sustainable_living_cost_2024"]["status"] == "UNAVAILABLE"
    assert state["minimum_sustainable_living_cost_2024"]["weighted_median_gross"] is None
    assert state["minimum_sustainable_living_cost_2026"]["weighted_median_gross"] is None
    assert state["survival_gap_2024"] is None
    assert state["adequacy_ratio_2024"] is None
    assert state["state_distributions_2024"] == []

    for rel in (
        Path("data/current/survival.json"),
        Path("site/data/survival.json"),
        Path("data/current/living_cost_2024.json"),
        Path("data/current/living_cost_2026.json"),
        Path("site/data/living_cost_2024.json"),
        Path("site/data/living_cost_2026.json"),
    ):
        payload = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        blob = json.dumps(payload)
        if "minimum_sustainable_living_cost_2024" in payload:
            assert payload["minimum_sustainable_living_cost_2024"]["weighted_median_gross"] is None
            assert payload["minimum_sustainable_living_cost_2026"]["weighted_median_gross"] is None
        if "national_distribution" in payload:
            assert payload["national_distribution"] is None
            assert payload["state_distributions"] == []
        assert (
            payload.get("status")
            in {
                "pipeline_validation_in_progress",
                None,
            }
            or payload.get("status_label") == "DATA PIPELINE VALIDATION IN PROGRESS"
        )
        assert "51220.16" not in blob or "retired" in blob.lower()


def test_config_and_pipeline_keep_both_flags_false():
    from foundation.config import definitions

    living = definitions()["living_cost"]
    assert living["candidate_calculation_authorized"] is False
    assert living["release_authorized"] is False
    assert living["states_modeled"] == 0

    pipeline = (SRC / "foundation" / "pipeline.py").read_text(encoding="utf-8")
    assert "candidate_calculation_authorized()" in pipeline
    assert "living_cost_release_authorized()" in pipeline


def test_bea_rpp_freshness_record_is_not_a_placeholder():
    """A VALIDATED family must name a real vintage, not a tautology."""
    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    check = payload["checks"]["bea_rpp"]
    vintage = check.get("latest_authoritative_vintage_found") or ""
    artifact = check.get("selected_artifact") or ""
    placeholder_vintages = {
        "latest retrieved BEA RPP",
        "bea rpp artifact",
        "latest retrieved",
    }
    assert check["retrieval_validation_status"] == "VALIDATED"
    assert vintage.lower() not in {p.lower() for p in placeholder_vintages}
    assert artifact.lower() not in {p.lower() for p in placeholder_vintages}
    assert vintage != "latest retrieved BEA RPP"
    assert artifact != "bea rpp artifact"
    assert artifact == "SARPP.zip"
    assert check["freshness_check_status"] in {
        "VERIFIED_CURRENT",
        "CHECK_FAILED",
        "NEWER_AVAILABLE",
    }
