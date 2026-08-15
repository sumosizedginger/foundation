"""Behavioral tests for live candidate-gate trust binding.

Does not calculate or publish an MSLC. Does not build the assembler.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from foundation.living_cost.candidate_bindings import (
    CONNECTIVITY_SUBCOMPONENTS,
    evaluate_candidate_input_bindings,
    evaluate_od010_translation_table,
    required_candidate_components,
    required_cpi_updated_bindings,
)
from foundation.living_cost.freshness import (
    MUTABLE_SOURCE_FAMILIES,
    REQUIRED_FRESHNESS_FAMILIES,
    FreshnessCheck,
    FreshnessGateError,
    _validate_candidate_checks,
    are_candidate_inputs_bound,
    assert_candidate_freshness_ready,
    candidate_calculation_authorized,
    evaluate_freshness_readiness,
    is_translation_index_bound,
    missing_project_cost_years,
    required_project_cost_years,
    run_candidate_readiness_gate,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"


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


def _patch_living_auth(monkeypatch: pytest.MonkeyPatch, *, candidate: bool, release: bool) -> None:
    from foundation.config import definitions as real_defs

    base = real_defs()
    living = dict(base["living_cost"])
    living["candidate_calculation_authorized"] = candidate
    living["release_authorized"] = release
    patched = {**base, "living_cost": living}
    monkeypatch.setattr("foundation.config.definitions", lambda: patched)


def _complete_binding(component: str, year: int) -> dict[str, object]:
    from foundation.living_cost.candidate_bindings import (
        COMPONENT_FRESHNESS_FAMILY,
        expected_translation_method,
    )

    family = COMPONENT_FRESHNESS_FAMILY[component]
    method_component = "connectivity" if component in CONNECTIVITY_SUBCOMPONENTS else component
    method = expected_translation_method(method_component, year)
    source_year = year - 1 if method == "CPI_UPDATED" else year
    rec: dict[str, object] = {
        "component": component,
        "project_cost_year": year,
        "source_id": family,
        "source_family": family,
        "source_data_year": source_year,
        "selected_artifacts": [
            {
                "artifact_id": f"{family}.bin",
                "sha256": "abc",
            }
        ],
        "model_method": "official",
        "evidence_status": "VALIDATED",
        "translation_method": method,
    }
    if method == "CPI_UPDATED":
        rec["od010_record_identity"] = {
            "component": component,
            "project_cost_year": year,
            "sha256": "d" * 64,
        }
    if component == "connectivity":
        rec["sub_bindings"] = {
            sub: _complete_binding(sub, year) for sub in CONNECTIVITY_SUBCOMPONENTS
        }
    return rec


def _complete_inputs() -> dict[str, object]:
    years = required_project_cost_years()
    inputs = {}
    for component in required_candidate_components():
        inputs[component] = {str(year): _complete_binding(component, year) for year in years}
    return {"inputs": inputs}


def _complete_translation_record(component: str, year: int) -> dict[str, object]:
    return {
        "component": component,
        "source_data_year": year - 1 if year > 2000 else year,
        "project_cost_year": year,
        "official_series_identifier": f"CUSR0000-{component}",
        "publisher": "BLS",
        "observation_period": f"{year} annual",
        "source_artifact": f"https://api.bls.gov/publicAPI/v2/timeseries/{component}",
        "translation_factor": 1.02,
        "retrieval_validation_state": "VALIDATED",
    }


def test_public_candidate_gate_has_no_checks_parameter():
    for fn in (assert_candidate_freshness_ready, run_candidate_readiness_gate):
        params = inspect.signature(fn).parameters
        assert list(params) == []
        assert "checks" not in params


def test_stale_synthetic_checks_cannot_be_injected():
    with pytest.raises(TypeError):
        run_candidate_readiness_gate(_all_ready())  # type: ignore[misc]
    with pytest.raises(TypeError):
        assert_candidate_freshness_ready(_all_ready())  # type: ignore[misc]


def test_public_gate_calls_current_family_truth(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    called = {"n": 0}
    live = _all_ready()

    def provider() -> dict[str, FreshnessCheck]:
        called["n"] += 1
        return live

    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", provider)
    with pytest.raises(FreshnessGateError, match="NOT_BOUND"):
        run_candidate_readiness_gate()
    assert called["n"] == 1


def test_candidate_auth_false_stops_before_discovery(monkeypatch: pytest.MonkeyPatch):
    assert candidate_calculation_authorized() is False
    called = {"n": 0}

    def provider() -> dict[str, FreshnessCheck]:
        called["n"] += 1
        return _all_ready()

    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", provider)
    with pytest.raises(FreshnessGateError, match="candidate_calculation_authorized"):
        run_candidate_readiness_gate()
    assert called["n"] == 0


def test_discovery_failure_blocks_candidate(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)

    def boom() -> dict[str, FreshnessCheck]:
        raise RuntimeError("landing page connection reset")

    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", boom)
    with pytest.raises(FreshnessGateError, match="live discovery failed"):
        run_candidate_readiness_gate()


def test_successful_live_discovery_is_exact_snapshot_returned(monkeypatch: pytest.MonkeyPatch):
    _patch_living_auth(monkeypatch, candidate=True, release=False)
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    live = _all_ready()
    monkeypatch.setattr("foundation.living_cost.freshness.current_family_truth", lambda: live)
    with pytest.raises(FreshnessGateError, match="NOT_BOUND"):
        run_candidate_readiness_gate()
    from foundation.living_cost.freshness import build_live_readiness_context, snapshot_from_context

    snapshot = snapshot_from_context(
        build_live_readiness_context(live, candidate_payload=None, od010_payload=None)
    )
    assert snapshot["required_project_cost_years"] == [2024, 2026]
    assert snapshot["calculates_mslc"] is False
    assert len(snapshot["freshness_run_id"]) == 64
    assert (
        snapshot["checks"]["usda_food"]["selected_artifact"] == live["usda_food"].selected_artifact
    )


def test_freshness_run_id_is_stable_for_same_core():
    from foundation.living_cost.freshness import compute_freshness_run_id

    core = {
        "generated_at": "2026-08-15T00:00:00Z",
        "required_project_cost_years": [2024, 2026],
        "checks": {"usda_food": {"selected_artifact": "a.xlsx", "artifact_hashes": []}},
        "od010_binding_identity": {"bound": False},
        "candidate_input_binding_identity": {"bound": False},
    }
    first = compute_freshness_run_id(core)
    second = compute_freshness_run_id(core)
    assert first == second
    changed = dict(core)
    changed["generated_at"] = "2026-08-15T00:00:01Z"
    assert compute_freshness_run_id(changed) != first


def test_year_coverage_requires_explicit_covered_true():
    years = (2024, 2026)
    absent = _ready_family("usda_food", year_coverage={"2024": {"covered": True}})
    assert missing_project_cost_years(absent, years) == [2026]

    false_flag = _ready_family(
        "usda_food",
        year_coverage={"2024": {"covered": True}, "2026": False},
    )
    assert missing_project_cost_years(false_flag, years) == [2026]

    covered_false = _ready_family(
        "usda_food",
        year_coverage={"2024": {"covered": True}, "2026": {"covered": False}},
    )
    assert missing_project_cost_years(covered_false, years) == [2026]

    empty = _ready_family(
        "usda_food",
        year_coverage={"2024": {"covered": True}, "2026": {}},
    )
    assert missing_project_cost_years(empty, years) == [2026]

    ok = _ready_family(
        "usda_food",
        year_coverage={"2024": {"covered": True}, "2026": {"covered": True, "note": "ytd"}},
    )
    assert missing_project_cost_years(ok, years) == []


def test_manual_bound_true_without_complete_records_is_unbound():
    fake = {"bound": True, "inputs": {"housing": {"note": "not a binding"}}}
    result = evaluate_candidate_input_bindings(fake, years=(2024, 2026))
    assert result["bound"] is False
    assert result["manual_bound_ignored"] is True
    assert "housing:2024" in result["missing"]
    assert "connectivity:2026" in result["missing"]


def test_production_candidate_inputs_remain_unbound():
    assert not (METADATA / "living_cost_candidate_input_bindings.json").exists()
    assert are_candidate_inputs_bound() is False


def test_complete_structural_bindings_derive_true():
    payload = _complete_inputs()
    payload["bound"] = False
    required = required_cpi_updated_bindings(years=(2024, 2026))
    od010 = {
        "series": [_complete_translation_record(component, year) for component, year in required]
    }
    result = evaluate_candidate_input_bindings(payload, od010_payload=od010)
    assert result["bound"] is True
    assert result["missing"] == []


def test_connectivity_requires_broadband_and_mobile_sub_bindings():
    payload = _complete_inputs()
    payload["inputs"]["connectivity"]["2024"].pop("sub_bindings")
    result = evaluate_candidate_input_bindings(payload, years=(2024, 2026))
    assert result["bound"] is False
    assert "connectivity:2024" in result["missing"]


def test_od010_manual_bound_true_is_not_enough():
    fake = {"bound": True, "series": {"foo": "CPI-U"}}
    result = evaluate_od010_translation_table(fake, years=(2024, 2026))
    assert result["bound"] is False
    assert result["manual_bound_ignored"] is True
    assert result["missing"]
    assert is_translation_index_bound() is False
    assert not (METADATA / "living_cost_od010_translation_table.json").exists()


def test_od010_required_pairs_come_from_source_lag():
    required = required_cpi_updated_bindings(years=(2024, 2026))
    pairs = set(required)
    assert ("health_oop", 2024) in pairs
    assert ("health_oop", 2026) in pairs
    assert ("insurance", 2024) in pairs
    assert ("insurance", 2026) in pairs
    assert ("maintenance", 2026) in pairs
    assert ("essentials", 2026) in pairs
    assert ("recreation", 2026) in pairs
    assert ("housing", 2024) not in pairs
    assert ("maintenance", 2024) not in pairs


def test_complete_od010_table_derives_bound_true():
    required = required_cpi_updated_bindings(years=(2024, 2026))
    series = [_complete_translation_record(component, year) for component, year in required]
    result = evaluate_od010_translation_table(
        {"bound": False, "series": series}, years=(2024, 2026)
    )
    assert result["bound"] is True
    assert result["missing"] == []


def test_mutable_verified_current_requires_artifact_currentness(
    monkeypatch: pytest.MonkeyPatch,
):
    checks = _all_ready()
    checks["usda_food"] = _ready_family(
        "usda_food",
        freshness_check_status="VERIFIED_CURRENT",
        listing_freshness_status="VERIFIED_CURRENT",
        artifact_currentness_status="CHECK_FAILED",
        selected_artifact_matches_latest=False,
    )
    readiness = evaluate_freshness_readiness(checks)
    assert "usda_food:MUTABLE_CURRENTNESS_INCONSISTENT" in readiness["blockers"]
    monkeypatch.setattr("foundation.living_cost.freshness.is_translation_index_bound", lambda: True)
    monkeypatch.setattr("foundation.living_cost.freshness.are_candidate_inputs_bound", lambda: True)
    with pytest.raises(FreshnessGateError, match="MUTABLE_CURRENTNESS|artifact"):
        _validate_candidate_checks(checks)


def test_mutable_families_are_the_rolling_sources():
    assert MUTABLE_SOURCE_FAMILIES == {
        "usda_food",
        "eia_gasoline",
        "epa_vehicle",
        "bea_rpp",
        "cms_marketplace_sbe",
        "naic_auto_insurance",
    }


def test_bea_status_text_derives_from_committed_artifact():
    from foundation.living_cost.freshness import freshness_status_summary

    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    bea = payload["checks"]["bea_rpp"]
    assert bea["retrieval_validation_status"] == "VALIDATED"
    status = bea["freshness_check_status"]
    text = freshness_status_summary(payload)
    assert f"bea_rpp: {status}" in text
    if status == "VERIFIED_CURRENT":
        assert bea["listing_freshness_status"] == "VERIFIED_CURRENT"
        assert bea["artifact_currentness_status"] == "VERIFIED_CURRENT"
        assert bea["selected_artifact_matches_latest"] is True


def test_check_failure_does_not_demote_validated_evidence():
    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    bea = payload["checks"]["bea_rpp"]
    assert bea["retrieval_validation_status"] == "VALIDATED"
    cms = payload["checks"]["cms_marketplace_sbe"]
    assert cms["retrieval_validation_status"] == "MODELED_FROM_MEASURED_INPUTS"
    assert cms["freshness_check_status"] == "CHECK_FAILED"


def test_authorization_and_bindings_remain_false():
    from foundation.config import definitions

    living = definitions()["living_cost"]
    assert living["candidate_calculation_authorized"] is False
    assert living["release_authorized"] is False
    assert list(required_project_cost_years()) == [2024, 2026]
    assert are_candidate_inputs_bound() is False
    assert is_translation_index_bound() is False
    payload = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    assert payload["ready_for_private_candidate"] is False
    coverage = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    assert coverage["states_modeled"] == 0
