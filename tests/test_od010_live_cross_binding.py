"""Behavioral tests for OD-010 live-freshness series cross-binding.

Does not calculate or publish an MSLC. Does not build the assembler.
Does not create a production translation table. No live-network calls.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from foundation.living_cost.candidate_bindings import (
    COMPONENT_FRESHNESS_FAMILY,
    FROZEN_CPI_UPDATED_PAIRS,
    evaluate_od010_translation_table,
    expected_translation_method,
    od010_record_hash,
    od010_series_inventory_is_specific,
    required_candidate_components,
    required_cpi_updated_bindings,
    validate_od010_bindings_against_snapshot,
)
from foundation.living_cost.freshness import (
    REQUIRED_FRESHNESS_FAMILIES,
    FreshnessCheck,
    authorizing_state_core,
    build_live_readiness_context,
    compute_freshness_run_id,
    snapshot_from_context,
)
from foundation.living_cost.freshness_discovery import discover_od010

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


def _series_id(component: str) -> str:
    return f"CUSR0000-{component}"


def _artifact(component: str) -> str:
    return f"https://api.bls.gov/publicAPI/v2/timeseries/{component}"


def _sha(component: str, year: int) -> str:
    return f"hash-{component}-{year}"


def _series_slot(component: str, year: int, **overrides: object) -> dict[str, object]:
    family = COMPONENT_FRESHNESS_FAMILY[component]
    source_year = _source_year(family, year)
    slot: dict[str, object] = {
        "covered": True,
        "official_series_identifier": _series_id(component),
        "publisher": "BLS",
        "latest_observation_period": f"{year} annual",
        "target_observation_period": f"{year} annual",
        "base_observation_period": f"{source_year} annual",
        "source_data_year": source_year,
        "selected_artifact": _artifact(component),
        "api_identity": _artifact(component),
        "sha256": _sha(component, year),
        "base_index_value": 100.0,
        "target_index_value": 102.0,
    }
    slot.update(overrides)
    return slot


def _live_series_coverage(**pair_overrides: object) -> dict[str, dict[str, dict[str, object]]]:
    coverage: dict[str, dict[str, dict[str, object]]] = {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        coverage.setdefault(component, {})[str(year)] = _series_slot(component, year)
    for key, value in pair_overrides.items():
        component, year_s = key.split(":")
        coverage[component][year_s] = value  # type: ignore[assignment]
    return coverage


def _od010_record(component: str, year: int, **overrides: object) -> dict[str, object]:
    family = COMPONENT_FRESHNESS_FAMILY[component]
    source_year = _source_year(family, year)
    rec: dict[str, object] = {
        "component": component,
        "source_data_year": source_year,
        "project_cost_year": year,
        "official_series_identifier": _series_id(component),
        "publisher": "BLS",
        "observation_period": f"{year} annual",
        "source_artifact": _artifact(component),
        "sha256": _sha(component, year),
        "translation_factor": 1.02,
        "retrieval_validation_state": "VALIDATED",
        "calculation_inputs": {
            "base_observation_period": f"{source_year} annual",
            "base_index_value": 100.0,
            "target_observation_period": f"{year} annual",
            "target_index_value": 102.0,
            "translation_factor": 1.02,
            "official_series_identifier": _series_id(component),
            "source_artifact": _artifact(component),
            "sha256": _sha(component, year),
        },
    }
    rec.update(overrides)
    return rec


def _complete_od010() -> dict[str, object]:
    return {
        "series": [_od010_record(component, year) for component, year in FROZEN_CPI_UPDATED_PAIRS]
    }


def _all_ready_with_od010_series(**coverage_overrides: object) -> dict[str, FreshnessCheck]:
    checks = {family: _ready_family(family) for family in REQUIRED_FRESHNESS_FAMILIES}
    checks["od010_price_index"] = _ready_family(
        "od010_price_index",
        publisher="BLS",
        selected_artifact="bls-cpi-api",
        series_coverage=_live_series_coverage(**coverage_overrides),
    )
    return checks


def test_frozen_cpi_updated_pairs_unchanged():
    assert required_cpi_updated_bindings(years=(2024, 2026)) == list(FROZEN_CPI_UPDATED_PAIRS)
    assert FROZEN_CPI_UPDATED_PAIRS == (
        ("health_oop", 2024),
        ("health_oop", 2026),
        ("insurance", 2024),
        ("insurance", 2026),
        ("maintenance", 2026),
        ("essentials", 2026),
        ("recreation", 2026),
    )
    assert len(required_candidate_components()) == 19
    assert expected_translation_method("registration", 2024) == "RULE_YEAR"
    assert expected_translation_method("local_tax", 2026) == "RULE_YEAR"
    assert expected_translation_method("replacement", 2024) == "MODEL_SUBINPUT"
    assert expected_translation_method("connectivity", 2026) == "SOURCE_CLASSIFIED"


def test_matching_live_and_table_series_may_pass_cross_bind():
    result = validate_od010_bindings_against_snapshot(
        _complete_od010(),
        _all_ready_with_od010_series(),
        years=(2024, 2026),
    )
    assert result["ok"] is True
    assert result["issues"] == []
    assert result["required"] == [f"{c}:{y}" for c, y in FROZEN_CPI_UPDATED_PAIRS]
    assert all(row["cross_bound"] is True for row in result["normalized"])


def test_live_series_x_table_series_y_fails():
    table = _complete_od010()
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == "insurance" and rec["project_cost_year"] == 2024:
            rec["official_series_identifier"] = "CUSR0000-WRONG-SERIES"
            calc = dict(rec["calculation_inputs"])  # type: ignore[arg-type]
            calc["official_series_identifier"] = "CUSR0000-WRONG-SERIES"
            rec["calculation_inputs"] = calc
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "insurance:2024:SERIES_IDENTIFIER_MISMATCH" in result["issues"]


def test_same_series_different_artifact_hash_fails():
    table = _complete_od010()
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == "health_oop" and rec["project_cost_year"] == 2026:
            rec["sha256"] = "HASH-A-OLD-ARTIFACT"
            calc = dict(rec["calculation_inputs"])  # type: ignore[arg-type]
            calc["sha256"] = "HASH-A-OLD-ARTIFACT"
            rec["calculation_inputs"] = calc
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "health_oop:2026:ARTIFACT_HASH_MISMATCH" in result["issues"]


def test_same_series_source_data_year_mismatch_fails():
    table = _complete_od010()
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == "essentials" and rec["project_cost_year"] == 2026:
            rec["source_data_year"] = 2019
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "essentials:2026:SOURCE_DATA_YEAR_MISMATCH" in result["issues"]


def test_target_observation_period_mismatch_fails():
    table = _complete_od010()
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == "recreation" and rec["project_cost_year"] == 2026:
            rec["observation_period"] = "2025 annual"
            calc = dict(rec["calculation_inputs"])  # type: ignore[arg-type]
            calc["target_observation_period"] = "2025 annual"
            rec["calculation_inputs"] = calc
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "recreation:2026:OBSERVATION_PERIOD_MISMATCH" in result["issues"]


def test_structurally_complete_but_failed_cross_bind_keeps_translation_unbound():
    table = _complete_od010()
    structural = evaluate_od010_translation_table(table, years=(2024, 2026))
    assert structural["bound"] is True
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == "maintenance":
            rec["official_series_identifier"] = "SERIES-Y-NOT-LIVE"
    ctx = build_live_readiness_context(
        _all_ready_with_od010_series(),
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    assert ctx["od010_evaluation"]["bound"] is True
    assert ctx["od010_cross_binding"]["ok"] is False
    assert ctx["translation_index_bound"] is False
    assert any(
        "SERIES_IDENTIFIER_MISMATCH" in issue for issue in ctx["od010_cross_binding"]["issues"]
    )


def test_structurally_complete_and_successful_cross_bind_may_bind_translation():
    table = _complete_od010()
    assert evaluate_od010_translation_table(table, years=(2024, 2026))["bound"] is True
    ctx = build_live_readiness_context(
        _all_ready_with_od010_series(),
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    assert ctx["od010_cross_binding"]["ok"] is True
    assert ctx["translation_index_bound"] is True
    snapshot = snapshot_from_context(ctx)
    assert snapshot["translation_index_bound"] is True
    assert snapshot["od010_cross_binding"]["ok"] is True
    assert snapshot["candidate_calculation_authorized"] is False
    assert snapshot["ready_for_private_candidate"] is False
    assert snapshot["calculates_mslc"] is False


def test_changing_live_series_or_observation_changes_freshness_run_id():
    table = _complete_od010()
    base_checks = _all_ready_with_od010_series()
    first_ctx = build_live_readiness_context(
        base_checks,
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    first = compute_freshness_run_id(authorizing_state_core(first_ctx))

    changed_series = _all_ready_with_od010_series(
        **{
            "insurance:2024": _series_slot(
                "insurance", 2024, official_series_identifier="CUSR0000-insurance-NEW"
            )
        }
    )
    series_ctx = build_live_readiness_context(
        changed_series,
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    assert compute_freshness_run_id(authorizing_state_core(series_ctx)) != first

    changed_hash = _all_ready_with_od010_series(
        **{"health_oop:2024": _series_slot("health_oop", 2024, sha256="hash-health_oop-2024-B")}
    )
    hash_ctx = build_live_readiness_context(
        changed_hash,
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    assert compute_freshness_run_id(authorizing_state_core(hash_ctx)) != first

    changed_period = _all_ready_with_od010_series(
        **{
            "recreation:2026": _series_slot(
                "recreation",
                2026,
                latest_observation_period="2026-05",
                target_observation_period="2026-05",
            )
        }
    )
    period_ctx = build_live_readiness_context(
        changed_period,
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    assert compute_freshness_run_id(authorizing_state_core(period_ctx)) != first


def test_naked_translation_factor_without_live_observations_fails():
    table = {
        "series": [
            {
                "component": component,
                "source_data_year": _source_year(COMPONENT_FRESHNESS_FAMILY[component], year),
                "project_cost_year": year,
                "official_series_identifier": _series_id(component),
                "publisher": "BLS",
                "observation_period": f"{year} annual",
                "source_artifact": _artifact(component),
                "sha256": _sha(component, year),
                "translation_factor": 1.02,
                "retrieval_validation_state": "VALIDATED",
            }
            for component, year in FROZEN_CPI_UPDATED_PAIRS
        ]
    }
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert any(issue.endswith(":TRANSLATION_FACTOR_UNBOUND") for issue in result["issues"])


def test_vague_bls_landing_without_series_inventory_fails_closed():
    checks = {family: _ready_family(family) for family in REQUIRED_FRESHNESS_FAMILIES}
    checks["od010_price_index"] = _ready_family(
        "od010_price_index",
        publisher="BLS",
        landing_url="https://www.bls.gov/cpi/",
        series_coverage=None,
    )
    result = validate_od010_bindings_against_snapshot(_complete_od010(), checks, years=(2024, 2026))
    assert result["ok"] is False
    assert "OD010_SERIES_COVERAGE_TOO_VAGUE" in result["issues"]
    assert od010_series_inventory_is_specific(checks["od010_price_index"]) is False


def test_discover_od010_uses_official_series_when_table_exists():
    check = discover_od010()
    table = METADATA / "living_cost_od010_translation_table.json"
    if not table.exists():
        assert check.freshness_check_status == "MANUAL_VERIFICATION_REQUIRED"
        return
    assert check.publisher == "BLS"
    coverage = check.series_coverage or {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        slot = coverage[component][str(year)]
        assert slot["covered"] is True
        assert str(slot["official_series_identifier"]).startswith("CUUR0000")
        assert slot["base_index_value"] not in (None, "", 0, 0.0)
    assert od010_series_inventory_is_specific(check) is True


def test_current_production_state_stays_fail_closed():
    assert not (METADATA / "living_cost_candidate_input_bindings.json").exists()
    from foundation.config import definitions

    cfg = definitions()["living_cost"]
    assert cfg["candidate_calculation_authorized"] is False
    assert cfg["release_authorized"] is False
    assert cfg["required_project_cost_years"] == [2024, 2026]
    freshness = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    assert freshness["candidate_inputs_bound"] is False
    assert freshness["candidate_calculation_authorized"] is False
    assert freshness["living_cost_release_authorized"] is False
    assert freshness["ready_for_private_candidate"] is False
    ctx = build_live_readiness_context(
        {family: _ready_family(family) for family in REQUIRED_FRESHNESS_FAMILIES}
    )
    assert ctx["candidate_inputs_bound"] is False
    assert ctx["calculates_mslc"] is False
    assert ctx["candidate_calculation_authorized"] is False


def test_record_hash_still_binds_to_exact_captured_record():
    rec = _od010_record("health_oop", 2024)
    first = od010_record_hash(rec)
    mutated = copy.deepcopy(rec)
    mutated["official_series_identifier"] = "OTHER"
    assert od010_record_hash(mutated) != first
    assert od010_record_hash(rec) == first
