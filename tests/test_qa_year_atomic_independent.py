"""Independent QA for GROK.MD year-specific / atomic binding integrity.

Does not calculate an MSLC. Does not build the assembler. Does not invent
bindings as project artifacts. Temporary payloads exist only in this test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from foundation.config import definitions
from foundation.living_cost import candidate_bindings as bindings
from foundation.living_cost.candidate_bindings import (
    BLOCKING_BINDING_EVIDENCE,
    COMPONENT_FRESHNESS_FAMILY,
    FROZEN_CPI_UPDATED_PAIRS,
    FROZEN_TRANSLATION_POLICY,
    PASSING_BINDING_EVIDENCE,
    REQUIRED_CANDIDATE_COMPONENTS,
    CapturedJsonArtifact,
    _translation_record_complete,
    authorized_artifacts_for_year,
    capture_json_artifact,
    evaluate_candidate_input_bindings,
    evaluate_od010_translation_table,
    expected_translation_method,
    live_source_data_year,
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
    living_cost_release_authorized,
    snapshot_from_context,
    validate_readiness_context,
)
from foundation.living_cost.freshness import (
    candidate_calculation_authorized as freshness_candidate_auth,
)
from foundation.living_cost.owner_freeze import (
    CANONICAL_RESILIENCE_RESERVE_ANNUAL,
    METHODOLOGY_STATUS_FROZEN,
    MINIMUM_SOCIAL_RECREATION_ANNUAL,
    OWNER_FREEZE_STATUS,
    PREFERRED_SOCIAL_RECREATION_ANNUAL,
    canonical_resilience_reserve,
    public_states_modeled,
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


def test_hud_year_specific_artifact_matrix():
    checks = _all_ready()
    checks["hud_fmr"] = _hud_live()
    od010 = _complete_od010()

    def run(year: int, artifact: str, digest: str) -> list[str]:
        payload = _complete_inputs()
        payload["inputs"]["housing"][str(year)]["selected_artifacts"] = [
            {"artifact_id": artifact, "sha256": digest}
        ]
        payload["inputs"]["housing"]["2024"]["selected_artifacts"] = payload["inputs"]["housing"][
            "2024"
        ].get("selected_artifacts") or [
            {"artifact_id": "FMR2024_final_revised.xlsx", "sha256": "HASH-A"}
        ]
        payload["inputs"]["housing"]["2026"]["selected_artifacts"] = payload["inputs"]["housing"][
            "2026"
        ].get("selected_artifacts") or [
            {"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"}
        ]
        payload["inputs"]["housing"][str(year)]["selected_artifacts"] = [
            {"artifact_id": artifact, "sha256": digest}
        ]
        result = validate_candidate_bindings_against_snapshot(
            payload, checks, years=(2024, 2026), od010_payload=od010
        )
        return result["issues"]

    issues_24_b = run(2024, "FY26_FMRs_revised.xlsx", "HASH-B")
    assert any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in issues_24_b)

    issues_24_a = run(2024, "FMR2024_final_revised.xlsx", "HASH-A")
    assert not any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in issues_24_a)

    issues_26_a = run(2026, "FMR2024_final_revised.xlsx", "HASH-A")
    assert any("housing:2026:YEAR_ARTIFACT_MISMATCH" in item for item in issues_26_a)

    issues_26_b = run(2026, "FY26_FMRs_revised.xlsx", "HASH-B")
    assert not any("housing:2026:YEAR_ARTIFACT_MISMATCH" in item for item in issues_26_b)

    year_keys_2024 = authorized_artifacts_for_year(checks["hud_fmr"], 2024)
    year_keys_2026 = authorized_artifacts_for_year(checks["hud_fmr"], 2026)
    assert ("FY26_FMRs_revised.xlsx", "HASH-B") not in year_keys_2024
    assert ("FMR2024_final_revised.xlsx", "HASH-A") not in year_keys_2026


def test_family_wide_hash_is_not_enough_without_year_authorization():
    """A hash that exists somewhere in the family must not authorize another year."""
    checks = _all_ready()
    checks["hud_fmr"] = _hud_live()
    payload = _complete_inputs()
    payload["inputs"]["housing"]["2024"]["selected_artifacts"] = [
        {"artifact_id": "FY26_FMRs_revised.xlsx", "sha256": "HASH-B"}
    ]
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert result["ok"] is False
    assert any("housing:2024:YEAR_ARTIFACT_MISMATCH" in item for item in result["issues"])


def test_acs_source_data_year_cross_bind():
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
    ok = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert not any(
        "population_weights:" in item and "SOURCE_DATA_YEAR_MISMATCH" in item
        for item in ok["issues"]
    )

    payload["inputs"]["population_weights"]["2026"]["source_data_year"] = 2026
    bad = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert any(
        "population_weights:2026:SOURCE_DATA_YEAR_MISMATCH" in item for item in bad["issues"]
    )


def test_meps_and_nhts_and_naic_source_years():
    checks = _all_ready()
    payload = _complete_inputs()
    payload["inputs"]["health_oop"]["2024"]["source_data_year"] = 2024
    payload["inputs"]["mileage"]["2026"]["source_data_year"] = 2026
    payload["inputs"]["insurance"]["2026"]["source_data_year"] = 2026
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    issues = result["issues"]
    assert any("health_oop:2024:SOURCE_DATA_YEAR_MISMATCH" in item for item in issues)
    assert any("mileage:2026:SOURCE_DATA_YEAR_MISMATCH" in item for item in issues)
    assert any("insurance:2026:SOURCE_DATA_YEAR_MISMATCH" in item for item in issues)
    assert live_source_data_year(checks["meps_full_year_consolidated"], 2026) == 2023
    assert live_source_data_year(checks["nhts_mileage"], 2024) == 2022
    assert live_source_data_year(checks["naic_auto_insurance"], 2026) == 2023
    assert live_source_data_year(checks["hud_fmr"], 2026) == 2026


def test_missing_live_source_data_year_fails_closed():
    checks = _all_ready()
    checks["hud_fmr"] = _ready_family(
        "hud_fmr",
        year_coverage={
            "2024": {
                "covered": True,
                "artifacts": [{"artifact_id": "hud_fmr.bin", "sha256": "abc"}],
            },
            "2026": {
                "covered": True,
                "source_data_year": 2026,
                "artifacts": [{"artifact_id": "hud_fmr.bin", "sha256": "abc"}],
            },
        },
    )
    payload = _complete_inputs()
    result = validate_candidate_bindings_against_snapshot(
        payload, checks, years=(2024, 2026), od010_payload=_complete_od010()
    )
    assert any("housing:2024:SOURCE_DATA_YEAR_UNSPECIFIED" in item for item in result["issues"])


def test_od010_all_blocking_states_fail_and_validated_may_pass():
    rec = _od010_record("health_oop", 2024)
    assert _translation_record_complete(rec, component="health_oop", year=2024) is True
    for state in sorted(BLOCKING_BINDING_EVIDENCE):
        rec["retrieval_validation_state"] = state
        assert _translation_record_complete(rec, component="health_oop", year=2024) is False, state
    rec["retrieval_validation_state"] = "OK"
    assert _translation_record_complete(rec, component="health_oop", year=2024) is False
    rec["retrieval_validation_state"] = "VALIDATED"
    assert _translation_record_complete(rec, component="health_oop", year=2024) is True
    rec["retrieval_validation_state"] = "MODELED_FROM_MEASURED_INPUTS"
    assert _translation_record_complete(rec, component="health_oop", year=2024) is True
    assert PASSING_BINDING_EVIDENCE == frozenset({"VALIDATED", "MODELED_FROM_MEASURED_INPUTS"})


def test_od010_table_blocking_states_unbound():
    for state in (
        "SOURCE_GAP",
        "UNAVAILABLE",
        "INCOMPLETE_PROVENANCE",
        "FORMULA_FROZEN_INPUTS_PENDING",
        "INVENTORY_NOT_VALIDATED",
        "RETRIEVED_UNVALIDATED",
        "ANYTHING_NONEMPTY",
    ):
        series = [_od010_record(component, year) for component, year in FROZEN_CPI_UPDATED_PAIRS]
        series[0]["retrieval_validation_state"] = state
        result = evaluate_od010_translation_table({"series": series}, years=(2024, 2026))
        assert result["bound"] is False, state
    ok = evaluate_od010_translation_table(_complete_od010(), years=(2024, 2026))
    assert ok["bound"] is True


def test_od010_record_hash_must_match_exact_record():
    payload = _complete_inputs()
    od010 = _complete_od010()
    identity = payload["inputs"]["health_oop"]["2024"]["od010_record_identity"]
    identity["record_hash"] = "a" * 64
    result = evaluate_candidate_input_bindings(payload, years=(2024, 2026), od010_payload=od010)
    assert result["bound"] is False
    assert "health_oop:2024" in result["missing"]

    payload = _complete_inputs()
    identity = payload["inputs"]["health_oop"]["2024"]["od010_record_identity"]
    identity["source_data_year"] = 1999
    result = evaluate_candidate_input_bindings(payload, years=(2024, 2026), od010_payload=od010)
    assert "health_oop:2024" in result["missing"]

    rec = _od010_record("health_oop", 2024)
    first = od010_record_hash(rec)
    rec["translation_factor"] = 9.99
    assert od010_record_hash(rec) != first


def test_translation_policy_separates_method_from_evidence():
    assert expected_translation_method("registration", 2024) == "RULE_YEAR"
    assert expected_translation_method("registration", 2026) == "RULE_YEAR"
    assert expected_translation_method("local_tax", 2024) == "RULE_YEAR"
    assert expected_translation_method("local_tax", 2026) == "RULE_YEAR"
    assert expected_translation_method("replacement", 2024) == "MODEL_SUBINPUT"
    assert expected_translation_method("connectivity", 2026) == "SOURCE_CLASSIFIED"
    assert FROZEN_TRANSLATION_POLICY["registration"] != "SOURCE_GAP"
    assert FROZEN_TRANSLATION_POLICY["local_tax"] != "SOURCE_GAP"
    assert FROZEN_TRANSLATION_POLICY["replacement"] != "FORMULA_PENDING_INPUTS"
    assert FROZEN_TRANSLATION_POLICY["connectivity"] != "YTD"
    coverage = json.loads(
        (METADATA / "living_cost_source_coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["source_lag"]["registration"]["translation_method"] == "RULE_YEAR"
    assert coverage["source_lag"]["local_tax"]["translation_method"] == "RULE_YEAR"
    assert coverage["coverage_by_year"]["2024"]["registration"] == "SOURCE_GAP"
    assert coverage["coverage_by_year"]["2026"]["local_tax"] == "SOURCE_GAP"


def test_atomic_capture_survives_disk_mutation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cand_path = tmp_path / "living_cost_candidate_input_bindings.json"
    od_path = tmp_path / "living_cost_od010_translation_table.json"
    payload_a = {"bound": False, "inputs": {"marker": "A"}}
    payload_b = {"bound": False, "inputs": {"marker": "B"}}
    od_a = {"bound": False, "series": {"marker": "OA"}}
    od_b = {"bound": False, "series": {"marker": "OB"}}
    cand_path.write_text(json.dumps(payload_a), encoding="utf-8")
    od_path.write_text(json.dumps(od_a), encoding="utf-8")
    sha_a = hashlib.sha256(cand_path.read_bytes()).hexdigest()
    od_sha_a = hashlib.sha256(od_path.read_bytes()).hexdigest()
    monkeypatch.setattr(bindings, "CANDIDATE_INPUT_BINDINGS", cand_path)
    monkeypatch.setattr(bindings, "OD010_TABLE", od_path)

    original = Path.read_bytes
    flipped = {"cand": False, "od": False}

    def mutating_read(self: Path) -> bytes:
        data = original(self)
        resolved = self.resolve()
        if resolved == cand_path.resolve() and not flipped["cand"]:
            flipped["cand"] = True
            cand_path.write_text(json.dumps(payload_b), encoding="utf-8")
        if resolved == od_path.resolve() and not flipped["od"]:
            flipped["od"] = True
            od_path.write_text(json.dumps(od_b), encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", mutating_read)
    ctx = build_live_readiness_context(_all_ready(), generated_at="2026-08-15T12:00:00Z")
    assert ctx["candidate_binding_payload"]["inputs"]["marker"] == "A"
    assert ctx["candidate_input_binding_identity"]["sha256"] == sha_a
    assert ctx["od010_payload"]["series"]["marker"] == "OA"
    assert ctx["od010_binding_identity"]["sha256"] == od_sha_a
    assert json.loads(original(cand_path))["inputs"]["marker"] == "B"
    assert json.loads(original(od_path))["series"]["marker"] == "OB"
    sha_b = hashlib.sha256(original(cand_path)).hexdigest()
    od_sha_b = hashlib.sha256(original(od_path)).hexdigest()
    assert sha_a != sha_b
    assert od_sha_a != od_sha_b
    assert ctx["candidate_input_binding_identity"]["sha256"] != sha_b
    assert ctx["od010_binding_identity"]["sha256"] != od_sha_b


def test_freshness_run_id_uses_atomic_captured_identities(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    cand_path = tmp_path / "bindings.json"
    payload_a = {"bound": False, "inputs": {"marker": "A"}}
    payload_b = {"bound": False, "inputs": {"marker": "B"}}
    cand_path.write_text(json.dumps(payload_a), encoding="utf-8")
    sha_a = hashlib.sha256(cand_path.read_bytes()).hexdigest()
    monkeypatch.setattr(bindings, "CANDIDATE_INPUT_BINDINGS", cand_path)
    original = Path.read_bytes
    flipped = {"done": False}

    def mutating_read(self: Path) -> bytes:
        data = original(self)
        if self.resolve() == cand_path.resolve() and not flipped["done"]:
            flipped["done"] = True
            cand_path.write_text(json.dumps(payload_b), encoding="utf-8")
        return data

    monkeypatch.setattr(Path, "read_bytes", mutating_read)
    ctx = build_live_readiness_context(_all_ready(), generated_at="2026-08-15T12:00:00Z")
    snapshot = snapshot_from_context(ctx)
    core = authorizing_state_core(snapshot)
    assert core["candidate_input_binding_identity"]["sha256"] == sha_a
    assert snapshot["freshness_run_id"] == compute_freshness_run_id(core)
    mutated_core = json.loads(json.dumps(core))
    mutated_core["candidate_input_binding_identity"]["sha256"] = hashlib.sha256(
        original(cand_path)
    ).hexdigest()
    assert compute_freshness_run_id(mutated_core) != snapshot["freshness_run_id"]


def test_no_second_disk_read_after_context(monkeypatch: pytest.MonkeyPatch):
    ctx = build_live_readiness_context(
        _all_ready(),
        candidate_payload={"bound": False, "inputs": {}},
        od010_payload=None,
        generated_at="2026-08-15T00:00:00Z",
    )
    calls = {"n": 0}

    def boom(*_args: object, **_kwargs: object) -> CapturedJsonArtifact:
        calls["n"] += 1
        raise AssertionError("binding files were re-read")

    monkeypatch.setattr(bindings, "capture_json_artifact", boom)
    monkeypatch.setattr(bindings, "load_candidate_binding_payload", boom)
    monkeypatch.setattr(bindings, "load_od010_payload", boom)
    with pytest.raises(FreshnessGateError):
        validate_readiness_context(ctx)
    snapshot_from_context(ctx)
    assert calls["n"] == 0


def test_current_locks_and_no_fake_bindings():
    living = definitions()["living_cost"]
    assert living["candidate_calculation_authorized"] is False
    assert living["release_authorized"] is False
    assert living["states_modeled"] == 0
    assert living["owner_freeze"]["status"] == "ACCEPTED"
    assert living["owner_freeze"]["methodology_status"] == "FROZEN"
    assert living["owner_freeze"]["decisions"] == [f"OD-{n:03d}" for n in range(1, 14)]
    assert OWNER_FREEZE_STATUS == "ACCEPTED"
    assert METHODOLOGY_STATUS_FROZEN == "FROZEN"
    assert freshness_candidate_auth() is False
    assert living_cost_release_authorized() is False
    assert public_states_modeled() == 0
    assert len(required_candidate_components()) == 19
    assert list(required_candidate_components()) == list(REQUIRED_CANDIDATE_COMPONENTS)
    assert len(required_cpi_updated_bindings(years=(2024, 2026))) == 7
    assert MINIMUM_SOCIAL_RECREATION_ANNUAL == 1200.0
    assert PREFERRED_SOCIAL_RECREATION_ANNUAL == 2400.0
    assert CANONICAL_RESILIENCE_RESERVE_ANNUAL == 0.0
    assert canonical_resilience_reserve() == 0.0
    assert living["social_recreation"]["minimum_annual"] == 1200
    assert living["social_recreation"]["preferred_annual"] == 2400
    assert living["resilience"]["extra_reserve_annual"] == 0

    assert not (METADATA / "living_cost_candidate_input_bindings.json").exists()
    ctx = build_live_readiness_context(_all_ready())
    assert ctx["candidate_inputs_bound"] is False
    assert ctx["calculates_mslc"] is False
    snapshot = snapshot_from_context(ctx)
    assert snapshot["ready_for_private_candidate"] is False
    assert snapshot["headline_calculated"] is False
    coverage = json.loads(
        (METADATA / "living_cost_source_coverage.json").read_text(encoding="utf-8")
    )
    assert coverage["states_modeled"] == 0
    assert coverage["candidate_calculation_authorized"] is False
    assert coverage["living_cost_release_authorized"] is False
    freshness = json.loads(
        (METADATA / "living_cost_candidate_freshness.json").read_text(encoding="utf-8")
    )
    assert freshness["ready_for_private_candidate"] is False
    assert freshness["candidate_inputs_bound"] is False
    assert (
        freshness.get("calculates_mslc") is False or freshness.get("headline_calculated") is False
    )


def test_capture_json_artifact_hashes_the_same_bytes_it_parses(tmp_path: Path):
    path = tmp_path / "x.json"
    raw = b'{"hello": "world", "n": 1}'
    path.write_bytes(raw)
    captured = capture_json_artifact(path)
    assert captured.exists is True
    assert captured.raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert captured.payload == {"hello": "world", "n": 1}
    path.write_bytes(b'{"hello": "changed"}')
    assert captured.payload == {"hello": "world", "n": 1}
    assert captured.raw_sha256 == hashlib.sha256(raw).hexdigest()
