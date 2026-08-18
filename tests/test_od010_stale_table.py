"""Regression: stale bound OD-010 table cannot remain canonical current.

Does not calculate an MSLC.
"""

from __future__ import annotations

import json
from pathlib import Path

from foundation.living_cost import od010_cpi
from foundation.living_cost.candidate_bindings import od010_translation_is_bound
from foundation.living_cost.od010_cpi import (
    FROZEN_OD010_SERIES,
    build_od010_records,
    write_od010_artifacts,
)


def _retrieve(tmp_path: Path, *, include_2026: bool) -> dict:
    data_rows = [
        {"year": "2023", "period": "M13", "periodName": "Annual", "value": "100.0"},
        {"year": "2024", "period": "M13", "periodName": "Annual", "value": "110.0"},
    ]
    if include_2026:
        data_rows.append({"year": "2026", "period": "M07", "periodName": "July", "value": "120.0"})
    body = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [
                {
                    "seriesID": spec["official_series_identifier"],
                    "data": data_rows,
                }
                for spec in FROZEN_OD010_SERIES.values()
            ]
        },
    }
    return {
        "retrieved_at": "2026-08-16T00:00:00Z",
        "http_status": 200,
        "request_url": "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        "request_payload": {"seriesid": []},
        "byte_size": 99,
        "sha256": "raw-sha-fixture",
        "raw_response_sha256": "raw-sha-fixture",
        "body": body,
    }


def test_unbound_retrieve_does_not_leave_stale_bound_table(tmp_path: Path, monkeypatch):
    metadata = tmp_path / "metadata"
    metadata.mkdir()
    history = metadata / "history"
    table = metadata / "living_cost_od010_translation_table.json"
    retrieve_path = metadata / "living_cost_od010_bls_retrieve.json"
    monkeypatch.setattr(od010_cpi, "METADATA_DIR", metadata)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE", table)
    monkeypatch.setattr(od010_cpi, "OD010_RETRIEVE", retrieve_path)
    monkeypatch.setattr(od010_cpi, "OD010_TABLE_HISTORY_DIR", history)

    complete = build_od010_records(_retrieve(tmp_path, include_2026=True))
    assert complete["bound"] is True
    write_od010_artifacts(_retrieve(tmp_path, include_2026=True), complete)
    assert table.exists()
    assert od010_translation_is_bound(table) is True

    incomplete = build_od010_records(_retrieve(tmp_path, include_2026=False))
    assert incomplete["bound"] is False
    write_od010_artifacts(_retrieve(tmp_path, include_2026=False), incomplete)

    current = json.loads(table.read_text(encoding="utf-8"))
    assert current["bound"] is False
    assert od010_translation_is_bound(table) is False
    archived = list(history.glob("living_cost_od010_translation_table_*.json"))
    assert archived, "prior bound table must be archived"
    prior = json.loads(archived[0].read_text(encoding="utf-8"))
    assert prior["bound"] is True
