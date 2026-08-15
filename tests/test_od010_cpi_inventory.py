"""Official BLS CPI inventory for frozen OD-010 pairs.

Does not calculate an MSLC. Uses the committed official retrieve/table
or a source-free builder fixture. No live network in this file.
"""

from __future__ import annotations

import json
from pathlib import Path

from foundation.living_cost.candidate_bindings import (
    FROZEN_CPI_UPDATED_PAIRS,
    evaluate_od010_translation_table,
    od010_series_inventory_is_specific,
    validate_od010_bindings_against_snapshot,
)
from foundation.living_cost.freshness import FreshnessCheck
from foundation.living_cost.od010_cpi import (
    DEFAULT_SOURCE_DATA_YEAR,
    FROZEN_OD010_SERIES,
    build_od010_records,
)

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / "data" / "metadata"
TABLE = METADATA / "living_cost_od010_translation_table.json"


def test_frozen_series_ids_are_official_bls_cuur():
    assert FROZEN_OD010_SERIES["health_oop"]["official_series_identifier"] == "CUUR0000SAM"
    assert FROZEN_OD010_SERIES["insurance"]["official_series_identifier"] == "CUUR0000SETE"
    assert FROZEN_OD010_SERIES["maintenance"]["official_series_identifier"] == "CUUR0000SETD"
    assert FROZEN_OD010_SERIES["recreation"]["official_series_identifier"] == "CUUR0000SAR"
    assert FROZEN_OD010_SERIES["essentials"]["official_series_identifier"] == "CUUR0000SA0"
    assert FROZEN_OD010_SERIES["essentials"]["disclosure"]
    assert DEFAULT_SOURCE_DATA_YEAR["health_oop"] == 2023
    assert DEFAULT_SOURCE_DATA_YEAR["insurance"] == 2023
    assert DEFAULT_SOURCE_DATA_YEAR["maintenance"] == 2024


def test_builder_from_source_free_bls_fixture():
    body = {
        "status": "REQUEST_SUCCEEDED",
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
    retrieve = {
        "retrieved_at": "2026-08-15T20:00:00Z",
        "sha256": "abc123fixture",
        "byte_size": 12,
        "body": body,
    }
    table = build_od010_records(retrieve)
    assert table["bound"] is True
    assert table["calculates_mslc"] is False
    assert len(table["series"]) == 7
    health_2024 = next(
        rec
        for rec in table["series"]
        if rec["component"] == "health_oop" and rec["project_cost_year"] == 2024
    )
    assert health_2024["source_data_year"] == 2023
    assert health_2024["calculation_inputs"]["base_index_value"] == "100.0"
    assert health_2024["calculation_inputs"]["target_index_value"] == "110.0"
    check = FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at="2026-08-15T20:00:00Z",
        latest_authoritative_vintage_found="2026-07",
        selected_vintage="2026-07",
        selected_artifact="https://api.bls.gov/publicAPI/v2/timeseries/data/",
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
        publisher="BLS",
        series_coverage=table["series_coverage"],
    )
    assert od010_series_inventory_is_specific(check, years=(2024, 2026)) is True
    result = validate_od010_bindings_against_snapshot(
        table, {"od010_price_index": check}, years=(2024, 2026)
    )
    assert result["ok"] is True
    assert result["issues"] == []


def test_committed_official_table_cross_binds_if_present():
    if not TABLE.exists():
        return
    table = json.loads(TABLE.read_text(encoding="utf-8"))
    structural = evaluate_od010_translation_table(table, years=(2024, 2026))
    assert structural["bound"] is True
    assert table["calculates_mslc"] is False
    check = FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at=table["generated_at"],
        latest_authoritative_vintage_found="BLS",
        selected_vintage="BLS",
        selected_artifact=table["api_identity"],
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
        publisher="BLS",
        series_coverage=table["series_coverage"],
    )
    result = validate_od010_bindings_against_snapshot(
        table, {"od010_price_index": check}, years=(2024, 2026)
    )
    assert result["ok"] is True, result["issues"]
    ids = {rec["official_series_identifier"] for rec in table["series"]}
    assert ids == {
        "CUUR0000SAM",
        "CUUR0000SETE",
        "CUUR0000SETD",
        "CUUR0000SAR",
        "CUUR0000SA0",
    }
    assert len(FROZEN_CPI_UPDATED_PAIRS) == 7
