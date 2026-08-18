"""Coverage promotion must validate derivation, not file existence.

Does not calculate an MSLC.
"""

from __future__ import annotations

import json
from pathlib import Path

from foundation.living_cost.evidence_validators import (
    MODELED,
    NOT_MODELED,
    epa_evidence_status,
    meps_evidence_status,
    selected_cache_sha,
    validate_epa_cohorts,
    validate_meps_derivation,
)


def _meps_ok(sha: str = "aaa") -> dict:
    return {
        "report_type": "living_cost_meps_oop_derivation",
        "source_data_year": 2023,
        "puf_id": "HC-251",
        "source_variable": "TOTSLF23",
        "weight_variable": "PERWT23F",
        "age_variable": "AGELAST",
        "insurance_variable": "INSCOV23",
        "insurance_code": 1,
        "insurance_code_label": "ANY PRIVATE",
        "age_low": 18,
        "age_high": 64,
        "weighted_mean": 1117.72,
        "weighted_median": 311.0,
        "weighted_p75": 1114.0,
        "layout": {"AGELAST": [194, 195]},
        "sha256": sha,
        "evidence_status": MODELED,
        "calculates_mslc": False,
    }


def _epa_ok(sha: str = "bbb") -> dict:
    cohort = {
        "model_year_low": 2012,
        "model_year_high": 2016,
        "final_cohort_row_count": 10,
        "median_mpg": 26.0,
        "mean_mpg": 26.1,
        "compact_only_median_mpg": 25.0,
        "midsize_only_median_mpg": 27.0,
        "canonical_mpg_field": "comb08",
    }
    c2026 = dict(cohort)
    c2026["model_year_low"] = 2014
    c2026["model_year_high"] = 2018
    return {
        "report_type": "living_cost_epa_mpg_cohorts",
        "sha256": sha,
        "combined_mpg_field": "comb08",
        "canonical_vclass_values": ["Compact Cars", "Midsize Cars"],
        "cohorts": {"2024": cohort, "2026": c2026},
        "calculates_mslc": False,
    }


def test_meps_sha_mismatch_is_not_modeled(tmp_path: Path):
    report = tmp_path / "meps.json"
    report.write_text(json.dumps(_meps_ok("sha-A")), encoding="utf-8")
    result = validate_meps_derivation(report, selected_sha="sha-B")
    assert result.ok is False
    assert result.evidence_status == NOT_MODELED
    assert "MEPS_REPORT_SHA_MISMATCH" in result.issues
    assert meps_evidence_status(report, selected_sha="sha-B") != MODELED


def test_epa_sha_mismatch_is_not_modeled(tmp_path: Path):
    report = tmp_path / "epa.json"
    report.write_text(json.dumps(_epa_ok("sha-A")), encoding="utf-8")
    result = validate_epa_cohorts(report, selected_sha="sha-B")
    assert result.ok is False
    assert result.evidence_status == NOT_MODELED
    assert "EPA_REPORT_SHA_MISMATCH" in result.issues
    assert epa_evidence_status(report, selected_sha="sha-B") != MODELED


def test_corrupt_meps_fields_fail_closed(tmp_path: Path):
    payload = _meps_ok()
    payload["weighted_mean"] = None
    payload["insurance_code_label"] = "throughout the year"
    report = tmp_path / "meps.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_meps_derivation(report, selected_sha="aaa")
    assert result.ok is False
    assert "MEPS_WEIGHTED_MEAN_INVALID" in result.issues


def test_corrupt_epa_fields_fail_closed(tmp_path: Path):
    payload = _epa_ok()
    payload["canonical_vclass_values"] = ["Compact Cars", "Subcompact Cars", "Midsize Cars"]
    payload["cohorts"]["2024"]["final_cohort_row_count"] = 0
    report = tmp_path / "epa.json"
    report.write_text(json.dumps(payload), encoding="utf-8")
    result = validate_epa_cohorts(report, selected_sha="bbb")
    assert result.ok is False
    assert "EPA_CANONICAL_VCLASS_NOT_EXACT_COMPACT_MIDSIZE" in result.issues
    assert "EPA_FINAL_ROWS_INVALID:2024" in result.issues


def test_file_existence_alone_is_not_modeled(tmp_path: Path):
    empty = tmp_path / "empty.json"
    empty.write_text("{}", encoding="utf-8")
    assert validate_meps_derivation(empty, selected_sha="x").ok is False
    assert validate_epa_cohorts(empty, selected_sha="x").ok is False


def test_freshness_discovery_hashes_selected_cache_bytes():
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "foundation"
        / "living_cost"
        / "freshness_discovery.py"
    ).read_text(encoding="utf-8")
    assert "selected_cache_sha(MEPS_CACHE_NAME)" in src
    assert "selected_cache_sha(EPA_CACHE_NAME)" in src
    assert "validate_meps_derivation(selected_sha=(sidecar" not in src
    assert "validate_epa_cohorts(selected_sha=(sidecar" not in src


def test_selected_cache_sha_prefers_file_bytes_over_sidecar(tmp_path: Path, monkeypatch):
    from foundation.living_cost import evidence_validators as ev

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    blob = cache_dir / "h251dat.zip"
    blob.write_bytes(b"official-bytes")
    sidecar = cache_dir / "h251dat.zip.provenance.json"
    sidecar.write_text('{"sha256": "sidecar-does-not-match-file"}', encoding="utf-8")
    monkeypatch.setattr(ev, "CACHE_DIR", cache_dir)
    import hashlib

    assert selected_cache_sha("h251dat.zip") == hashlib.sha256(b"official-bytes").hexdigest()


def test_valid_reports_promote(tmp_path: Path):
    meps = tmp_path / "meps.json"
    epa = tmp_path / "epa.json"
    meps.write_text(json.dumps(_meps_ok("ok-m")), encoding="utf-8")
    epa.write_text(json.dumps(_epa_ok("ok-e")), encoding="utf-8")
    assert validate_meps_derivation(meps, selected_sha="ok-m").ok is True
    assert validate_epa_cohorts(epa, selected_sha="ok-e").ok is True
    assert meps_evidence_status(meps, selected_sha="ok-m") == MODELED
    assert epa_evidence_status(epa, selected_sha="ok-e") == MODELED
