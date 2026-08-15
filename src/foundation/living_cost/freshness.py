"""Enforceable freshness gate for a future PRIVATE candidate MSLC calculation.

This module does not calculate or publish a Minimum Sustainable Living Cost.
It only refuses a future candidate when authorization or freshness is unmet.

Authorization is read from config/definitions.yml (one source of truth):

    living_cost.candidate_calculation_authorized
    living_cost.release_authorized

Freshness records come from source-specific discovery, not from a timestamped
hard-coded snapshot.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REQUIRED_FRESHNESS_FAMILIES: tuple[str, ...] = (
    "acs_population_weights",
    "hud_fmr",
    "usda_food",
    "cms_marketplace_sbe",
    "meps_full_year_consolidated",
    "nhts_mileage",
    "epa_vehicle",
    "eia_gasoline",
    "naic_auto_insurance",
    "bls_ce",
    "fcc_broadband",
    "mobile_price",
    "bea_rpp",
    "federal_tax_law",
    "state_tax_law",
    "local_tax_law",
    "vehicle_registration",
    "vehicle_replacement",
    "od010_price_index",
)

BLOCKING_EVIDENCE = {
    "SOURCE_GAP",
    "UNAVAILABLE",
    "INCOMPLETE_PROVENANCE",
    "FORMULA_FROZEN_INPUTS_PENDING",
    "INVENTORY_NOT_VALIDATED",
    "RETRIEVED_UNVALIDATED",
}

PASSING_EVIDENCE = {
    "VALIDATED",
    "MODELED_FROM_MEASURED_INPUTS",
}

FRESHNESS_CHECK_STATUSES = {
    "VERIFIED_CURRENT",
    "NEWER_AVAILABLE",
    "CHECK_FAILED",
    "MANUAL_VERIFICATION_REQUIRED",
    "SOURCE_GAP",
}

BLOCKING_CHECK_STATUSES = FRESHNESS_CHECK_STATUSES - {"VERIFIED_CURRENT"}

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OD010_TABLE = PROJECT_ROOT / "data" / "metadata" / "living_cost_od010_translation_table.json"


class FreshnessGateError(RuntimeError):
    """Future candidate calculation is not allowed."""


class AuthorizationConfigError(FreshnessGateError):
    """Canonical authorization record is missing or malformed."""


@dataclass(frozen=True)
class FreshnessCheck:
    source_id: str
    latest_checked_at: str
    latest_authoritative_vintage_found: str | None
    selected_vintage: str | None
    selected_artifact: str | None
    newer_data_exists: bool | None
    retrieval_validation_status: str
    reason_if_not_refreshed: str | None = None
    freshness_check_status: str = "CHECK_FAILED"
    publisher: str | None = None
    landing_url: str | None = None
    selected_artifacts: tuple[dict[str, Any], ...] = ()
    retrieved_at: str | None = None
    transformation_method: str | None = None
    input_evidence_status: str | None = None
    months_included: tuple[str, ...] | None = None
    month_count: int | None = None
    first_month: str | None = None
    last_month: str | None = None
    extra: dict[str, Any] | None = field(default=None)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if payload.get("selected_artifacts") is not None:
            payload["selected_artifacts"] = list(payload["selected_artifacts"])
        if payload.get("months_included") is not None:
            payload["months_included"] = list(payload["months_included"])
        return payload


_PLACEHOLDER_LABELS = {
    "latest retrieved bea rpp",
    "bea rpp artifact",
    "latest retrieved",
    "current artifact",
    "validated artifact",
    "usda food-plan monthly reports",
    "target-year monthly reports / ytd",
    "cms rate/plan/service-area puf zips",
}


def _is_placeholder_label(*labels: str | None) -> bool:
    tokens = {str(label).strip().lower() for label in labels if label}
    return bool(tokens & _PLACEHOLDER_LABELS)


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _living_cost_config() -> dict[str, Any]:
    from foundation.config import definitions

    try:
        data = definitions()
    except (OSError, TypeError, ValueError) as exc:
        raise AuthorizationConfigError(f"canonical authorization record unreadable: {exc}") from exc
    living = data.get("living_cost") if isinstance(data, dict) else None
    if not isinstance(living, dict):
        raise AuthorizationConfigError("definitions.yml missing living_cost mapping")
    return living


def _read_bool_flag(name: str) -> bool:
    living = _living_cost_config()
    if name not in living:
        raise AuthorizationConfigError(f"living_cost.{name} is absent")
    value = living[name]
    if not isinstance(value, bool):
        raise AuthorizationConfigError(f"living_cost.{name} must be a boolean, got {type(value)}")
    return value


def candidate_calculation_authorized() -> bool:
    """Private unpublished candidate permission from definitions.yml."""
    return _read_bool_flag("candidate_calculation_authorized")


def living_cost_release_authorized() -> bool:
    """Public headline permission from definitions.yml (release_authorized)."""
    return _read_bool_flag("release_authorized")


def is_translation_index_bound() -> bool:
    """True only when a live OD-010 translation table exists and is marked bound."""
    if not OD010_TABLE.exists():
        return False
    try:
        payload = json.loads(OD010_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    series = payload.get("series")
    return payload.get("bound") is True and bool(series)


def freshness_gate_checklist() -> dict[str, Any]:
    return {
        "required_before_candidate_calculation": list(REQUIRED_FRESHNESS_FAMILIES),
        "if_newer_authoritative_data_exist": [
            "retrieve",
            "hash",
            "validate",
            "use",
        ],
        "do_not_recalculate_historical_2024_with_2026_prices": True,
        "headline_authorized_by_this_gate": False,
        "calculates_mslc": False,
        "candidate_calculation_authorized": candidate_calculation_authorized(),
        "living_cost_release_authorized": living_cost_release_authorized(),
        "private_candidate_never_implies_publication": True,
        "authorization_source": "config/definitions.yml",
        "translation_index_bound": is_translation_index_bound(),
    }


def _has_concrete_provenance(check: FreshnessCheck) -> bool:
    if _is_placeholder_label(
        check.selected_vintage,
        check.selected_artifact,
        check.latest_authoritative_vintage_found,
    ):
        return False
    if not check.latest_checked_at:
        return False
    if not (check.publisher or check.landing_url or check.source_id):
        return False
    period = (check.selected_vintage or check.latest_authoritative_vintage_found or "").strip()
    if not period:
        return False
    artifacts = list(check.selected_artifacts)
    if artifacts:
        return any(
            (item.get("artifact_id") or item.get("filename"))
            and not _is_placeholder_label(str(item.get("artifact_id") or item.get("filename")))
            for item in artifacts
        )
    artifact = (check.selected_artifact or "").strip()
    return bool(artifact) and not _is_placeholder_label(artifact)


def assert_candidate_freshness_ready(
    checks: Iterable[FreshnessCheck] | dict[str, FreshnessCheck],
    *,
    project_cost_year: int,
    required_families: Iterable[str] = REQUIRED_FRESHNESS_FAMILIES,
    translation_index_bound: bool | None = None,
    silent_source_year_relabel: bool = False,
) -> None:
    """Refuse a future PRIVATE candidate when freshness or candidate auth is incomplete.

    Does not compute MSLC, Gap, Adequacy, rankings, or a national median.
    Authorization is read only from config/definitions.yml.
    """
    del project_cost_year
    authorized = candidate_calculation_authorized()
    if not authorized:
        raise FreshnessGateError(
            "candidate_calculation_authorized is false; private candidate refused"
        )
    if translation_index_bound is None:
        translation_index_bound = is_translation_index_bound()
    by_id: dict[str, FreshnessCheck]
    if isinstance(checks, dict):
        by_id = dict(checks)
    else:
        by_id = {item.source_id: item for item in checks}

    missing = [family for family in required_families if family not in by_id]
    if missing:
        raise FreshnessGateError(
            f"required freshness check was not performed: {', '.join(missing)}"
        )

    if silent_source_year_relabel:
        raise FreshnessGateError("source year is being silently relabeled")

    if not translation_index_bound:
        raise FreshnessGateError(
            "OD010_TRANSLATION_INDEX_NOT_BOUND: required OD-010 translation index is not bound"
        )

    for family in required_families:
        check = by_id[family]
        if not check.latest_checked_at:
            raise FreshnessGateError(f"{family}: freshness check has no latest_checked_at")
        if check.freshness_check_status in BLOCKING_CHECK_STATUSES:
            raise FreshnessGateError(
                f"{family}: freshness_check_status is {check.freshness_check_status}"
            )
        if check.newer_data_exists is True:
            raise FreshnessGateError(
                f"{family}: newer authoritative source is known but not processed"
            )
        if check.newer_data_exists is None:
            raise FreshnessGateError(
                f"{family}: currentness was not established (newer_data_exists is null)"
            )
        if check.retrieval_validation_status in BLOCKING_EVIDENCE:
            raise FreshnessGateError(
                f"{family}: required source remains {check.retrieval_validation_status}"
            )
        if check.retrieval_validation_status in PASSING_EVIDENCE and not _has_concrete_provenance(
            check
        ):
            raise FreshnessGateError(f"{family}: passing evidence state lacks concrete provenance")


def assert_public_release_authorized() -> None:
    """Public headline publication requires the separate release authorization."""
    if not living_cost_release_authorized():
        raise FreshnessGateError(
            "living_cost_release_authorized is false; public headline publication refused"
        )


def current_family_truth() -> dict[str, FreshnessCheck]:
    """Run source-specific discovery. Do not fake readiness."""
    from foundation.living_cost.freshness_discovery import discover_all_families

    return discover_all_families()


def evaluate_freshness_readiness(
    checks: dict[str, FreshnessCheck],
    *,
    translation_index_bound: bool | None = None,
    silent_source_year_relabel: bool = False,
    candidate_inputs_bound: bool = False,
) -> dict[str, Any]:
    blocking: list[str] = []
    bound = (
        is_translation_index_bound() if translation_index_bound is None else translation_index_bound
    )
    if not bound:
        blocking.append("OD010_TRANSLATION_INDEX_NOT_BOUND")
    if silent_source_year_relabel:
        blocking.append("SILENT_SOURCE_YEAR_RELABEL")
    if not candidate_inputs_bound:
        blocking.append("REQUIRED_CANDIDATE_INPUTS_NOT_BOUND")
    for family in REQUIRED_FRESHNESS_FAMILIES:
        check = checks.get(family)
        if check is None:
            blocking.append(f"{family}:CHECK_NOT_PERFORMED")
            continue
        if not check.latest_checked_at:
            blocking.append(f"{family}:MISSING_CHECKED_AT")
        if check.freshness_check_status in BLOCKING_CHECK_STATUSES:
            blocking.append(f"{family}:{check.freshness_check_status}")
        if check.newer_data_exists is True:
            blocking.append(f"{family}:NEWER_DATA_NOT_PROCESSED")
        if check.retrieval_validation_status in BLOCKING_EVIDENCE:
            blocking.append(f"{family}:{check.retrieval_validation_status}")
        if check.retrieval_validation_status in PASSING_EVIDENCE and not _has_concrete_provenance(
            check
        ):
            blocking.append(f"{family}:MISSING_CONCRETE_PROVENANCE")
    authorized = candidate_calculation_authorized()
    ready = (
        authorized
        and bound
        and not silent_source_year_relabel
        and candidate_inputs_bound
        and not blocking
    )
    empirical_families = sorted(
        {
            family
            for family, check in checks.items()
            if check.retrieval_validation_status in BLOCKING_EVIDENCE
        }
    )
    return {
        "ready_for_private_candidate": ready,
        "candidate_calculation_authorized": authorized,
        "living_cost_release_authorized": living_cost_release_authorized(),
        "translation_index_bound": bound,
        "silent_source_year_relabel": silent_source_year_relabel,
        "candidate_inputs_bound": candidate_inputs_bound,
        "blocker_count": len(blocking),
        "gate_blocker_reason_count": len(blocking),
        "empirical_blocker_family_count": len(empirical_families),
        "empirical_blocker_families": empirical_families,
        "blockers": blocking,
        "headline_calculated": False,
        "authorization_source": "config/definitions.yml",
    }


def write_candidate_freshness_report(metadata_dir: Path) -> dict[str, Any]:
    """Write a truthful fail-closed freshness artifact from real discovery."""
    checks = current_family_truth()
    readiness = evaluate_freshness_readiness(checks)
    automated = []
    manual = []
    failed = []
    gaps = []
    for family, check in checks.items():
        if check.freshness_check_status == "VERIFIED_CURRENT":
            automated.append(family)
        elif check.freshness_check_status == "MANUAL_VERIFICATION_REQUIRED":
            manual.append(family)
        elif check.freshness_check_status == "CHECK_FAILED":
            failed.append(family)
        elif check.freshness_check_status == "SOURCE_GAP":
            gaps.append(family)
        else:
            automated.append(family)
    payload = {
        "report_type": "living_cost_candidate_freshness",
        "generated_at": _now_iso(),
        "schema_version": "2.0",
        "calculates_mslc": False,
        "required_families": list(REQUIRED_FRESHNESS_FAMILIES),
        "checks": {key: check.to_dict() for key, check in checks.items()},
        **readiness,
        "discovery": {
            "automated_or_verified": automated,
            "manual_verification_required": manual,
            "check_failed": failed,
            "source_gap": gaps,
            "timestamps_from_hardcoded_snapshot": False,
        },
        "status_by_family": {
            family: check.freshness_check_status for family, check in checks.items()
        },
        "notes": {
            "health_oop": (
                "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
                "Do not claim healthcare OOP ready merely because HC-251 was downloaded."
            ),
            "mpg": (
                "EPA MPG evidence is RETRIEVED_UNVALIDATED. "
                "OD-004 methodology FROZEN is not VALIDATED evidence."
            ),
            "vehicle_replacement": (
                "Formula frozen. Acquisition, residual, and usable years pending."
            ),
        },
    }
    metadata_dir.mkdir(parents=True, exist_ok=True)
    dest = metadata_dir / "living_cost_candidate_freshness.json"
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def freshness_status_summary(payload: dict[str, Any]) -> str:
    """Build status text from the actual freshness artifact. Do not invent statuses."""
    checks = payload.get("checks") or {}
    lines = [
        f"ready_for_private_candidate={payload.get('ready_for_private_candidate')}",
        f"empirical_blocker_family_count={payload.get('empirical_blocker_family_count')}",
        f"gate_blocker_reason_count={payload.get('gate_blocker_reason_count', payload.get('blocker_count'))}",
    ]
    for family in REQUIRED_FRESHNESS_FAMILIES:
        check = checks.get(family) or {}
        status = check.get("freshness_check_status", "CHECK_NOT_PERFORMED")
        lines.append(f"{family}: {status}")
    return "\n".join(lines)


BLOCKER_NOTES: dict[str, str] = {
    "health_oop": (
        "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
        "Tasks still required: use newest officially released Full Year Consolidated PUF; "
        "validate fixed-width/codebook parsing; enforce approved age/private-insurance "
        "filter; apply correct survey weights; derive weighted-mean canonical OOP; "
        "retain median/P75 sensitivity; produce source hash/provenance; bind OD-010 "
        "medical price translation for lagged years. Do not claim healthcare OOP ready "
        "merely because HC-251 was downloaded."
    ),
    "mpg": (
        "EPA MPG: RETRIEVED_UNVALIDATED. OD-004 methodology is FROZEN; evidence is not "
        "VALIDATED. Before candidate readiness validate gasoline non-BEV/non-PHEV "
        "compact+midsize 8-12 model-year window median combined MPG from official EPA/"
        "DOE rows. Record artifact, vintage, cohort model-year range, row count, filter "
        "criteria, median MPG, sensitivities, hash/provenance."
    ),
}


def stamp_source_coverage_from_current_truth(coverage_path: Path) -> dict[str, Any]:
    """Regenerate control metadata on the existing honest coverage file.

    Does not change evidence statuses to look better.
    """
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    coverage["generated_at"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    coverage["candidate_calculation_authorized"] = candidate_calculation_authorized()
    coverage["living_cost_release_authorized"] = living_cost_release_authorized()
    coverage["states_modeled"] = 0
    coverage["headline_calculated"] = False
    coverage["gap_calculated"] = False
    coverage["adequacy_calculated"] = False
    coverage["blocker_notes"] = dict(BLOCKER_NOTES)
    required_blockers = {
        "health_oop": "RETRIEVED_UNVALIDATED",
        "mpg": "RETRIEVED_UNVALIDATED",
        "maintenance": "INCOMPLETE_PROVENANCE",
        "essentials": "INCOMPLETE_PROVENANCE",
        "recreation": "INCOMPLETE_PROVENANCE",
        "insurance": "RETRIEVED_UNVALIDATED",
        "registration": "SOURCE_GAP",
        "replacement": "FORMULA_FROZEN_INPUTS_PENDING",
        "connectivity": "SOURCE_GAP",
        "federal_tax": "INVENTORY_NOT_VALIDATED",
        "state_tax": "SOURCE_GAP",
        "local_tax": "SOURCE_GAP",
    }
    for year, comps in coverage.get("coverage_by_year", {}).items():
        for name, expected in required_blockers.items():
            actual = comps.get(name)
            if actual != expected:
                raise ValueError(
                    f"coverage {year}.{name} is {actual!r}, expected {expected!r}; "
                    "do not alter evidence statuses to look better"
                )
    coverage_path.write_text(json.dumps(coverage, indent=2), encoding="utf-8")
    return coverage
