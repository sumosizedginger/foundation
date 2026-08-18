"""Canonical evidence-status helpers for MEPS OOP and EPA MPG reports.

File existence is not evidence. write_coverage(), freshness discovery,
write_transport_coverage(), and public status renderers must use these
helpers. Does not calculate an MSLC.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
CACHE_DIR = PROJECT_ROOT / "data" / "cache"

MEPS_DERIVATION_PATH = METADATA_DIR / "living_cost_meps_oop_derivation.json"
EPA_COHORT_PATH = METADATA_DIR / "living_cost_epa_mpg_cohorts.json"
MEPS_CACHE_NAME = "h251dat.zip"
EPA_CACHE_NAME = "epa_fueleconomy_vehicles.csv.zip"

MEPS_REPORT_TYPE = "living_cost_meps_oop_derivation"
EPA_REPORT_TYPE = "living_cost_epa_mpg_cohorts"
MODELED = "MODELED_FROM_MEASURED_INPUTS"
NOT_MODELED = "RETRIEVED_UNVALIDATED"

CANONICAL_EPA_VCLASS = ("Compact Cars", "Midsize Cars")
CANONICAL_MPG_FIELD = "comb08"
FROZEN_EPA_WINDOWS: dict[int, tuple[int, int]] = {
    2024: (2012, 2016),
    2026: (2014, 2018),
}


@dataclass(frozen=True)
class EvidenceValidation:
    ok: bool
    evidence_status: str
    issues: list[str] = field(default_factory=list)
    payload: dict[str, Any] | None = None


def file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def selected_cache_sha(filename: str) -> str | None:
    """SHA-256 of the selected cached official bytes, else provenance sidecar."""
    cache_path = CACHE_DIR / filename
    digest = file_sha256(cache_path)
    if digest:
        return digest
    sidecar = CACHE_DIR / f"{filename}.provenance.json"
    if not sidecar.is_file():
        return None
    try:
        payload = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    sha = payload.get("sha256")
    return str(sha) if isinstance(sha, str) and sha else None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _positive_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def _nonneg_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def validate_meps_derivation(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> EvidenceValidation:
    """MEPS is MODELED_FROM_MEASURED_INPUTS only when derivation matches selected PUF."""
    path = report_path or MEPS_DERIVATION_PATH
    issues: list[str] = []
    payload = _load_json(path)
    if payload is None:
        return EvidenceValidation(False, NOT_MODELED, ["MEPS_DERIVATION_UNREADABLE"])

    if payload.get("report_type") != MEPS_REPORT_TYPE:
        issues.append("MEPS_REPORT_TYPE_INVALID")
    if payload.get("source_data_year") != 2023:
        issues.append("MEPS_SOURCE_DATA_YEAR_INVALID")
    if payload.get("puf_id") not in {"HC-251", "H251"}:
        issues.append("MEPS_PUF_ID_MISMATCH")
    expected_sha = selected_sha if selected_sha is not None else selected_cache_sha(MEPS_CACHE_NAME)
    report_sha = payload.get("sha256")
    if not isinstance(report_sha, str) or not report_sha:
        issues.append("MEPS_REPORT_SHA_MISSING")
    elif not expected_sha:
        issues.append("MEPS_SELECTED_CACHE_SHA_MISSING")
    elif report_sha != expected_sha:
        issues.append("MEPS_REPORT_SHA_MISMATCH")
    for key in (
        "source_variable",
        "weight_variable",
        "age_variable",
        "insurance_variable",
        "insurance_code",
        "insurance_code_label",
        "layout",
    ):
        if payload.get(key) in (None, "", {}, []):
            issues.append(f"MEPS_METADATA_MISSING:{key}")
    if payload.get("source_variable") != "TOTSLF23":
        issues.append("MEPS_SOURCE_VARIABLE_INVALID")
    if payload.get("insurance_variable") != "INSCOV23":
        issues.append("MEPS_INSURANCE_VARIABLE_INVALID")
    if payload.get("insurance_code") != 1:
        issues.append("MEPS_INSURANCE_CODE_INVALID")
    if payload.get("insurance_code_label") != "ANY PRIVATE":
        issues.append("MEPS_INSURANCE_LABEL_INVALID")
    if payload.get("age_low") != 18 or payload.get("age_high") != 64:
        issues.append("MEPS_AGE_FILTER_INVALID")
    if not _nonneg_number(payload.get("weighted_mean")):
        issues.append("MEPS_WEIGHTED_MEAN_INVALID")
    if not _nonneg_number(payload.get("weighted_median")):
        issues.append("MEPS_WEIGHTED_MEDIAN_INVALID")
    if not _nonneg_number(payload.get("weighted_p75")):
        issues.append("MEPS_WEIGHTED_P75_INVALID")
    if payload.get("evidence_status") != MODELED:
        issues.append("MEPS_EVIDENCE_STATUS_INVALID")
    if payload.get("calculates_mslc") is True:
        issues.append("MEPS_CLAIMS_MSLC")
    ok = not issues
    return EvidenceValidation(ok, MODELED if ok else NOT_MODELED, issues, payload)


def validate_epa_cohorts(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> EvidenceValidation:
    """EPA is MODELED_FROM_MEASURED_INPUTS only when the cohort report matches OD-004."""
    path = report_path or EPA_COHORT_PATH
    issues: list[str] = []
    payload = _load_json(path)
    if payload is None:
        return EvidenceValidation(False, NOT_MODELED, ["EPA_COHORT_UNREADABLE"])

    if payload.get("report_type") != EPA_REPORT_TYPE:
        issues.append("EPA_REPORT_TYPE_INVALID")
    expected_sha = selected_sha if selected_sha is not None else selected_cache_sha(EPA_CACHE_NAME)
    report_sha = payload.get("sha256")
    if not isinstance(report_sha, str) or not report_sha:
        issues.append("EPA_REPORT_SHA_MISSING")
    elif not expected_sha:
        issues.append("EPA_SELECTED_CACHE_SHA_MISSING")
    elif report_sha != expected_sha:
        issues.append("EPA_REPORT_SHA_MISMATCH")
    if payload.get("combined_mpg_field") != CANONICAL_MPG_FIELD:
        issues.append("EPA_CANONICAL_FIELD_NOT_COMB08")
    vclass = payload.get("canonical_vclass_values") or payload.get("canonical_vclass")
    if isinstance(vclass, str):
        vclass_values = (vclass,)
    elif isinstance(vclass, (list, tuple)):
        vclass_values = tuple(str(item) for item in vclass)
    else:
        vclass_values = ()
    if tuple(vclass_values) != CANONICAL_EPA_VCLASS:
        issues.append("EPA_CANONICAL_VCLASS_NOT_EXACT_COMPACT_MIDSIZE")
    cohorts = payload.get("cohorts")
    if not isinstance(cohorts, dict):
        issues.append("EPA_COHORTS_MISSING")
        cohorts = {}
    for year, window in FROZEN_EPA_WINDOWS.items():
        rec = cohorts.get(str(year))
        if not isinstance(rec, dict):
            issues.append(f"EPA_YEAR_MISSING:{year}")
            continue
        if rec.get("model_year_low") != window[0] or rec.get("model_year_high") != window[1]:
            issues.append(f"EPA_MODEL_YEAR_WINDOW_INVALID:{year}")
        final_n = rec.get("final_cohort_row_count")
        if not isinstance(final_n, int) or final_n <= 0:
            issues.append(f"EPA_FINAL_ROWS_INVALID:{year}")
        if not _positive_number(rec.get("median_mpg")):
            issues.append(f"EPA_MEDIAN_INVALID:{year}")
        if rec.get("mean_mpg") is not None and not _positive_number(rec.get("mean_mpg")):
            issues.append(f"EPA_MEAN_INVALID:{year}")
        compact = rec.get("compact_only_median_mpg")
        midsize = rec.get("midsize_only_median_mpg")
        if compact is not None and not _positive_number(compact):
            issues.append(f"EPA_COMPACT_MEDIAN_INVALID:{year}")
        if midsize is not None and not _positive_number(midsize):
            issues.append(f"EPA_MIDSIZE_MEDIAN_INVALID:{year}")
        if rec.get("canonical_mpg_field") not in (None, CANONICAL_MPG_FIELD):
            issues.append(f"EPA_YEAR_FIELD_NOT_COMB08:{year}")
    if payload.get("calculates_mslc") is True:
        issues.append("EPA_CLAIMS_MSLC")
    ok = not issues
    return EvidenceValidation(ok, MODELED if ok else NOT_MODELED, issues, payload)


def meps_derivation_is_valid(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> bool:
    return validate_meps_derivation(report_path, selected_sha=selected_sha).ok


def epa_cohorts_are_valid(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> bool:
    return validate_epa_cohorts(report_path, selected_sha=selected_sha).ok


def meps_evidence_status(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> str:
    return validate_meps_derivation(report_path, selected_sha=selected_sha).evidence_status


def epa_evidence_status(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> str:
    return validate_epa_cohorts(report_path, selected_sha=selected_sha).evidence_status
