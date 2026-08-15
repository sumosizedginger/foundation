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

import hashlib
import json
from collections.abc import Iterable, Mapping
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

MUTABLE_SOURCE_FAMILIES: frozenset[str] = frozenset(
    {
        "usda_food",
        "eia_gasoline",
        "epa_vehicle",
        "bea_rpp",
        "cms_marketplace_sbe",
        "naic_auto_insurance",
    }
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
OD010_TABLE = PROJECT_ROOT / "data" / "metadata" / "living_cost_od010_translation_table.json"
CANDIDATE_INPUT_BINDINGS = (
    PROJECT_ROOT / "data" / "metadata" / "living_cost_candidate_input_bindings.json"
)


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
    listing_freshness_status: str | None = None
    artifact_currentness_status: str | None = None
    selected_artifact_matches_latest: bool | None = None
    year_coverage: dict[str, Any] | None = None
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
    """True only when required CPI_UPDATED component/year records are complete.

    A manually written {"bound": true, "series": {"foo": "..."}} does not bind.
    """
    from foundation.living_cost.candidate_bindings import od010_translation_is_bound

    return od010_translation_is_bound(OD010_TABLE)


def required_project_cost_years() -> tuple[int, ...]:
    """Canonical candidate target-year bundle from definitions.yml."""
    living = _living_cost_config()
    if "required_project_cost_years" not in living:
        raise AuthorizationConfigError("living_cost.required_project_cost_years is absent")
    raw = living["required_project_cost_years"]
    if not isinstance(raw, list) or not raw:
        raise AuthorizationConfigError(
            "living_cost.required_project_cost_years must be a non-empty list"
        )
    years: list[int] = []
    for item in raw:
        if not isinstance(item, int) or isinstance(item, bool):
            raise AuthorizationConfigError(
                f"living_cost.required_project_cost_years entries must be ints, got {type(item)}"
            )
        years.append(item)
    return tuple(years)


def are_candidate_inputs_bound() -> bool:
    """True only when every required component/year has a complete binding.

    The candidate assembler is not built. Absence of the binding record is
    false. A non-empty file or a manually asserted bound=true is not enough.
    """
    from foundation.living_cost.candidate_bindings import candidate_inputs_are_bound

    return candidate_inputs_are_bound(CANDIDATE_INPUT_BINDINGS)


def detect_silent_source_year_relabel(
    checks: dict[str, FreshnessCheck],
) -> bool:
    """Derive silent year-relabel from candidate input metadata, not a caller bool."""
    for check in checks.values():
        extra = check.extra or {}
        if extra.get("substituted_2024_for_2026") is True:
            return True
        if extra.get("silent_source_year_relabel") is True:
            return True
        coverage = check.year_coverage or extra.get("year_coverage") or {}
        if not isinstance(coverage, dict):
            continue
        for rec in coverage.values():
            if isinstance(rec, dict) and rec.get("silent_relabel") is True:
                return True
    return False


def _year_coverage_map(check: FreshnessCheck) -> dict[Any, Any]:
    if isinstance(check.year_coverage, dict):
        return check.year_coverage
    extra = check.extra or {}
    coverage = extra.get("year_coverage")
    return coverage if isinstance(coverage, dict) else {}


def missing_project_cost_years(
    check: FreshnessCheck,
    years: Iterable[int],
) -> list[int]:
    """A year is covered only when its record explicitly says covered: true."""
    coverage = _year_coverage_map(check)
    missing: list[int] = []
    for year in years:
        rec = coverage.get(year)
        if rec is None:
            rec = coverage.get(str(year))
        if not isinstance(rec, dict) or rec.get("covered") is not True:
            missing.append(int(year))
    return missing


def _unique_reasons(reasons: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        if reason in seen:
            continue
        seen.add(reason)
        out.append(reason)
    return out


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
        "candidate_inputs_bound": are_candidate_inputs_bound(),
        "required_project_cost_years": list(required_project_cost_years()),
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


def _as_check_map(
    checks: Iterable[FreshnessCheck] | Mapping[str, FreshnessCheck],
) -> dict[str, FreshnessCheck]:
    if isinstance(checks, Mapping):
        return dict(checks)
    return {item.source_id: item for item in checks}


def _mutable_currentness_inconsistent(check: FreshnessCheck) -> bool:
    if check.freshness_check_status != "VERIFIED_CURRENT":
        return False
    return not (
        check.listing_freshness_status == "VERIFIED_CURRENT"
        and check.artifact_currentness_status == "VERIFIED_CURRENT"
        and check.selected_artifact_matches_latest is True
    )


def _validate_candidate_checks(
    checks: Iterable[FreshnessCheck] | Mapping[str, FreshnessCheck],
) -> None:
    """PURE INTERNAL validator. Tests may pass synthetic checks here.

    Public candidate authorization must not call this with caller-supplied
    checks. The public boundary always runs live discovery first.
    """
    translation_index_bound = is_translation_index_bound()
    candidate_inputs_bound = are_candidate_inputs_bound()
    target_years = required_project_cost_years()
    by_id = _as_check_map(checks)

    missing = [family for family in REQUIRED_FRESHNESS_FAMILIES if family not in by_id]
    if missing:
        raise FreshnessGateError(
            f"required freshness check was not performed: {', '.join(missing)}"
        )

    if detect_silent_source_year_relabel(by_id):
        raise FreshnessGateError("source year is being silently relabeled")

    if not translation_index_bound:
        raise FreshnessGateError(
            "OD010_TRANSLATION_INDEX_NOT_BOUND: required OD-010 translation index is not bound"
        )
    if not candidate_inputs_bound:
        raise FreshnessGateError(
            "REQUIRED_CANDIDATE_INPUTS_NOT_BOUND: required candidate inputs are not bound"
        )

    for family in REQUIRED_FRESHNESS_FAMILIES:
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
        if family in MUTABLE_SOURCE_FAMILIES and _mutable_currentness_inconsistent(check):
            raise FreshnessGateError(
                f"{family}: VERIFIED_CURRENT requires listing and artifact "
                "currentness VERIFIED_CURRENT and selected_artifact_matches_latest=true"
            )
        missing_years = missing_project_cost_years(check, target_years)
        if missing_years:
            raise FreshnessGateError(
                f"{family}: required project cost year(s) not covered: {missing_years}"
            )


def compute_freshness_run_id(core: Mapping[str, Any]) -> str:
    """SHA-256 of the canonical readiness-core JSON."""
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_check_identity(checks: Mapping[str, Any]) -> dict[str, Any]:
    identity: dict[str, Any] = {}
    for family, check in checks.items():
        artifacts = check.get("selected_artifacts") or []
        hashes = []
        for item in artifacts:
            if isinstance(item, dict):
                hashes.append(
                    {
                        "artifact_id": item.get("artifact_id") or item.get("filename"),
                        "sha256": item.get("sha256"),
                    }
                )
        identity[family] = {
            "selected_artifact": check.get("selected_artifact"),
            "selected_vintage": check.get("selected_vintage"),
            "latest_authoritative_vintage_found": check.get("latest_authoritative_vintage_found"),
            "freshness_check_status": check.get("freshness_check_status"),
            "artifact_hashes": hashes,
            "year_coverage": check.get("year_coverage"),
        }
    return identity


def build_readiness_snapshot(checks: Mapping[str, FreshnessCheck]) -> dict[str, Any]:
    """Immutable-style readiness snapshot for a future candidate assembler."""
    from foundation.living_cost.candidate_bindings import (
        candidate_input_binding_identity,
        translation_binding_identity,
    )

    generated_at = _now_iso()
    target_years = list(required_project_cost_years())
    od010_identity = translation_binding_identity()
    input_identity = candidate_input_binding_identity()
    checks_dict = {key: check.to_dict() for key, check in checks.items()}
    core = {
        "generated_at": generated_at,
        "required_project_cost_years": target_years,
        "checks": _canonical_check_identity(checks_dict),
        "od010_binding_identity": od010_identity,
        "candidate_input_binding_identity": input_identity,
    }
    readiness = evaluate_freshness_readiness(checks)
    snapshot = {
        "freshness_run_id": compute_freshness_run_id(core),
        "generated_at": generated_at,
        "required_project_cost_years": target_years,
        "checks": checks_dict,
        "od010_binding_identity": od010_identity,
        "candidate_input_binding_identity": input_identity,
        **readiness,
        "calculates_mslc": False,
    }
    return json.loads(json.dumps(snapshot, default=str))


def run_candidate_readiness_gate() -> dict[str, Any]:
    """PUBLIC production boundary. Runs live discovery. No caller-supplied checks.

    A future candidate assembler must consume this returned snapshot. It must
    not discard the live result and later load an older committed JSON file.
    Does not calculate an MSLC.
    """
    if not candidate_calculation_authorized():
        raise FreshnessGateError(
            "candidate_calculation_authorized is false; private candidate refused"
        )
    try:
        checks = current_family_truth()
    except FreshnessGateError:
        raise
    except Exception as exc:
        raise FreshnessGateError(
            f"live discovery failed; private candidate refused: {exc}"
        ) from exc
    snapshot = build_readiness_snapshot(checks)
    _validate_candidate_checks(checks)
    return snapshot


def assert_candidate_freshness_ready() -> dict[str, Any]:
    """PUBLIC production gate. No externally supplied checks.

    Internally executes current_family_truth() immediately before readiness
    is assessed. Tests must use _validate_candidate_checks for synthetic
    objects and must monkeypatch the discovery provider, not inject checks.
    """
    return run_candidate_readiness_gate()


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
) -> dict[str, Any]:
    """Score readiness from canonical project state. No public override parameters."""
    blocking: list[str] = []
    bound = is_translation_index_bound()
    candidate_inputs_bound = are_candidate_inputs_bound()
    silent_source_year_relabel = detect_silent_source_year_relabel(checks)
    target_years = required_project_cost_years()
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
        if (
            check.newer_data_exists is None
            and check.freshness_check_status not in BLOCKING_CHECK_STATUSES
        ):
            blocking.append(f"{family}:CURRENTNESS_NOT_ESTABLISHED")
        if check.retrieval_validation_status in BLOCKING_EVIDENCE:
            blocking.append(f"{family}:{check.retrieval_validation_status}")
        if check.retrieval_validation_status in PASSING_EVIDENCE and not _has_concrete_provenance(
            check
        ):
            blocking.append(f"{family}:MISSING_CONCRETE_PROVENANCE")
        if family in MUTABLE_SOURCE_FAMILIES and _mutable_currentness_inconsistent(check):
            blocking.append(f"{family}:MUTABLE_CURRENTNESS_INCONSISTENT")
        missing_years = missing_project_cost_years(check, target_years)
        coverage = _year_coverage_map(check)
        if not coverage:
            for year in target_years:
                blocking.append(f"{family}:MISSING_YEAR_{year}")
        elif missing_years and check.retrieval_validation_status not in {
            "SOURCE_GAP",
            "UNAVAILABLE",
            "FORMULA_FROZEN_INPUTS_PENDING",
        }:
            for year in missing_years:
                blocking.append(f"{family}:MISSING_YEAR_{year}")
    blocking = _unique_reasons(blocking)
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
        "required_project_cost_years": list(target_years),
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
    snapshot = build_readiness_snapshot(checks)
    payload = {
        "report_type": "living_cost_candidate_freshness",
        "generated_at": snapshot["generated_at"],
        "schema_version": "2.2",
        "calculates_mslc": False,
        "freshness_run_id": snapshot["freshness_run_id"],
        "required_families": list(REQUIRED_FRESHNESS_FAMILIES),
        "checks": snapshot["checks"],
        "od010_binding_identity": snapshot["od010_binding_identity"],
        "candidate_input_binding_identity": snapshot["candidate_input_binding_identity"],
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
    return json.loads(dest.read_text(encoding="utf-8"))


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
