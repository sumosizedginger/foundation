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


NAIC_CACHE_NAME = "publication-aut-pb-auto-insurance-database.pdf"
NAIC_DERIVATION_PATH = METADATA_DIR / "living_cost_naic_auto_insurance.json"
NAIC_REPORT_TYPE = "living_cost_naic_auto_insurance"
NAIC_VALIDATED = "VALIDATED"
NAIC_NOT_VALIDATED = "RETRIEVED_UNVALIDATED"
FEDERAL_TAX_INVENTORY_PATH = METADATA_DIR / "living_cost_federal_tax_inventory.json"
FEDERAL_TAX_REPORT_TYPE = "living_cost_federal_tax_inventory"
FEDERAL_TAX_VALIDATED = "VALIDATED"
FEDERAL_TAX_NOT_VALIDATED = "INVENTORY_NOT_VALIDATED"


def validate_naic_derivation(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> EvidenceValidation:
    """NAIC is VALIDATED only when Table 5 binds to selected PDF bytes."""
    from foundation.sources.naic_report import US_STATE_NAMES

    path = report_path or NAIC_DERIVATION_PATH
    issues: list[str] = []
    payload = _load_json(path)
    if payload is None:
        return EvidenceValidation(False, NAIC_NOT_VALIDATED, ["NAIC_DERIVATION_UNREADABLE"])
    if payload.get("report_type") != NAIC_REPORT_TYPE:
        issues.append("NAIC_REPORT_TYPE_INVALID")
    if payload.get("canonical_measure") != "combined_average_premium":
        issues.append("NAIC_CANONICAL_MEASURE_INVALID")
    if payload.get("calculates_mslc") is True:
        issues.append("NAIC_CLAIMS_MSLC")
    expected_sha = selected_sha if selected_sha is not None else selected_cache_sha(NAIC_CACHE_NAME)
    report_sha = payload.get("sha256")
    if not isinstance(report_sha, str) or not report_sha:
        issues.append("NAIC_REPORT_SHA_MISSING")
    elif not expected_sha:
        issues.append("NAIC_SELECTED_PDF_SHA_MISSING")
    elif report_sha != expected_sha:
        issues.append("NAIC_REPORT_SHA_MISMATCH")
    if payload.get("pdf_identifier_bound") is not True:
        issues.append("NAIC_PDF_NOT_IDENTIFIER_BOUND")
    ident = payload.get("publication_identifier")
    listing = payload.get("listing_identifier")
    if not ident or ident != listing:
        issues.append("NAIC_LISTING_IDENTIFIER_MISMATCH")
    if payload.get("source_data_year") != (payload.get("data_year_range") or {}).get("end"):
        issues.append("NAIC_SOURCE_DATA_YEAR_INVALID")
    rows = payload.get("jurisdictions")
    if not isinstance(rows, list) or not rows:
        issues.append("NAIC_JURISDICTIONS_MISSING")
        rows = []
    states: list[str] = []
    for rec in rows:
        if not isinstance(rec, dict):
            issues.append("NAIC_ROW_INVALID")
            continue
        st = rec.get("state")
        if not isinstance(st, str):
            issues.append("NAIC_STATE_INVALID")
            continue
        states.append(st)
        prem = rec.get("combined_average_premium")
        if not _positive_number(prem):
            issues.append(f"NAIC_PREMIUM_INVALID:{st}")
        if rec.get("source_artifact_sha256") != report_sha:
            issues.append(f"NAIC_ROW_SHA_MISMATCH:{st}")
    if len(states) != len(set(states)):
        issues.append("NAIC_DUPLICATE_STATES")
    if set(states) != set(US_STATE_NAMES.values()):
        issues.append("NAIC_STATE_SET_INCOMPLETE")
    national = payload.get("national")
    if not isinstance(national, dict) or not _positive_number(
        national.get("combined_average_premium")
    ):
        issues.append("NAIC_NATIONAL_ROW_MISSING")
    elif national.get("not_state_average") is not True:
        issues.append("NAIC_NATIONAL_NOT_MARKED_SEPARATE")
    release = payload.get("official_release_national_combined_average_premium")
    if isinstance(national, dict) and isinstance(release, (int, float)):
        pdf_nat = national.get("combined_average_premium")
        if _positive_number(pdf_nat) and abs(round(float(pdf_nat)) - round(float(release))) > 1:
            issues.append("NAIC_NATIONAL_RELEASE_MISMATCH")
    if payload.get("validation_ok") is not True:
        issues.append("NAIC_VALIDATION_FLAG_FALSE")
    ok = not issues
    return EvidenceValidation(ok, NAIC_VALIDATED if ok else NAIC_NOT_VALIDATED, issues, payload)


def _brackets_match(code_brackets: list[Any], inventory_brackets: list[Any]) -> bool:
    if len(code_brackets) != len(inventory_brackets):
        return False
    for code, inv in zip(code_brackets, inventory_brackets, strict=True):
        code_upper, code_rate = code
        inv_upper = inv.get("upper")
        inv_rate = inv.get("rate")
        if abs(float(code_rate) - float(inv_rate)) > 1e-12:
            return False
        if code_upper == float("inf"):
            if inv_upper is not None:
                return False
        elif inv_upper is None or abs(float(code_upper) - float(inv_upper)) > 0.01:
            return False
    return True


def _federal_artifact_index(artifacts: Any) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    if not isinstance(artifacts, list):
        return index
    for item in artifacts:
        if isinstance(item, dict) and isinstance(item.get("key"), str):
            index[item["key"]] = item
    return index


def _resolve_field_authority(
    *,
    year: int,
    field: str,
    rec: dict[str, Any] | None,
    artifacts: dict[str, dict[str, Any]],
    allowed_keys: set[str],
) -> list[str]:
    from foundation.sources.federal_tax import official_authority_url

    if not isinstance(rec, dict):
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    key = rec.get("source_artifact_key")
    sha = rec.get("source_sha256")
    if not key or key not in artifacts:
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    art = artifacts[key]
    if key not in allowed_keys:
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    if art.get("http_ok") is not True or not art.get("sha256"):
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    if sha != art.get("sha256"):
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    if not official_authority_url(art.get("url")):
        return [f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:{field}"]
    return []


def validate_federal_tax_inventory(
    report_path: Path | None = None,
) -> EvidenceValidation:
    """Federal tax is VALIDATED only when each field binds a year-specific IRS artifact."""
    from foundation.living_cost.taxes import FEDERAL_TAX_RULES
    from foundation.sources.federal_tax import (
        INCOME_TAX_ARTIFACT_BY_YEAR,
        PAYROLL_ARTIFACT_BY_YEAR,
    )

    path = report_path or FEDERAL_TAX_INVENTORY_PATH
    issues: list[str] = []
    payload = _load_json(path)
    if payload is None:
        return EvidenceValidation(
            False, FEDERAL_TAX_NOT_VALIDATED, ["FEDERAL_TAX_INVENTORY_UNREADABLE"]
        )
    if payload.get("report_type") != FEDERAL_TAX_REPORT_TYPE:
        issues.append("FEDERAL_TAX_REPORT_TYPE_INVALID")
    if payload.get("calculates_mslc") is True:
        issues.append("FEDERAL_TAX_CLAIMS_MSLC")
    years = payload.get("years")
    if not isinstance(years, dict):
        return EvidenceValidation(
            False, FEDERAL_TAX_NOT_VALIDATED, issues + ["FEDERAL_TAX_YEARS_MISSING"], payload
        )
    artifacts = _federal_artifact_index(payload.get("retrieved_artifacts"))
    for year in (2024, 2026):
        rec = years.get(str(year))
        if not isinstance(rec, dict):
            issues.append(f"FEDERAL_TAX_YEAR_MISSING:{year}")
            continue
        if rec.get("parsed_ok") is not True or rec.get("issues"):
            issues.append(f"FEDERAL_TAX_YEAR_UNPARSED:{year}:{rec.get('issues')}")
        if year not in FEDERAL_TAX_RULES:
            issues.append(f"FEDERAL_TAX_CODE_YEAR_MISSING:{year}")
            continue
        income_keys = {INCOME_TAX_ARTIFACT_BY_YEAR[year]}
        payroll_keys = {PAYROLL_ARTIFACT_BY_YEAR[year]}
        rules = FEDERAL_TAX_RULES[year]
        std = rec.get("standard_deduction") or {}
        issues.extend(
            _resolve_field_authority(
                year=year,
                field="standard_deduction",
                rec=std if isinstance(std, dict) else None,
                artifacts=artifacts,
                allowed_keys=income_keys,
            )
        )
        if (
            not isinstance(std, dict)
            or std.get("value") is None
            or abs(float(rules["standard_deduction"]) - float(std["value"])) > 0.01
        ):
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:standard_deduction")
        oasdi = rec.get("oasdi") or {}
        issues.extend(
            _resolve_field_authority(
                year=year,
                field="oasdi",
                rec=oasdi if isinstance(oasdi, dict) else None,
                artifacts=artifacts,
                allowed_keys=payroll_keys,
            )
        )
        if (
            not isinstance(oasdi, dict)
            or oasdi.get("employee_rate") is None
            or abs(float(rules["ss_tax_rate"]) - float(oasdi["employee_rate"])) > 1e-12
        ):
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:oasdi_rate")
        if (
            not isinstance(oasdi, dict)
            or oasdi.get("taxable_maximum") is None
            or abs(float(rules["ss_wage_cap"]) - float(oasdi["taxable_maximum"])) > 0.01
        ):
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:oasdi_cap")
        hi = rec.get("medicare_hi") or {}
        issues.extend(
            _resolve_field_authority(
                year=year,
                field="medicare_hi",
                rec=hi if isinstance(hi, dict) else None,
                artifacts=artifacts,
                allowed_keys=payroll_keys,
            )
        )
        if (
            not isinstance(hi, dict)
            or hi.get("employee_rate") is None
            or abs(float(rules["medicare_rate"]) - float(hi["employee_rate"])) > 1e-12
        ):
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:medicare_rate")
        if not isinstance(hi, dict) or hi.get("no_limit") is not True:
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:medicare_cap")
        addl = rec.get("additional_medicare_tax") or {}
        issues.extend(
            _resolve_field_authority(
                year=year,
                field="additional_medicare_tax",
                rec=addl if isinstance(addl, dict) else None,
                artifacts=artifacts,
                allowed_keys=payroll_keys,
            )
        )
        if not isinstance(addl, dict) or addl.get("applicable") is not True:
            issues.append(
                f"FEDERAL_TAX_MODEL_GAP:{year}:additional_medicare_missing_from_inventory"
            )
        else:
            code_rate = rules.get("additional_medicare_rate")
            code_thr = rules.get("additional_medicare_threshold")
            if code_rate is None or code_thr is None:
                issues.append(
                    f"FEDERAL_TAX_MODEL_GAP:{year}:additional_medicare "
                    f"threshold={addl.get('threshold')} rate={addl.get('rate')} "
                    "existing=omitted required=IRC_3101(b)(2)"
                )
            else:
                if abs(float(code_rate) - float(addl.get("rate") or 0)) > 1e-12:
                    issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:additional_medicare_rate")
                if abs(float(code_thr) - float(addl.get("threshold") or 0)) > 0.01:
                    issues.append(
                        f"FEDERAL_TAX_RULES_MISMATCH:{year}:additional_medicare_threshold"
                    )
        inv_br = rec.get("income_tax_brackets") or []
        if not _brackets_match(list(rules["brackets"]), inv_br):
            issues.append(f"FEDERAL_TAX_RULES_MISMATCH:{year}:brackets")
        if isinstance(inv_br, list):
            for idx, bracket in enumerate(inv_br):
                if not isinstance(bracket, dict):
                    issues.append(f"FEDERAL_TAX_FIELD_AUTHORITY_UNBOUND:{year}:brackets")
                    break
                issues.extend(
                    _resolve_field_authority(
                        year=year,
                        field=f"brackets:{idx}",
                        rec=bracket,
                        artifacts=artifacts,
                        allowed_keys=income_keys,
                    )
                )
    if 2025 in FEDERAL_TAX_RULES:
        issues.append("FEDERAL_TAX_UNSUPPORTED_YEAR_PRESENT:2025")
    ok = not issues
    return EvidenceValidation(
        ok, FEDERAL_TAX_VALIDATED if ok else FEDERAL_TAX_NOT_VALIDATED, issues, payload
    )


def naic_derivation_is_valid(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> bool:
    return validate_naic_derivation(report_path, selected_sha=selected_sha).ok


def naic_evidence_status(
    report_path: Path | None = None,
    *,
    selected_sha: str | None = None,
) -> str:
    return validate_naic_derivation(report_path, selected_sha=selected_sha).evidence_status


def federal_tax_inventory_is_valid(report_path: Path | None = None) -> bool:
    return validate_federal_tax_inventory(report_path).ok


def federal_tax_evidence_status(report_path: Path | None = None) -> str:
    return validate_federal_tax_inventory(report_path).evidence_status
