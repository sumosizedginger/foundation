"""Raw BLS response SHA is not observation currentness.

Does not calculate an MSLC. No live network.
"""

from __future__ import annotations

import copy

from foundation.living_cost.candidate_bindings import validate_od010_bindings_against_snapshot
from foundation.living_cost.freshness import FreshnessCheck
from foundation.living_cost.od010_cpi import (
    FROZEN_OD010_SERIES,
    build_od010_records,
    compute_observation_set_sha256,
    required_od010_series_ids,
)


def _body(*, response_time: str = "1 ms") -> dict:
    return {
        "status": "REQUEST_SUCCEEDED",
        "responseTime": response_time,
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
                        {
                            "year": "2026",
                            "period": "M07",
                            "periodName": "July",
                            "value": "120.0",
                        },
                    ],
                }
                for spec in FROZEN_OD010_SERIES.values()
            ]
        },
    }


def _retrieve(body: dict, raw_sha: str) -> dict:
    return {
        "retrieved_at": "2026-08-16T00:00:00Z",
        "sha256": raw_sha,
        "raw_response_sha256": raw_sha,
        "observation_set_sha256": compute_observation_set_sha256(body),
        "byte_size": 12,
        "body": body,
    }


def test_required_series_ids_are_frozen_official():
    assert required_od010_series_ids() == [
        "CUUR0000SAM",
        "CUUR0000SETE",
        "CUUR0000SETD",
        "CUUR0000SAR",
        "CUUR0000SA0",
    ]


def test_observation_identity_ignores_volatile_response_time():
    a = compute_observation_set_sha256(_body(response_time="10 ms"))
    b = compute_observation_set_sha256(_body(response_time="999 ms"))
    assert a == b
    assert len(a) == 64


def test_raw_sha_may_differ_while_observation_identity_matches():
    body = _body()
    first = build_od010_records(_retrieve(body, "raw-aaa"))
    second = build_od010_records(_retrieve(body, "raw-bbb"))
    assert first["raw_response_sha256"] != second["raw_response_sha256"]
    assert first["observation_set_sha256"] == second["observation_set_sha256"]
    assert first["series"][0]["sha256"] == first["observation_set_sha256"]
    assert first["series"][0]["raw_response_sha256"] == "raw-aaa"


def test_cross_bind_uses_observation_identity_not_raw_sha():
    body = _body()
    table = build_od010_records(_retrieve(body, "raw-table"))
    live = build_od010_records(_retrieve(body, "raw-live-different"))
    check = FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at="2026-08-16T00:00:00Z",
        latest_authoritative_vintage_found="BLS",
        selected_vintage="BLS",
        selected_artifact=live["api_identity"],
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
        publisher="BLS",
        series_coverage=live["series_coverage"],
    )
    result = validate_od010_bindings_against_snapshot(
        table, {"od010_price_index": check}, years=(2024, 2026)
    )
    assert result["ok"] is True, result["issues"]


def test_newer_target_month_changes_observation_identity():
    older = _body()
    newer = copy.deepcopy(older)
    for series in newer["Results"]["series"]:
        series["data"].append(
            {"year": "2026", "period": "M08", "periodName": "August", "value": "121.0"}
        )
    assert compute_observation_set_sha256(older) != compute_observation_set_sha256(newer)
