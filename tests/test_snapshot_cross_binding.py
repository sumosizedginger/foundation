"""Behavioral tests for snapshot / input cross-binding.

Does not calculate or publish an MSLC. Does not build the assembler.
No live-network calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from foundation.living_cost.candidate_bindings import (
    COMPONENT_FRESHNESS_FAMILY,
    FROZEN_CPI_UPDATED_PAIRS,
    REQUIRED_CANDIDATE_COMPONENTS,
    CoverageAuthorityError,
    SourceLagAuthorityError,
    assert_canonical_component_universe,
    assert_source_lag_preserves_frozen_od010,
    evaluate_candidate_input_bindings,
    expected_translation_method,
    required_candidate_components,
    required_cpi_updated_bindings,
    validate_candidate_bindings_against_snapshot,
)
from foundation.living_cost.freshness import (
    REQUIRED_FRESHNESS_FAMILIES,
    FreshnessCheck,
    FreshnessGateError,
    authorizing_state_core,
    build_live_readiness_context,
    compute_freshness_run_id,
    snapshot_from_context,
    validate_readiness_context,
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


def _od010_record(component: str, year: int) -> dict[str, object]:
    return {
        "component": component,
        "source_data_year": year - 1,
        "project_cost_year": year,
        "official_series_identifier": f"CUSR0000-{component}",
        "publisher": "BLS",
        "observation_period": f"{year} annual",
        "source_artifact": f"https://api.bls.gov/publicAPI/v2/timeseries/{component}",
        "translation_factor": 1.02,
        "retrieval_validation_state": "VALIDATED",
    }


def _complete_od010() -> dict[str, object]:
    return {
        "series": [_od010_record(component, year) for component, year in FROZEN_CPI_UPDATED_PAIRS]
    }


def _binding(component: str, year: int, **overrides: object) -> dict[str, object]:
    family = COMPONENT_FRESHNESS_FAMILY[component]
    method_component = "connectivity" if component in {"broadband", "mobile"} else component
    method = expected_translation_method(method_component, year)
    rec: dict[str, object] = {
        "component": component,
        "project_cost_year": year,
        "source_id": family,
        "source_family": family,
        "source_data_year": year - 1 if method == "CPI_UPDATED" else year,
        "selected_artifacts": [{"artifact_id": f"{family}.bin", "sha256": "abc"}],
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
    rec.update(overrides)
    return rec


def _complete_inputs(**component_overrides: object) -> dict[str, object]:
    inputs: dict[str, object] = {}
    for component in required_candidate_components():
        years: dict[str, object] = {}
        for year in (2024, 2026):
            rec = _binding(component, year)
            if component == "connectivity":
                rec["sub_bindings"] = {
                    "broadband": _binding("broadband", year),
                    "mobile": _binding("mobile", year),
                }
            years[str(year)] = rec
        inputs[component] = years
    for key, value in component_overrides.items():
        inputs[key] = value
    return {"inputs": inputs}


def test_artifact_sha_mismatch_fails_cross_bind():
    checks = _all_ready()
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2024"]["selected_artifacts"] = [
        {"artifact_id": "hud_fmr.bin", "sha256": "SHA-A-NOT-LIVE"}
    ]
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["ok"] is False
    assert any("housing:2024:ARTIFACT_SHA_MISMATCH" in item for item in result["issues"])


def test_source_id_mismatch_fails_cross_bind():
    checks = _all_ready()
    payload = _complete_inputs()
    payload["inputs"]["food"]["2024"]["source_id"] = "some_other_source"
    payload["inputs"]["food"]["2024"]["source_family"] = "some_other_source"
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["ok"] is False
    assert any("food:2024:SOURCE_ID_MISMATCH" in item for item in result["issues"])


def test_source_gap_evidence_is_incomplete():
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2024"]["evidence_status"] = "SOURCE_GAP"
    result = evaluate_candidate_input_bindings(
        payload, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["bound"] is False
    assert "housing:2024" in result["missing"]


def test_retrieved_unvalidated_evidence_is_incomplete():
    payload = _complete_inputs()
    payload["inputs"]["mpg"]["2026"]["evidence_status"] = "RETRIEVED_UNVALIDATED"
    result = evaluate_candidate_input_bindings(
        payload, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["bound"] is False
    assert "mpg:2026" in result["missing"]


def test_validated_evidence_matching_live_may_pass_structural():
    payload = _complete_inputs()
    result = evaluate_candidate_input_bindings(
        payload, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["bound"] is True
    cross = validate_candidate_bindings_against_snapshot(
        payload, _all_ready(), years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert cross["ok"] is True


def test_frozen_cpi_updated_cannot_be_bound_as_none():
    payload = _complete_inputs()
    payload["inputs"]["health_oop"]["2024"]["translation_method"] = "NONE"
    result = evaluate_candidate_input_bindings(
        payload, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["bound"] is False
    assert "health_oop:2024" in result["missing"]


def test_cpi_updated_without_od010_record_fails():
    payload = _complete_inputs()
    result = evaluate_candidate_input_bindings(payload, years=(2024, 2026), od010_payload=None)
    assert result["bound"] is False
    assert "health_oop:2024" in result["missing"]
    assert "insurance:2026" in result["missing"]


def test_generated_coverage_cannot_delete_registration():
    coverage = {
        "required_components": [c for c in REQUIRED_CANDIDATE_COMPONENTS if c != "registration"]
    }
    with pytest.raises(CoverageAuthorityError):
        assert_canonical_component_universe(coverage)
    assert "registration" in required_candidate_components()
    assert len(required_candidate_components()) == 19


def test_generated_source_lag_cannot_drop_frozen_cpi_updated():
    lag = json.loads((METADATA / "living_cost_source_coverage.json").read_text())["source_lag"]
    lag = dict(lag)
    lag["health_oop"] = dict(lag["health_oop"])
    lag["health_oop"]["translation_method"] = "NONE"
    with pytest.raises(SourceLagAuthorityError):
        assert_source_lag_preserves_frozen_od010(lag, years=(2024, 2026))
    pairs = set(required_cpi_updated_bindings(years=(2024, 2026)))
    assert ("health_oop", 2024) in pairs


def _run_ids_for(checks: dict[str, FreshnessCheck], **identity_overrides: object) -> str:
    ctx = build_live_readiness_context(
        checks,
        candidate_payload=None,
        od010_payload=None,
        generated_at="2026-08-15T00:00:00Z",
    )
    for key, value in identity_overrides.items():
        if key in {"candidate_input_binding_identity", "od010_binding_identity"}:
            ident = dict(ctx[key])
            ident.update(value)  # type: ignore[arg-type]
            ctx[key] = ident
    return compute_freshness_run_id(authorizing_state_core(ctx))


def test_retrieval_validation_status_changes_freshness_run_id():
    first = _run_ids_for(_all_ready())
    changed = _all_ready()
    changed["usda_food"] = _ready_family(
        "usda_food", retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS"
    )
    second = _run_ids_for(changed)
    assert first != second


def test_artifact_currentness_status_changes_freshness_run_id():
    first = _run_ids_for(_all_ready())
    changed = _all_ready()
    changed["eia_gasoline"] = _ready_family(
        "eia_gasoline", artifact_currentness_status="CHECK_FAILED"
    )
    second = _run_ids_for(changed)
    assert first != second


def test_artifact_sha_changes_freshness_run_id():
    first = _run_ids_for(_all_ready())
    changed = _all_ready()
    changed["hud_fmr"] = _ready_family(
        "hud_fmr",
        selected_artifacts=({"artifact_id": "hud_fmr.bin", "sha256": "NEW-SHA"},),
    )
    second = _run_ids_for(changed)
    assert first != second


def test_candidate_binding_hash_changes_freshness_run_id():
    first = _run_ids_for(_all_ready(), candidate_input_binding_identity={"sha256": "bind-aaa"})
    second = _run_ids_for(_all_ready(), candidate_input_binding_identity={"sha256": "bind-bbb"})
    assert first != second


def test_od010_binding_hash_changes_freshness_run_id():
    first = _run_ids_for(_all_ready(), od010_binding_identity={"sha256": "od-aaa"})
    second = _run_ids_for(_all_ready(), od010_binding_identity={"sha256": "od-bbb"})
    assert first != second


def test_readiness_validates_the_exact_captured_context(monkeypatch: pytest.MonkeyPatch):
    from foundation.config import definitions as real_defs
    from foundation.living_cost import candidate_bindings as bindings

    base = real_defs()
    living = dict(base["living_cost"])
    living["candidate_calculation_authorized"] = True
    monkeypatch.setattr("foundation.config.definitions", lambda: {**base, "living_cost": living})

    captured = {"bound": False, "inputs": {"housing": {"note": "captured"}}}
    ctx = build_live_readiness_context(
        _all_ready(),
        candidate_payload=captured,
        od010_payload=None,
        generated_at="2026-08-15T00:00:00Z",
    )
    assert ctx["candidate_binding_payload"] is captured
    calls = {"n": 0}

    def boom() -> None:
        calls["n"] += 1
        raise AssertionError("binding files were re-read")

    monkeypatch.setattr(bindings, "load_candidate_binding_payload", boom)
    monkeypatch.setattr(bindings, "load_od010_payload", boom)
    with pytest.raises(FreshnessGateError, match="NOT_BOUND"):
        validate_readiness_context(ctx)
    snapshot_from_context(ctx)
    assert calls["n"] == 0
    assert ctx["candidate_input_binding_identity"]["bound"] is False


def test_official_coverage_writer_source_lag_matches_frozen_policy():
    writer = (ROOT / "scripts" / "validate_living_cost_sources.py").read_text(encoding="utf-8")
    assert "NONE_ALREADY_LOCAL" not in writer
    assert '"2024": "NONE", "2026": "CPI_UPDATED"' in writer
    assert expected_translation_method("maintenance", 2024) == "NONE"
    committed = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    assert_source_lag_preserves_frozen_od010(committed["source_lag"], years=(2024, 2026))
    assert_canonical_component_universe(committed)


def test_canonical_component_count_and_cpi_pairs():
    assert len(required_candidate_components()) == 19
    assert len(required_cpi_updated_bindings(years=(2024, 2026))) == 7
    assert set(required_cpi_updated_bindings(years=(2024, 2026))) == set(FROZEN_CPI_UPDATED_PAIRS)


def test_future_contract_fields_exist_on_snapshot():
    snapshot = snapshot_from_context(
        build_live_readiness_context(_all_ready(), candidate_payload=None, od010_payload=None)
    )
    contract = snapshot["future_candidate_must_record"]
    assert contract["freshness_run_id"] is True
    assert contract["candidate_input_binding_identity"] is True
    assert contract["od010_binding_identity"] is True
    assert contract["must_not_reload_bindings_after_readiness"] is True
    assert snapshot["calculates_mslc"] is False
