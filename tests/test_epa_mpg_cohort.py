"""EPA/DOE official MPG cohort derivation. Does not calculate an MSLC."""

from __future__ import annotations

import json
from pathlib import Path

from foundation.sources.epa_mpg import filter_funnel

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cache" / "epa_fueleconomy_vehicles.csv.zip"
REPORT = ROOT / "data" / "metadata" / "living_cost_epa_mpg_cohorts.json"


def test_committed_epa_cohort_report_matches_official_bytes():
    if not CACHE.exists() or not REPORT.exists():
        return
    payload = json.loads(REPORT.read_text(encoding="utf-8"))
    assert payload["calculates_mslc"] is False
    assert payload["combined_mpg_field"] == "comb08"
    assert payload["canonical_vclass_values"] == ["Compact Cars", "Midsize Cars"]
    import hashlib

    assert payload["sha256"] == hashlib.sha256(CACHE.read_bytes()).hexdigest()
    c2024 = payload["cohorts"]["2024"]
    c2026 = payload["cohorts"]["2026"]
    assert c2024["model_year_low"] == 2012
    assert c2024["model_year_high"] == 2016
    assert c2026["model_year_low"] == 2014
    assert c2026["model_year_high"] == 2018
    assert c2024["final_cohort_row_count"] > 1000
    assert c2026["final_cohort_row_count"] > 1000
    assert c2024["median_mpg"] is not None
    assert c2026["median_mpg"] is not None


def test_filter_funnel_on_tiny_fixture():
    rows = [
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "atvType": "",
            "VClass": "Compact Cars",
            "comb08": "30",
        },
        {
            "year": "2013",
            "fuelType1": "Electricity",
            "atvType": "EV",
            "VClass": "Compact Cars",
            "comb08": "110",
        },
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "atvType": "",
            "VClass": "Sport Utility Vehicle",
            "comb08": "18",
        },
    ]
    report = filter_funnel(rows, 2024)
    assert report["rows_after_fuel_filter"] == 2
    assert report["rows_after_body_class_filter"] == 1
    assert report["final_cohort_row_count"] == 1
    assert report["median_mpg"] == 30.0
    assert report["canonical_vclass_values"] == ["Compact Cars", "Midsize Cars"]
    assert report["canonical_mpg_field"] == "comb08"


def test_subcompact_and_minicompact_are_not_canonical():
    rows = [
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Subcompact Cars",
            "comb08": "40",
        },
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Minicompact Cars",
            "comb08": "41",
        },
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Compact Cars",
            "comb08": "22",
        },
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Midsize Cars",
            "comb08": "24",
        },
    ]
    report = filter_funnel(rows, 2024)
    assert report["rows_after_body_class_filter"] == 2
    assert report["final_cohort_row_count"] == 2
    assert report["median_mpg"] in {22.0, 23.0, 24.0}
    assert report["median_mpg"] not in {40.0, 41.0}
    assert report["compact_only_median_mpg"] == 22.0
    assert report["midsize_only_median_mpg"] == 24.0


def test_canonical_mpg_requires_comb08_and_does_not_use_ucity():
    rows = [
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Compact Cars",
            "comb08": "",
            "UCity": "99",
            "combA08": "88",
        },
        {
            "year": "2013",
            "fuelType1": "Regular Gasoline",
            "VClass": "Midsize Cars",
            "comb08": "21",
        },
    ]
    report = filter_funnel(rows, 2024)
    assert report["rows_after_model_year_filter"] == 2
    assert report["rows_missing_canonical_comb08"] == 1
    assert report["final_cohort_row_count"] == 1
    assert report["median_mpg"] == 21.0
