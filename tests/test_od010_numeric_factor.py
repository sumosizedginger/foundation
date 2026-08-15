"""Adversarial tests for OD-010 numeric observation / factor integrity.

Does not calculate an MSLC. Does not create a production translation table.
No live-network calls.
"""

from __future__ import annotations

import math
from pathlib import Path

from foundation.living_cost.candidate_bindings import (
    COMPONENT_FRESHNESS_FAMILY,
    CPI_UPDATED_FACTOR_OPERATION,
    FROZEN_CPI_UPDATED_PAIRS,
    factors_equal,
    index_values_equal,
    od010_series_inventory_is_specific,
    recompute_cpi_updated_factor,
    validate_od010_bindings_against_snapshot,
)
from foundation.living_cost.freshness import (
    REQUIRED_FRESHNESS_FAMILIES,
    FreshnessCheck,
    authorizing_state_core,
    build_live_readiness_context,
    compute_freshness_run_id,
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
        "base_index_value": 100,
        "target_index_value": 102,
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
            "base_index_value": 100,
            "target_observation_period": f"{year} annual",
            "target_index_value": 102,
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


def _mutate_one(table: dict[str, object], component: str, year: int, **changes: object) -> None:
    for rec in table["series"]:  # type: ignore[union-attr]
        if rec["component"] == component and rec["project_cost_year"] == year:
            calc = dict(rec.get("calculation_inputs") or {})
            calc_changes = changes.pop("calculation_inputs", None)
            rec.update(changes)
            if isinstance(calc_changes, dict):
                calc.update(calc_changes)
                rec["calculation_inputs"] = calc
            elif rec.get("calculation_inputs") is not None:
                rec["calculation_inputs"] = calc
            return


def test_cpi_updated_factor_is_target_over_base():
    assert CPI_UPDATED_FACTOR_OPERATION == "target_index_value / base_index_value"
    assert recompute_cpi_updated_factor(100, 102) == recompute_cpi_updated_factor("100", "102")
    assert factors_equal(recompute_cpi_updated_factor(100, 102), 1.02)
    assert index_values_equal(100, "100.0")
    assert not index_values_equal(100, 99)


def test_a_table_base_differs_from_live_fails():
    table = _complete_od010()
    _mutate_one(
        table,
        "health_oop",
        2024,
        calculation_inputs={"base_index_value": 99},
    )
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "health_oop:2024:CALC_BASE_VALUE_MISMATCH" in result["issues"]


def test_b_table_target_differs_from_live_fails():
    table = _complete_od010()
    _mutate_one(
        table,
        "insurance",
        2026,
        calculation_inputs={"target_index_value": 103},
    )
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "insurance:2026:CALC_TARGET_VALUE_MISMATCH" in result["issues"]


def test_c_record_factor_not_derived_from_observations_fails():
    table = _complete_od010()
    _mutate_one(table, "essentials", 2026, translation_factor=9.99)
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "essentials:2026:TRANSLATION_FACTOR_MISMATCH" in result["issues"]


def test_d_calc_factor_disagrees_with_record_factor_fails():
    table = _complete_od010()
    _mutate_one(
        table,
        "recreation",
        2026,
        translation_factor=1.02,
        calculation_inputs={"translation_factor": 1.03},
    )
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "recreation:2026:TRANSLATION_FACTOR_MISMATCH" in result["issues"]


def test_e_calc_sha_differs_from_matching_record_and_live_sha_fails():
    table = _complete_od010()
    _mutate_one(
        table,
        "maintenance",
        2026,
        calculation_inputs={"sha256": "DIFFERENT-CALC-BYTES"},
    )
    result = validate_od010_bindings_against_snapshot(
        table, _all_ready_with_od010_series(), years=(2024, 2026)
    )
    assert result["ok"] is False
    assert "maintenance:2026:CALC_ARTIFACT_HASH_MISMATCH" in result["issues"]
    assert "maintenance:2026:ARTIFACT_HASH_MISMATCH" not in result["issues"]


def test_f_zero_base_fails():
    result = validate_od010_bindings_against_snapshot(
        _complete_od010(),
        _all_ready_with_od010_series(
            **{"health_oop:2024": _series_slot("health_oop", 2024, base_index_value=0)}
        ),
        years=(2024, 2026),
    )
    assert result["ok"] is False
    assert "health_oop:2024:INVALID_BASE_INDEX_VALUE" in result["issues"] or (
        "OD010_SERIES_COVERAGE_TOO_VAGUE" in result["issues"]
    )
    assert not od010_series_inventory_is_specific(
        _all_ready_with_od010_series(
            **{"health_oop:2024": _series_slot("health_oop", 2024, base_index_value=0)}
        )["od010_price_index"],
        years=(2024, 2026),
    )


def test_g_nan_inf_negative_index_values_fail():
    for bad in (float("nan"), float("inf"), -5):
        checks = _all_ready_with_od010_series(
            **{"insurance:2024": _series_slot("insurance", 2024, target_index_value=bad)}
        )
        result = validate_od010_bindings_against_snapshot(
            _complete_od010(), checks, years=(2024, 2026)
        )
        assert result["ok"] is False
        assert not od010_series_inventory_is_specific(
            checks["od010_price_index"], years=(2024, 2026)
        )
        if math.isnan(bad) if isinstance(bad, float) else False:
            assert "insurance:2024:INVALID_TARGET_INDEX_VALUE" in result["issues"] or (
                "OD010_SERIES_COVERAGE_TOO_VAGUE" in result["issues"]
            )


def test_h_correct_values_and_factor_may_pass():
    result = validate_od010_bindings_against_snapshot(
        _complete_od010(),
        _all_ready_with_od010_series(),
        years=(2024, 2026),
    )
    assert result["ok"] is True
    assert result["issues"] == []
    row = next(
        item
        for item in result["normalized"]
        if item["component"] == "health_oop" and item["project_cost_year"] == 2024
    )
    assert row["live_base_index_value"] == 100
    assert row["table_base_index_value"] == 100
    assert row["live_target_index_value"] == 102
    assert row["table_target_index_value"] == 102
    assert row["claimed_translation_factor"] == 1.02
    assert row["calculation_input_translation_factor"] == 1.02
    assert factors_equal(row["recomputed_translation_factor"], 1.02)


def test_i_changing_only_live_index_value_changes_freshness_run_id():
    table = _complete_od010()
    first_ctx = build_live_readiness_context(
        _all_ready_with_od010_series(),
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    first = compute_freshness_run_id(authorizing_state_core(first_ctx))
    changed = _all_ready_with_od010_series(
        **{
            "health_oop:2024": _series_slot(
                "health_oop", 2024, base_index_value=101, target_index_value=102
            )
        }
    )
    second_ctx = build_live_readiness_context(
        changed,
        candidate_payload=None,
        od010_payload=table,
        generated_at="2026-08-15T12:00:00Z",
    )
    second = compute_freshness_run_id(authorizing_state_core(second_ctx))
    assert first != second
    pair = next(
        item
        for item in first_ctx["od010_cross_binding"]["normalized"]
        if item["component"] == "health_oop" and item["project_cost_year"] == 2024
    )
    assert "live_base_index_value" in pair
    assert "recomputed_translation_factor" in pair


def test_production_state_stays_fail_closed():
    import json

    from foundation.config import definitions

    assert not (METADATA / "living_cost_od010_translation_table.json").exists()
    cfg = definitions()["living_cost"]
    assert cfg["candidate_calculation_authorized"] is False
    assert cfg["release_authorized"] is False
    freshness = json.loads((METADATA / "living_cost_candidate_freshness.json").read_text())
    od010 = freshness["checks"]["od010_price_index"]
    assert od010["freshness_check_status"] == "MANUAL_VERIFICATION_REQUIRED"
    assert od010["retrieval_validation_status"] == "INVENTORY_NOT_VALIDATED"
    assert freshness["translation_index_bound"] is False
    assert freshness["candidate_inputs_bound"] is False
    assert freshness["ready_for_private_candidate"] is False
    assert (freshness.get("od010_cross_binding") or {}).get("ok") is False
    coverage = od010.get("series_coverage") or {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        slot = coverage[component][str(year)]
        assert slot["covered"] is False
        assert (
            slot.get("base_index_value") in (None, 0, 0.0) or slot.get("base_index_value") is None
        )
        assert slot.get("official_series_identifier") is None
