"""discover_od010 must perform a live BLS request and not trust cache.

Does not calculate an MSLC.
"""

from __future__ import annotations

from foundation.living_cost import od010_cpi
from foundation.living_cost.freshness import is_translation_index_bound
from foundation.living_cost.freshness_discovery import discover_od010
from foundation.living_cost.od010_cpi import (
    FROZEN_OD010_SERIES,
    build_od010_records,
    compute_observation_set_sha256,
    write_od010_artifacts,
)


def _body(*, august: bool = False) -> dict:
    month = (
        {"year": "2026", "period": "M08", "periodName": "August", "value": "121.0"}
        if august
        else {"year": "2026", "period": "M07", "periodName": "July", "value": "120.0"}
    )
    return {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": "volatile",
        "Results": {
            "series": [
                {
                    "seriesID": spec["official_series_identifier"],
                    "data": [
                        {
                            "year": "2023",
                            "period": "M13",
                            "periodName": "Annual",
                            "value": "100.0",
                        },
                        {
                            "year": "2024",
                            "period": "M13",
                            "periodName": "Annual",
                            "value": "110.0",
                        },
                        month,
                    ],
                }
                for spec in FROZEN_OD010_SERIES.values()
            ]
        },
    }


def _retrieve(body: dict, raw_sha: str) -> dict:
    return {
        "retrieved_at": "2026-08-16T12:00:00Z",
        "http_status": 200,
        "request_url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "request_payload": {"seriesid": []},
        "byte_size": 20,
        "sha256": raw_sha,
        "raw_response_sha256": raw_sha,
        "observation_set_sha256": compute_observation_set_sha256(body),
        "body": body,
    }


def test_discover_uses_live_retrieve_not_cached_table(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    table = metadata / "living_cost_od010_translation_table.json"
    retrieve_path = metadata / "living_cost_od010_bls_retrieve.json"
    currentness = metadata / "living_cost_od010_live_currentness.json"
    history = metadata / "history"
    monkeypatch.setattr(od010_cpi, "METADATA_DIR", metadata)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE", table)
    monkeypatch.setattr(od010_cpi, "OD010_RETRIEVE", retrieve_path)
    monkeypatch.setattr(od010_cpi, "OD010_LIVE_CURRENTNESS", currentness)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE_HISTORY_DIR", history)
    monkeypatch.setattr("foundation.living_cost.freshness_discovery.METADATA_DIR", metadata)
    monkeypatch.setattr("foundation.living_cost.freshness.OD010_TABLE", table)

    july = _body(august=False)
    write_od010_artifacts(
        _retrieve(july, "raw-cached"), build_od010_records(_retrieve(july, "raw-cached"))
    )

    live_calls = {"n": 0}

    def fake_retrieve(*_args, **_kwargs):
        live_calls["n"] += 1
        return _retrieve(july, "raw-live-different")

    monkeypatch.setattr(od010_cpi, "retrieve_bls_cpi_series", fake_retrieve)
    check = discover_od010()
    assert live_calls["n"] == 1
    assert check.freshness_check_status == "VERIFIED_CURRENT"
    assert check.extra["raw_response_sha256"] == "raw-live-different"
    assert check.extra["observation_set_sha256"] == compute_observation_set_sha256(july)
    assert check.series_coverage["health_oop"]["2026"]["target_observation_period"] == "2026 July"


def test_discover_marks_newer_available_and_unbinds(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    table = metadata / "living_cost_od010_translation_table.json"
    retrieve_path = metadata / "living_cost_od010_bls_retrieve.json"
    currentness = metadata / "living_cost_od010_live_currentness.json"
    history = metadata / "history"
    monkeypatch.setattr(od010_cpi, "METADATA_DIR", metadata)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE", table)
    monkeypatch.setattr(od010_cpi, "OD010_RETRIEVE", retrieve_path)
    monkeypatch.setattr(od010_cpi, "OD010_LIVE_CURRENTNESS", currentness)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE_HISTORY_DIR", history)
    monkeypatch.setattr("foundation.living_cost.freshness_discovery.METADATA_DIR", metadata)
    monkeypatch.setattr("foundation.living_cost.freshness.OD010_TABLE", table)

    july = _body(august=False)
    write_od010_artifacts(
        _retrieve(july, "raw-cached"), build_od010_records(_retrieve(july, "raw-cached"))
    )
    assert is_translation_index_bound() is True

    def fake_retrieve(*_args, **_kwargs):
        return _retrieve(_body(august=True), "raw-live-aug")

    monkeypatch.setattr(od010_cpi, "retrieve_bls_cpi_series", fake_retrieve)
    check = discover_od010()
    assert check.freshness_check_status == "NEWER_AVAILABLE"
    assert check.newer_data_exists is True
    assert check.extra["translation_table_bound"] is False
    assert is_translation_index_bound() is False


def test_discover_check_failed_does_not_use_cache_as_verified(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    table = metadata / "living_cost_od010_translation_table.json"
    retrieve_path = metadata / "living_cost_od010_bls_retrieve.json"
    currentness = metadata / "living_cost_od010_live_currentness.json"
    history = metadata / "history"
    monkeypatch.setattr(od010_cpi, "METADATA_DIR", metadata)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE", table)
    monkeypatch.setattr(od010_cpi, "OD010_RETRIEVE", retrieve_path)
    monkeypatch.setattr(od010_cpi, "OD010_LIVE_CURRENTNESS", currentness)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE_HISTORY_DIR", history)
    monkeypatch.setattr("foundation.living_cost.freshness_discovery.METADATA_DIR", metadata)

    july = _body(august=False)
    write_od010_artifacts(
        _retrieve(july, "raw-cached"), build_od010_records(_retrieve(july, "raw-cached"))
    )

    def boom(*_args, **_kwargs):
        raise RuntimeError("BLS down")

    monkeypatch.setattr(od010_cpi, "retrieve_bls_cpi_series", boom)
    check = discover_od010()
    assert check.freshness_check_status == "CHECK_FAILED"
    assert check.newer_data_exists is None
    assert (
        check.retrieval_validation_status != "VALIDATED"
        or check.freshness_check_status != "VERIFIED_CURRENT"
    )
    assert "failed" in (check.reason_if_not_refreshed or "").lower()
    assert is_translation_index_bound() is True


def test_live_identity_mismatch_unbinds_translation_index(tmp_path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    table = metadata / "living_cost_od010_translation_table.json"
    retrieve_path = metadata / "living_cost_od010_bls_retrieve.json"
    currentness = metadata / "living_cost_od010_live_currentness.json"
    history = metadata / "history"
    monkeypatch.setattr(od010_cpi, "METADATA_DIR", metadata)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE", table)
    monkeypatch.setattr(od010_cpi, "OD010_RETRIEVE", retrieve_path)
    monkeypatch.setattr(od010_cpi, "OD010_LIVE_CURRENTNESS", currentness)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE_HISTORY_DIR", history)
    monkeypatch.setattr("foundation.living_cost.freshness_discovery.METADATA_DIR", metadata)
    monkeypatch.setattr("foundation.living_cost.freshness.OD010_TABLE", table)

    july = _body(august=False)
    write_od010_artifacts(
        _retrieve(july, "raw-cached"), build_od010_records(_retrieve(july, "raw-cached"))
    )
    mutated = _body(august=False)
    mutated["Results"]["series"][0]["data"][0]["value"] = "999.0"

    def fake_retrieve(*_args, **_kwargs):
        return _retrieve(mutated, "raw-live-mismatch")

    monkeypatch.setattr(od010_cpi, "retrieve_bls_cpi_series", fake_retrieve)
    check = discover_od010()
    assert check.freshness_check_status != "VERIFIED_CURRENT"
    assert check.extra["translation_table_bound"] is False
    assert is_translation_index_bound() is False
