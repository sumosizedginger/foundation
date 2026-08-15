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
    od010_record_hash,
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


def _source_year(family: str, year: int) -> int:
    lagged = {
        "acs_population_weights": 2024,
        "nhts_mileage": 2022,
        "meps_full_year_consolidated": 2023,
        "naic_auto_insurance": 2023,
        "bea_rpp": 2024,
        "bls_ce": 2024,
        "epa_vehicle": 2024,
    }
    return lagged.get(family, year)


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
            "2024": {
                "covered": True,
                "source_data_year": _source_year(family, 2024),
                "artifacts": [{"artifact_id": f"{family}.bin", "sha256": "abc"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": _source_year(family, 2026),
                "artifacts": [{"artifact_id": f"{family}.bin", "sha256": "abc"}],
            },
        },
    }
    payload.update(overrides)
    return FreshnessCheck(**payload)  # type: ignore[arg-type]


def _all_ready() -> dict[str, FreshnessCheck]:
    return {family: _ready_family(family) for family in REQUIRED_FRESHNESS_FAMILIES}


def _od010_record(component: str, year: int) -> dict[str, object]:
    family = COMPONENT_FRESHNESS_FAMILY[component]
    return {
        "component": component,
        "source_data_year": _source_year(family, year),
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
    source_year = _source_year(family, year)
    rec: dict[str, object] = {
        "component": component,
        "project_cost_year": year,
        "source_id": family,
        "source_family": family,
        "source_data_year": source_year,
        "selected_artifacts": [{"artifact_id": f"{family}.bin", "sha256": "abc"}],
        "model_method": "official",
        "evidence_status": "VALIDATED",
        "translation_method": method,
    }
    if method == "SOURCE_CLASSIFIED":
        rec["source_class"] = "high_frequency"
        rec["translation_method"] = "YTD"
    if method == "CPI_UPDATED":
        od_rec = _od010_record(component, year)
        rec["od010_record_identity"] = {
            "component": component,
            "project_cost_year": year,
            "source_data_year": source_year,
            "record_hash": od010_record_hash(od_rec),
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
    assert any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])


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

    def boom(*_args: object, **_kwargs: object) -> None:
        calls["n"] += 1
        raise AssertionError("binding files were re-read")

    monkeypatch.setattr(bindings, "load_candidate_binding_payload", boom)
    monkeypatch.setattr(bindings, "load_od010_payload", boom)
    monkeypatch.setattr(bindings, "capture_json_artifact", boom)
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
    assert expected_translation_method("registration", 2024) == "RULE_YEAR"
    assert expected_translation_method("local_tax", 2026) == "RULE_YEAR"
    assert expected_translation_method("replacement", 2024) == "MODEL_SUBINPUT"
    assert expected_translation_method("connectivity", 2026) == "SOURCE_CLASSIFIED"
    committed = json.loads((METADATA / "living_cost_source_coverage.json").read_text())
    assert committed["source_lag"]["registration"]["translation_method"] == "RULE_YEAR"
    assert committed["coverage_by_year"]["2024"]["registration"] == "SOURCE_GAP"
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


def _hud_live() -> FreshnessCheck:
    return _ready_family(
        "hud_fmr",
        selected_artifacts=(
            {"artifact_id": "FMR2024_final_revised.xlsx", "sha256": "HASH-A"},
            {"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"},
        ),
        year_coverage={
            "2024": {
                "covered": True,
                "source_data_year": 2024,
                "artifacts": [{"artifact_id": "FMR2024_final_revised.xlsx", "sha256": "HASH-A"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": 2026,
                "artifacts": [{"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"}],
            },
        },
    )


def test_housing_2024_cannot_bind_fy26_artifact():
    checks = _all_ready()
    checks["hud_fmr"] = _hud_live()
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2024"]["selected_artifacts"] = [
        {"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"}
    ]
    payload["inputs"]["housing"]["2024"]["source_data_year"] = 2024
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["ok"] is False
    assert any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])


def test_housing_2024_may_bind_fy24_artifact():
    checks = _all_ready()
    checks["hud_fmr"] = _hud_live()
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2024"]["selected_artifacts"] = [
        {"artifact_id": "FMR2024_final_revised.xlsx", "sha256": "HASH-A"}
    ]
    payload["inputs"]["housing"]["2026"]["selected_artifacts"] = [
        {"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"}
    ]
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert not any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])
    assert not any("housing:2026:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])


def test_housing_2026_cannot_bind_fy24_artifact():
    checks = _all_ready()
    checks["hud_fmr"] = _hud_live()
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2026"]["selected_artifacts"] = [
        {"artifact_id": "FMR2024_final_revised.xlsx", "sha256": "HASH-A"}
    ]
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert any("housing:2026:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])


def test_acs_2026_may_use_2024_source_year_and_artifact():
    checks = _all_ready()
    checks["acs_population_weights"] = _ready_family(
        "acs_population_weights",
        selected_artifacts=({"artifact_id": "acsdt5y2024-b01001.dat", "sha256": "ACS24"},),
        year_coverage={
            "2024": {
                "covered": True,
                "source_data_year": 2024,
                "artifacts": [{"artifact_id": "acsdt5y2024-b01001.dat", "sha256": "ACS24"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": 2024,
                "artifacts": [{"artifact_id": "acsdt5y2024-b01001.dat", "sha256": "ACS24"}],
            },
        },
    )
    payload = _complete_inputs()
    for year in ("2024", "2026"):
        payload["inputs"]["population_weights"][year]["source_data_year"] = 2024
        payload["inputs"]["population_weights"][year]["selected_artifacts"] = [
            {"artifact_id": "acsdt5y2024-b01001.dat", "sha256": "ACS24"}
        ]
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert not any(
        "population_weights:" in item and "MISMATCH" in item for item in result["issues"]
    )


def test_acs_2026_false_source_year_fails():
    checks = _all_ready()
    checks["acs_population_weights"] = _ready_family(
        "acs_population_weights",
        year_coverage={
            "2024": {
                "covered": True,
                "source_data_year": 2024,
                "artifacts": [{"artifact_id": "acs_population_weights.bin", "sha256": "abc"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": 2024,
                "artifacts": [{"artifact_id": "acs_population_weights.bin", "sha256": "abc"}],
            },
        },
    )
    payload = _complete_inputs()
    payload["inputs"]["population_weights"]["2026"]["source_data_year"] = 2026
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert any(
        "population_weights:2026:SOURCE_DATA_YEAR_MISMATCH" in item for item in result["issues"]
    )


def test_meps_source_year_must_match_live_fyc():
    checks = _all_ready()
    checks["meps_full_year_consolidated"] = _ready_family(
        "meps_full_year_consolidated",
        year_coverage={
            "2024": {
                "covered": True,
                "source_data_year": 2023,
                "artifacts": [{"artifact_id": "meps_full_year_consolidated.bin", "sha256": "abc"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": 2023,
                "artifacts": [{"artifact_id": "meps_full_year_consolidated.bin", "sha256": "abc"}],
            },
        },
    )
    payload = _complete_inputs()
    payload["inputs"]["health_oop"]["2024"]["source_data_year"] = 2024
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert any("health_oop:2024:SOURCE_DATA_YEAR_MISMATCH" in item for item in result["issues"])


def test_od010_validation_state_must_be_passing():
    from foundation.living_cost.candidate_bindings import evaluate_od010_translation_table

    def table(state: str) -> dict[str, object]:
        series = [_od010_record(component, year) for component, year in FROZEN_CPI_UPDATED_PAIRS]
        series[0]["retrieval_validation_state"] = state
        return {"series": series}

    for state in ("SOURCE_GAP", "RETRIEVED_UNVALIDATED", "INCOMPLETE_PROVENANCE"):
        result = evaluate_od010_translation_table(table(state), years=(2024, 2026))
        assert result["bound"] is False, state
    ok = evaluate_od010_translation_table(_complete_od010(), years=(2024, 2026))
    assert ok["bound"] is True


def test_od010_arbitrary_hash_fails():
    payload = _complete_inputs()
    payload["inputs"]["health_oop"]["2024"]["od010_record_identity"] = {
        "component": "health_oop",
        "project_cost_year": 2024,
        "source_data_year": 2023,
        "record_hash": "a" * 64,
    }
    result = evaluate_candidate_input_bindings(
        payload, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["bound"] is False
    assert "health_oop:2024" in result["missing"]


def test_atomic_capture_payload_and_hash_stay_together(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import hashlib

    from foundation.living_cost import candidate_bindings as bindings
    from foundation.living_cost.candidate_bindings import capture_json_artifact

    path = tmp_path / "living_cost_candidate_input_bindings.json"
    payload_a = {"bound": False, "inputs": {"marker": "A"}}
    payload_b = {"bound": False, "inputs": {"marker": "B"}}
    path.write_text(json.dumps(payload_a), encoding="utf-8")
    sha_a = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(bindings, "CANDIDATE_INPUT_BINDINGS", path)

    captured = capture_json_artifact(path)
    path.write_text(json.dumps(payload_b), encoding="utf-8")
    sha_b = hashlib.sha256(path.read_bytes()).hexdigest()
    ctx = build_live_readiness_context(
        _all_ready(),
        candidate_payload=captured.payload,
        od010_payload=None,
        generated_at="2026-08-15T00:00:00Z",
    )
    ctx["candidate_input_binding_identity"]["sha256"] = captured.raw_sha256
    assert captured.payload["inputs"]["marker"] == "A"
    assert captured.raw_sha256 == sha_a
    assert sha_a != sha_b
    assert ctx["candidate_binding_payload"]["inputs"]["marker"] == "A"
    assert ctx["candidate_input_binding_identity"]["sha256"] == sha_a

    od_path = tmp_path / "living_cost_od010_translation_table.json"
    od_a = {"bound": False, "series": {"marker": "OA"}}
    od_b = {"bound": False, "series": {"marker": "OB"}}
    od_path.write_text(json.dumps(od_a), encoding="utf-8")
    od_sha_a = hashlib.sha256(od_path.read_bytes()).hexdigest()
    od_cap = capture_json_artifact(od_path)
    od_path.write_text(json.dumps(od_b), encoding="utf-8")
    assert od_cap.payload["series"]["marker"] == "OA"
    assert od_cap.raw_sha256 == od_sha_a
    assert od_cap.raw_sha256 != hashlib.sha256(od_path.read_bytes()).hexdigest()


def test_atomic_capture_survives_file_change_during_readiness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import hashlib

    from foundation.living_cost import candidate_bindings as bindings

    path = tmp_path / "bindings.json"
    payload_a = {"bound": False, "inputs": {"marker": "A"}}
    payload_b = {"bound": False, "inputs": {"marker": "B"}}
    path.write_text(json.dumps(payload_a), encoding="utf-8")
    sha_a = hashlib.sha256(path.read_bytes()).hexdigest()
    monkeypatch.setattr(bindings, "CANDIDATE_INPUT_BINDINGS", path)
    original = Path.read_bytes
    flipped = {"done": False}

    def mutating_read(self: Path) -> bytes:
        data = original(self)
        if self.resolve() == path.resolve() and not flipped["done"]:
            flipped["done"] = True
            path.write_text(json.dumps(payload_b), encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", mutating_read)
    ctx = build_live_readiness_context(_all_ready(), generated_at="2026-08-15T00:00:00Z")
    assert ctx["candidate_binding_payload"]["inputs"]["marker"] == "A"
    assert ctx["candidate_input_binding_identity"]["sha256"] == sha_a
    assert json.loads(original(path))["inputs"]["marker"] == "B"
