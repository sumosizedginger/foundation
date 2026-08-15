"""Structural validators for candidate-input and OD-010 translation bindings.

bound=true is DERIVED from complete valid records. A manually asserted
top-level boolean is never trusted. Generated coverage cannot shrink the
required component universe or drop frozen CPI_UPDATED pairs.

This module does not calculate an MSLC and does not create fake bindings.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# CPI_UPDATED factor is always target/base. Do not silently change this
# arithmetic; a different transformation needs a new frozen method.
CPI_UPDATED_FACTOR_OPERATION = "target_index_value / base_index_value"
# Index observations: exact after Decimal(str(value)) normalize.
# Factors: same exact compare, then a documented 1e-12 relative fallback
# for stored-precision rounding only.
INDEX_COMPARE_POLICY = "exact Decimal(str) normalize"
FACTOR_ABS_TOLERANCE = Decimal("1e-12")
FACTOR_REL_TOLERANCE = Decimal("1e-12")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
OD010_TABLE = METADATA_DIR / "living_cost_od010_translation_table.json"
CANDIDATE_INPUT_BINDINGS = METADATA_DIR / "living_cost_candidate_input_bindings.json"
SOURCE_COVERAGE = METADATA_DIR / "living_cost_source_coverage.json"

REQUIRED_CANDIDATE_COMPONENTS: tuple[str, ...] = (
    "housing",
    "population_weights",
    "food",
    "health_premium",
    "health_oop",
    "mileage",
    "mpg",
    "gas",
    "insurance",
    "maintenance",
    "registration",
    "replacement",
    "connectivity",
    "essentials",
    "recreation",
    "rpp",
    "federal_tax",
    "state_tax",
    "local_tax",
)

CONNECTIVITY_SUBCOMPONENTS: tuple[str, ...] = ("broadband", "mobile")

PASSING_BINDING_EVIDENCE = frozenset({"VALIDATED", "MODELED_FROM_MEASURED_INPUTS"})

BLOCKING_BINDING_EVIDENCE = frozenset(
    {
        "SOURCE_GAP",
        "UNAVAILABLE",
        "INCOMPLETE_PROVENANCE",
        "FORMULA_FROZEN_INPUTS_PENDING",
        "INVENTORY_NOT_VALIDATED",
        "RETRIEVED_UNVALIDATED",
    }
)

# Frozen OD-010 / source-lag policy. Generated coverage must match this.
# Year-specific dicts are keyed by project cost year.
FROZEN_TRANSLATION_POLICY: dict[str, str | dict[int, str]] = {
    "housing": "NONE",
    "population_weights": "LATEST_AVAILABLE",
    "food": {2024: "NONE", 2026: "YTD"},
    "health_premium": "NONE",
    "health_oop": "CPI_UPDATED",
    "mileage": "LATEST_AVAILABLE",
    "mpg": "LATEST_AVAILABLE",
    "gas": "NONE",
    "insurance": "CPI_UPDATED",
    "maintenance": {2024: "NONE", 2026: "CPI_UPDATED"},
    "registration": "RULE_YEAR",
    "replacement": "MODEL_SUBINPUT",
    "connectivity": "SOURCE_CLASSIFIED",
    "essentials": {2024: "NONE", 2026: "CPI_UPDATED"},
    "recreation": {2024: "NONE", 2026: "CPI_UPDATED"},
    "rpp": "LATEST_AVAILABLE",
    "federal_tax": "RULE_YEAR",
    "state_tax": "RULE_YEAR",
    "local_tax": "RULE_YEAR",
}

# Evidence status is separate. Registration/local-tax remain SOURCE_GAP.
REPLACEMENT_SUBINPUT_POLICY: dict[str, str] = {
    "formula": "(acquisition - residual) / usable remaining years",
    "acquisition": "LATEST_AVAILABLE",
    "residual": "LATEST_AVAILABLE",
    "usable_years": "LATEST_AVAILABLE",
    "evidence_status": "FORMULA_FROZEN_INPUTS_PENDING",
}

CONNECTIVITY_SOURCE_CLASS_METHODS: dict[str, str] = {
    "high_frequency": "YTD",
    "point_in_time": "NONE",
}

FROZEN_CPI_UPDATED_PAIRS: tuple[tuple[str, int], ...] = (
    ("health_oop", 2024),
    ("health_oop", 2026),
    ("insurance", 2024),
    ("insurance", 2026),
    ("maintenance", 2026),
    ("essentials", 2026),
    ("recreation", 2026),
)

# Deterministic component -> live freshness family mapping.
# Binding source_id must equal the family or "{family}_{project_cost_year}".
COMPONENT_FRESHNESS_FAMILY: dict[str, str] = {
    "housing": "hud_fmr",
    "population_weights": "acs_population_weights",
    "food": "usda_food",
    "health_premium": "cms_marketplace_sbe",
    "health_oop": "meps_full_year_consolidated",
    "mileage": "nhts_mileage",
    "mpg": "epa_vehicle",
    "gas": "eia_gasoline",
    "insurance": "naic_auto_insurance",
    "maintenance": "bls_ce",
    "registration": "vehicle_registration",
    "replacement": "vehicle_replacement",
    "connectivity": "fcc_broadband",
    "broadband": "fcc_broadband",
    "mobile": "mobile_price",
    "essentials": "bls_ce",
    "recreation": "bls_ce",
    "rpp": "bea_rpp",
    "federal_tax": "federal_tax_law",
    "state_tax": "state_tax_law",
    "local_tax": "local_tax_law",
}

REQUIRED_BINDING_FIELDS: tuple[str, ...] = (
    "component",
    "project_cost_year",
    "source_id",
    "source_data_year",
    "selected_artifacts",
    "model_method",
    "evidence_status",
    "translation_method",
)

REQUIRED_TRANSLATION_FIELDS: tuple[str, ...] = (
    "component",
    "source_data_year",
    "project_cost_year",
    "official_series_identifier",
    "publisher",
    "observation_period",
    "source_artifact",
    "retrieval_validation_state",
)


class CoverageAuthorityError(ValueError):
    """Generated coverage tried to redefine the required component universe."""


class SourceLagAuthorityError(ValueError):
    """Generated source_lag tried to weaken frozen OD-010 translation policy."""


def load_source_lag() -> dict[str, Any]:
    """Generated source-lag metadata. Never the authority for required pairs."""
    if not SOURCE_COVERAGE.exists():
        return {}
    try:
        payload = json.loads(SOURCE_COVERAGE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    lag = payload.get("source_lag")
    return lag if isinstance(lag, dict) else {}


def required_candidate_components() -> tuple[str, ...]:
    """Frozen methodology authority. Generated coverage cannot shrink this."""
    return REQUIRED_CANDIDATE_COMPONENTS


def expected_translation_method(component: str, year: int) -> str:
    """Frozen OD-010 expected translation method for a component/year."""
    policy = FROZEN_TRANSLATION_POLICY.get(component)
    if policy is None:
        raise SourceLagAuthorityError(f"no frozen translation policy for {component}")
    if isinstance(policy, dict):
        if year not in policy:
            raise SourceLagAuthorityError(f"no frozen translation policy for {component}:{year}")
        return policy[year]
    return policy


def od010_record_hash(record: dict[str, Any]) -> str:
    """Canonical SHA-256 of the authorizing OD-010 translation record."""
    core = {
        "component": record.get("component"),
        "source_data_year": record.get("source_data_year"),
        "project_cost_year": record.get("project_cost_year"),
        "official_series_identifier": record.get("official_series_identifier")
        or record.get("series_id")
        or record.get("official_series"),
        "publisher": record.get("publisher"),
        "observation_period": record.get("observation_period") or record.get("period"),
        "source_artifact": record.get("source_artifact")
        or record.get("provenance")
        or record.get("source_provenance"),
        "translation_factor": record.get("translation_factor"),
        "calculation_inputs": record.get("calculation_inputs"),
        "retrieval_validation_state": record.get("retrieval_validation_state")
        or record.get("retrieval_validation_status")
        or record.get("validation_state"),
    }
    encoded = json.dumps(core, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def required_cpi_updated_bindings(
    source_lag: dict[str, Any] | None = None,
    years: tuple[int, ...] | None = None,
) -> list[tuple[str, int]]:
    """CPI_UPDATED pairs from frozen OD-010 policy, not generated coverage."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    year_set = set(years)
    pairs = [(component, year) for component, year in FROZEN_CPI_UPDATED_PAIRS if year in year_set]
    if source_lag is not None:
        assert_source_lag_preserves_frozen_od010(source_lag, years=years)
    return pairs


def assert_canonical_component_universe(coverage: dict[str, Any]) -> None:
    """Generated coverage must match the frozen required-component list."""
    listed = coverage.get("required_components")
    if not isinstance(listed, list) or not all(isinstance(item, str) for item in listed):
        raise CoverageAuthorityError("coverage.required_components is missing or malformed")
    if set(listed) != set(REQUIRED_CANDIDATE_COMPONENTS):
        raise CoverageAuthorityError(
            "generated coverage required_components must equal the frozen "
            f"canonical set; got {listed}"
        )
    if list(listed) != list(REQUIRED_CANDIDATE_COMPONENTS):
        raise CoverageAuthorityError(
            "generated coverage required_components order must match the frozen tuple"
        )


def _source_lag_method(source_lag: dict[str, Any], component: str, year: int) -> str | None:
    rec = source_lag.get(component)
    if not isinstance(rec, dict):
        return None
    method = rec.get("translation_method")
    if isinstance(method, dict):
        value = method.get(str(year), method.get(year))
        return str(value) if value is not None else None
    if method is None:
        return None
    return str(method)


def assert_source_lag_preserves_frozen_od010(
    source_lag: dict[str, Any],
    years: tuple[int, ...] | None = None,
) -> None:
    """Fail closed if generated source_lag drops or relabels frozen CPI_UPDATED."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        if year not in years:
            continue
        actual = _source_lag_method(source_lag, component, year)
        if actual != "CPI_UPDATED":
            raise SourceLagAuthorityError(
                f"frozen CPI_UPDATED requirement {component}:{year} is "
                f"{actual!r} in generated source_lag"
            )
    for component in REQUIRED_CANDIDATE_COMPONENTS:
        for year in years:
            expected = expected_translation_method(component, year)
            actual = _source_lag_method(source_lag, component, year)
            if actual is None:
                raise SourceLagAuthorityError(
                    f"generated source_lag missing translation for {component}:{year}"
                )
            if actual != expected:
                raise SourceLagAuthorityError(
                    f"generated source_lag {component}:{year} is {actual!r}, "
                    f"frozen policy requires {expected!r}"
                )


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _year_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _artifacts_complete(artifacts: Any) -> bool:
    if not isinstance(artifacts, list) or not artifacts:
        return False
    for item in artifacts:
        if not isinstance(item, dict):
            return False
        ident = item.get("artifact_id") or item.get("filename")
        sha = item.get("sha256")
        if not _nonempty_str(ident):
            return False
        if not _nonempty_str(sha):
            return False
    return True


def source_id_matches_family(source_id: str, family: str, year: int) -> bool:
    """Documented deterministic mapping: family or family_YYYY."""
    if source_id == family:
        return True
    return source_id == f"{family}_{year}"


def _od010_index(payload: Any) -> dict[tuple[str, int], dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    indexed: dict[tuple[str, int], dict[str, Any]] = {}
    for rec in _normalize_translation_records(payload):
        component = rec.get("component")
        year = _year_int(rec.get("project_cost_year"))
        if isinstance(component, str) and year is not None:
            indexed[(component, year)] = rec
    return indexed


def _binding_record_complete(
    rec: Any,
    *,
    component: str,
    year: int,
    od010_index: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> bool:
    if not isinstance(rec, dict):
        return False
    if rec.get("component") != component:
        return False
    if _year_int(rec.get("project_cost_year")) != year:
        return False
    source_id = rec.get("source_id") or rec.get("source_family")
    if not _nonempty_str(source_id):
        return False
    family = COMPONENT_FRESHNESS_FAMILY.get(component)
    if family and not source_id_matches_family(str(source_id), family, year):
        return False
    if _year_int(rec.get("source_data_year")) is None:
        return False
    if not _artifacts_complete(rec.get("selected_artifacts")):
        return False
    model = rec.get("model_method") or rec.get("transformation_method")
    if not _nonempty_str(model):
        return False
    evidence = rec.get("evidence_status")
    if evidence not in PASSING_BINDING_EVIDENCE:
        return False
    method_component = "connectivity" if component in CONNECTIVITY_SUBCOMPONENTS else component
    expected = expected_translation_method(method_component, year)
    if expected == "SOURCE_CLASSIFIED":
        source_class = rec.get("source_class")
        if source_class not in CONNECTIVITY_SOURCE_CLASS_METHODS:
            return False
        if rec.get("translation_method") != CONNECTIVITY_SOURCE_CLASS_METHODS[str(source_class)]:
            return False
    elif rec.get("translation_method") != expected:
        return False
    if expected == "CPI_UPDATED":
        if od010_index is None:
            return False
        od_rec = od010_index.get((component, year))
        if od_rec is None or not _translation_record_complete(
            od_rec, component=component, year=year
        ):
            return False
        binding_source_year = _year_int(rec.get("source_data_year"))
        od_source_year = _year_int(od_rec.get("source_data_year"))
        if binding_source_year != od_source_year:
            return False
        identity = rec.get("od010_record_identity") or rec.get("translation_record_identity")
        if not isinstance(identity, dict):
            return False
        if identity.get("component") != component:
            return False
        if _year_int(identity.get("project_cost_year")) != year:
            return False
        if _year_int(identity.get("source_data_year")) != od_source_year:
            return False
        claimed = identity.get("record_hash") or identity.get("sha256")
        if claimed != od010_record_hash(od_rec):
            return False
    return True


def _connectivity_complete(
    rec: Any,
    *,
    year: int,
    od010_index: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> bool:
    if not _binding_record_complete(
        rec, component="connectivity", year=year, od010_index=od010_index
    ):
        return False
    subs = rec.get("sub_bindings")
    if not isinstance(subs, dict):
        return False
    for sub in CONNECTIVITY_SUBCOMPONENTS:
        if not _binding_record_complete(
            subs.get(sub), component=sub, year=year, od010_index=od010_index
        ):
            return False
    return True


def _component_year_record(inputs: dict[str, Any], component: str, year: int) -> Any:
    block = inputs.get(component)
    if not isinstance(block, dict):
        return None
    if str(year) in block:
        return block.get(str(year))
    if year in block:
        return block.get(year)
    nested = block.get("years")
    if isinstance(nested, dict):
        if str(year) in nested:
            return nested.get(str(year))
        return nested.get(year)
    return None


def iter_binding_records(
    payload: Any,
    years: tuple[int, ...],
) -> list[tuple[str, int, Any]]:
    components = required_candidate_components()
    if not isinstance(payload, dict):
        return [(component, year, None) for component in components for year in years]
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    rows: list[tuple[str, int, Any]] = []
    for component in components:
        for year in years:
            rec = _component_year_record(inputs, component, year)
            rows.append((component, year, rec))
            if isinstance(rec, dict) and component == "connectivity":
                subs = rec.get("sub_bindings")
                if isinstance(subs, dict):
                    for sub in CONNECTIVITY_SUBCOMPONENTS:
                        rows.append((sub, year, subs.get(sub)))
    return rows


def evaluate_candidate_input_bindings(
    payload: Any,
    years: tuple[int, ...] | None = None,
    od010_payload: Any | None = None,
) -> dict[str, Any]:
    """Derive completeness. Ignore a manually asserted top-level bound flag."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    components = required_candidate_components()
    missing: list[str] = []
    od010_index = _od010_index(od010_payload)
    if not isinstance(payload, dict):
        return {
            "bound": False,
            "missing": [f"{c}:{year}" for c in components for year in years],
            "manual_bound_ignored": False,
            "years": list(years),
            "components": list(components),
        }
    inputs = payload.get("inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    for component in components:
        for year in years:
            rec = _component_year_record(inputs, component, year)
            ok = (
                _connectivity_complete(rec, year=year, od010_index=od010_index)
                if component == "connectivity"
                else _binding_record_complete(
                    rec, component=component, year=year, od010_index=od010_index
                )
            )
            if not ok:
                missing.append(f"{component}:{year}")
    return {
        "bound": not missing,
        "missing": missing,
        "manual_bound_ignored": payload.get("bound") is True,
        "years": list(years),
        "components": list(components),
    }


def _live_artifact_keys(check: Any) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    artifacts = getattr(check, "selected_artifacts", None)
    if artifacts is None and isinstance(check, dict):
        artifacts = check.get("selected_artifacts") or []
    for item in artifacts or ():
        if not isinstance(item, dict):
            continue
        ident = item.get("artifact_id") or item.get("filename")
        sha = item.get("sha256")
        if _nonempty_str(ident) and _nonempty_str(sha):
            keys.add((str(ident), str(sha)))
    selected = getattr(check, "selected_artifact", None)
    if selected is None and isinstance(check, dict):
        selected = check.get("selected_artifact")
    if _nonempty_str(selected) and keys:
        # filename-only selected_artifact still matches if hashes align
        pass
    return keys


def _live_evidence(check: Any) -> str | None:
    status = getattr(check, "retrieval_validation_status", None)
    if status is None and isinstance(check, dict):
        status = check.get("retrieval_validation_status")
    return status if isinstance(status, str) else None


def year_coverage_record(check: Any, year: int) -> dict[str, Any] | None:
    coverage = getattr(check, "year_coverage", None)
    if coverage is None and isinstance(check, dict):
        coverage = check.get("year_coverage")
    extra = getattr(check, "extra", None)
    if coverage is None and isinstance(extra, dict):
        coverage = extra.get("year_coverage")
    if not isinstance(coverage, dict):
        return None
    rec = coverage.get(year)
    if rec is None:
        rec = coverage.get(str(year))
    return rec if isinstance(rec, dict) else None


def authorized_artifacts_for_year(check: Any, year: int) -> set[tuple[str, str]]:
    """Artifacts authorized for one project cost year. Empty if unspecified."""
    rec = year_coverage_record(check, year)
    keys: set[tuple[str, str]] = set()
    if rec is None:
        return keys
    artifacts = rec.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            ident = item.get("artifact_id") or item.get("filename")
            sha = item.get("sha256")
            if _nonempty_str(ident) and _nonempty_str(sha):
                keys.add((str(ident), str(sha)))
    if keys:
        return keys
    ident = rec.get("artifact")
    if _nonempty_str(ident):
        sha = rec.get("sha256")
        if _nonempty_str(sha):
            keys.add((str(ident), str(sha)))
        else:
            for live_id, live_sha in _live_artifact_keys(check):
                if live_id == ident:
                    keys.add((live_id, live_sha))
    return keys


def live_source_data_year(check: Any, year: int) -> int | None:
    rec = year_coverage_record(check, year)
    if rec is None:
        return None
    return _year_int(rec.get("source_data_year"))


def validate_candidate_bindings_against_snapshot(
    payload: Any,
    live_checks: Any,
    years: tuple[int, ...] | None = None,
    od010_payload: Any | None = None,
) -> dict[str, Any]:
    """Require candidate bindings to reference the same live freshness artifacts."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    issues: list[str] = []
    if not isinstance(live_checks, dict):
        return {"ok": False, "issues": ["LIVE_CHECKS_MISSING"]}
    structural = evaluate_candidate_input_bindings(
        payload, years=years, od010_payload=od010_payload
    )
    if not structural["bound"]:
        issues.extend(f"{item}:STRUCTURALLY_INCOMPLETE" for item in structural["missing"])
    for component, year, rec in iter_binding_records(payload, years):
        if component in CONNECTIVITY_SUBCOMPONENTS:
            family = COMPONENT_FRESHNESS_FAMILY[component]
        else:
            family = COMPONENT_FRESHNESS_FAMILY.get(component)
        if not family or not isinstance(rec, dict):
            continue
        check = live_checks.get(family)
        if check is None:
            issues.append(f"{component}:{year}:NO_LIVE_FAMILY")
            continue
        source = rec.get("source_id") or rec.get("source_family")
        if not _nonempty_str(source) or not source_id_matches_family(str(source), family, year):
            issues.append(f"{component}:{year}:SOURCE_ID_MISMATCH")
        year_rec = year_coverage_record(check, year)
        if year_rec is None or year_rec.get("covered") is not True:
            issues.append(f"{component}:{year}:YEAR_NOT_COVERED")
        live_sdy = live_source_data_year(check, year)
        bind_sdy = _year_int(rec.get("source_data_year"))
        if live_sdy is None:
            issues.append(f"{component}:{year}:SOURCE_DATA_YEAR_UNSPECIFIED")
        elif bind_sdy != live_sdy:
            issues.append(f"{component}:{year}:SOURCE_DATA_YEAR_MISMATCH")
        year_keys = authorized_artifacts_for_year(check, year)
        if not year_keys:
            issues.append(f"{component}:{year}:YEAR_ARTIFACTS_UNSPECIFIED")
        for item in rec.get("selected_artifacts") or []:
            if not isinstance(item, dict):
                issues.append(f"{component}:{year}:YEAR_ARTIFACT_MISMATCH")
                continue
            ident = item.get("artifact_id") or item.get("filename")
            sha = item.get("sha256")
            if not _nonempty_str(ident) or not _nonempty_str(sha):
                issues.append(f"{component}:{year}:YEAR_ARTIFACT_MISMATCH")
                continue
            if (str(ident), str(sha)) not in year_keys:
                issues.append(f"{component}:{year}:YEAR_ARTIFACT_MISMATCH")
        live_status = _live_evidence(check)
        if rec.get("evidence_status") != live_status:
            issues.append(f"{component}:{year}:EVIDENCE_STATUS_MISMATCH")
    unique: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        if issue in seen:
            continue
        seen.add(issue)
        unique.append(issue)
    return {"ok": not unique, "issues": unique}


def od010_series_coverage(check: Any) -> dict[str, Any]:
    """Structured live OD-010 series inventory. Empty if the family is too vague."""
    coverage = getattr(check, "series_coverage", None)
    if coverage is None and isinstance(check, dict):
        coverage = check.get("series_coverage")
    extra = getattr(check, "extra", None)
    if extra is None and isinstance(check, dict):
        extra = check.get("extra")
    if coverage is None and isinstance(extra, dict):
        coverage = extra.get("series_coverage")
    return coverage if isinstance(coverage, dict) else {}


def od010_series_slot(check: Any, component: str, year: int) -> dict[str, Any] | None:
    coverage = od010_series_coverage(check)
    block = coverage.get(component)
    if not isinstance(block, dict):
        return None
    rec = block.get(year)
    if rec is None:
        rec = block.get(str(year))
    return rec if isinstance(rec, dict) else None


def unbound_od010_series_coverage(
    years: tuple[int, ...] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Required series slots with no invented identifiers or observations."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    year_set = set(years)
    coverage: dict[str, dict[str, dict[str, Any]]] = {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        if year not in year_set:
            continue
        coverage.setdefault(component, {})[str(year)] = {
            "covered": False,
            "official_series_identifier": None,
            "publisher": None,
            "latest_observation_period": None,
            "target_observation_period": None,
            "base_observation_period": None,
            "source_data_year": None,
            "selected_artifact": None,
            "api_identity": None,
            "sha256": None,
            "base_index_value": None,
            "target_index_value": None,
            "note": "series not inventoried; do not invent official series identifiers",
        }
    return coverage


def od010_series_inventory_is_specific(
    check: Any,
    years: tuple[int, ...] | None = None,
) -> bool:
    """True only when every frozen CPI_UPDATED pair has concrete live series evidence."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    coverage = od010_series_coverage(check)
    if not coverage:
        return False
    for component, year in required_cpi_updated_bindings(years=years):
        slot = od010_series_slot(check, component, year)
        if slot is None or slot.get("covered") is not True:
            return False
        if not _nonempty_str(slot.get("official_series_identifier")):
            return False
        if not _nonempty_str(slot.get("publisher")):
            return False
        period = (
            slot.get("latest_observation_period")
            or slot.get("target_observation_period")
            or slot.get("observation_period")
        )
        if not _nonempty_str(period):
            return False
        artifact = slot.get("selected_artifact") or slot.get("api_identity")
        if not _nonempty_str(artifact):
            return False
        if _year_int(slot.get("source_data_year")) is None:
            return False
        if not _nonempty_str(slot.get("base_observation_period")):
            return False
        if not _positive_finite_index(slot.get("base_index_value")):
            return False
        if not _positive_finite_index(slot.get("target_index_value")):
            return False
    return True


def _od010_record_series_id(rec: dict[str, Any]) -> str | None:
    value = (
        rec.get("official_series_identifier") or rec.get("series_id") or rec.get("official_series")
    )
    return str(value) if _nonempty_str(value) else None


def _od010_record_period(rec: dict[str, Any]) -> str | None:
    value = rec.get("observation_period") or rec.get("period")
    return str(value) if _nonempty_str(value) else None


def _od010_record_artifact(rec: dict[str, Any]) -> str | None:
    value = rec.get("source_artifact") or rec.get("provenance") or rec.get("source_provenance")
    if isinstance(value, dict):
        ident = value.get("artifact_id") or value.get("filename") or value.get("api_identity")
        return str(ident) if _nonempty_str(ident) else None
    return str(value) if _nonempty_str(value) else None


def _od010_record_sha(rec: dict[str, Any]) -> str | None:
    """Table-level identity only. Do not fall back to calculation_inputs SHA."""
    for key in ("sha256", "source_artifact_sha256", "response_identity"):
        value = rec.get(key)
        if _nonempty_str(value):
            return str(value)
    artifact = rec.get("source_artifact")
    if isinstance(artifact, dict) and _nonempty_str(artifact.get("sha256")):
        return str(artifact["sha256"])
    return None


def _calc_identity_sha(calc: dict[str, Any]) -> str | None:
    for key in ("sha256", "response_identity"):
        value = calc.get(key)
        if _nonempty_str(value):
            return str(value)
    return None


def _as_decimal(value: Any) -> Decimal | None:
    """Parse an observation/factor. None if missing, non-numeric, NaN, or Inf."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Decimal):
        return value if value.is_finite() else None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError):
        return None
    return parsed if parsed.is_finite() else None


def _positive_finite_index(value: Any) -> bool:
    parsed = _as_decimal(value)
    return parsed is not None and parsed > 0


def index_values_equal(left: Any, right: Any) -> bool:
    """Exact Decimal(str) equality after normalize. No loose float tolerance."""
    a = _as_decimal(left)
    b = _as_decimal(right)
    if a is None or b is None:
        return False
    return a == b or a.normalize() == b.normalize()


def factors_equal(left: Any, right: Any) -> bool:
    """Exact Decimal compare, then 1e-12 relative fallback for stored precision."""
    a = _as_decimal(left)
    b = _as_decimal(right)
    if a is None or b is None:
        return False
    if a == b or a.normalize() == b.normalize():
        return True
    scale = max(abs(a), abs(b), Decimal(1))
    return abs(a - b) <= max(FACTOR_ABS_TOLERANCE, FACTOR_REL_TOLERANCE * scale)


def recompute_cpi_updated_factor(base_index_value: Any, target_index_value: Any) -> Decimal | None:
    """CPI_UPDATED operation: target / base. None if either value is invalid."""
    base = _as_decimal(base_index_value)
    target = _as_decimal(target_index_value)
    if base is None or target is None:
        return None
    if base <= 0 or target <= 0:
        return None
    return target / base


def _live_series_period(slot: dict[str, Any]) -> str | None:
    value = (
        slot.get("latest_observation_period")
        or slot.get("target_observation_period")
        or slot.get("observation_period")
    )
    return str(value) if _nonempty_str(value) else None


def _live_series_artifact(slot: dict[str, Any]) -> str | None:
    value = slot.get("selected_artifact") or slot.get("api_identity")
    return str(value) if _nonempty_str(value) else None


def _live_series_sha(slot: dict[str, Any]) -> str | None:
    for key in ("sha256", "response_identity"):
        value = slot.get(key)
        if _nonempty_str(value):
            return str(value)
    return None


def _calculation_inputs(rec: dict[str, Any]) -> dict[str, Any]:
    calc = rec.get("calculation_inputs")
    return calc if isinstance(calc, dict) else {}


def _normalized_od010_cross_pair(
    component: str,
    year: int,
    rec: dict[str, Any] | None,
    slot: dict[str, Any] | None,
    *,
    cross_bound: bool,
) -> dict[str, Any]:
    calc = _calculation_inputs(rec or {})
    live_base = None if slot is None else slot.get("base_index_value")
    live_target = None if slot is None else slot.get("target_index_value")
    table_base = calc.get("base_index_value")
    table_target = calc.get("target_index_value")
    recomputed = recompute_cpi_updated_factor(live_base, live_target)
    return {
        "component": component,
        "project_cost_year": year,
        "source_data_year": None if rec is None else rec.get("source_data_year"),
        "official_series_identifier": None if rec is None else _od010_record_series_id(rec),
        "live_official_series_identifier": None
        if slot is None
        else slot.get("official_series_identifier"),
        "publisher": None if rec is None else rec.get("publisher"),
        "observation_period": None if rec is None else _od010_record_period(rec),
        "live_observation_period": None if slot is None else _live_series_period(slot),
        "source_artifact": None if rec is None else _od010_record_artifact(rec),
        "live_artifact": None if slot is None else _live_series_artifact(slot),
        "sha256": None if rec is None else _od010_record_sha(rec),
        "live_sha256": None if slot is None else _live_series_sha(slot),
        "base_observation_period": calc.get("base_observation_period"),
        "target_observation_period": calc.get("target_observation_period"),
        "live_base_index_value": live_base,
        "table_base_index_value": table_base,
        "live_target_index_value": live_target,
        "table_target_index_value": table_target,
        "claimed_translation_factor": None if rec is None else rec.get("translation_factor"),
        "calculation_input_translation_factor": calc.get("translation_factor"),
        "recomputed_translation_factor": (None if recomputed is None else format(recomputed, "f")),
        "base_index_value": table_base,
        "target_index_value": table_target,
        "translation_factor": None if rec is None else rec.get("translation_factor"),
        "cross_bound": cross_bound,
    }


def validate_od010_bindings_against_snapshot(
    od010_payload: Any,
    live_checks: Any,
    years: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Cross-bind every frozen CPI_UPDATED record to live od010_price_index evidence."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    issues: list[str] = []
    required = required_cpi_updated_bindings(years=years)
    required_labels = [f"{component}:{year}" for component, year in required]
    if not isinstance(live_checks, dict):
        return {
            "ok": False,
            "issues": ["OD010_LIVE_FRESHNESS_MISSING"],
            "required": required_labels,
            "normalized": [],
        }
    check = live_checks.get("od010_price_index")
    if check is None:
        return {
            "ok": False,
            "issues": ["OD010_LIVE_FRESHNESS_MISSING"],
            "required": required_labels,
            "normalized": [],
        }
    coverage = od010_series_coverage(check)
    inventory_specific = od010_series_inventory_is_specific(check, years=years)
    if not coverage or not inventory_specific:
        issues.append("OD010_SERIES_COVERAGE_TOO_VAGUE")
    if not isinstance(od010_payload, dict):
        issues.append("OD010_TABLE_ABSENT")
        normalized = [
            _normalized_od010_cross_pair(
                component,
                year,
                None,
                od010_series_slot(check, component, year),
                cross_bound=False,
            )
            for component, year in required
        ]
        return {
            "ok": False,
            "issues": _unique_issue_strings(issues),
            "required": required_labels,
            "normalized": normalized,
        }

    indexed = _od010_index(od010_payload)
    normalized: list[dict[str, Any]] = []
    for component, year in required:
        rec = indexed.get((component, year))
        slot = od010_series_slot(check, component, year)
        pair_issues: list[str] = []
        if rec is None:
            pair_issues.append(f"{component}:{year}:OD010_RECORD_MISSING")
        elif not _translation_record_complete(rec, component=component, year=year):
            pair_issues.append(f"{component}:{year}:OD010_RECORD_INCOMPLETE")
        if slot is None or slot.get("covered") is not True:
            pair_issues.append(f"{component}:{year}:SERIES_NOT_COVERED")
        if rec is not None and slot is not None and slot.get("covered") is True:
            table_series = _od010_record_series_id(rec)
            live_series = (
                str(slot["official_series_identifier"])
                if _nonempty_str(slot.get("official_series_identifier"))
                else None
            )
            if table_series != live_series:
                pair_issues.append(f"{component}:{year}:SERIES_IDENTIFIER_MISMATCH")
            live_sdy = _year_int(slot.get("source_data_year"))
            table_sdy = _year_int(rec.get("source_data_year"))
            if live_sdy is None:
                pair_issues.append(f"{component}:{year}:LIVE_SOURCE_DATA_YEAR_UNSPECIFIED")
            elif table_sdy != live_sdy:
                pair_issues.append(f"{component}:{year}:SOURCE_DATA_YEAR_MISMATCH")
            live_publisher = slot.get("publisher")
            if _nonempty_str(live_publisher) and rec.get("publisher") != live_publisher:
                pair_issues.append(f"{component}:{year}:PUBLISHER_MISMATCH")
            table_period = _od010_record_period(rec)
            live_period = _live_series_period(slot)
            if live_period is None:
                pair_issues.append(f"{component}:{year}:LIVE_OBSERVATION_UNSPECIFIED")
            elif table_period != live_period:
                pair_issues.append(f"{component}:{year}:OBSERVATION_PERIOD_MISMATCH")
            table_artifact = _od010_record_artifact(rec)
            live_artifact = _live_series_artifact(slot)
            live_api = slot.get("api_identity")
            artifact_ok = False
            if _nonempty_str(table_artifact) and _nonempty_str(live_artifact):
                artifact_ok = table_artifact == live_artifact or (
                    _nonempty_str(live_api) and table_artifact == str(live_api)
                )
            if not artifact_ok:
                pair_issues.append(f"{component}:{year}:ARTIFACT_MISMATCH")
            table_sha = _od010_record_sha(rec)
            live_sha = _live_series_sha(slot)
            if (live_sha or table_sha) and table_sha != live_sha:
                pair_issues.append(f"{component}:{year}:ARTIFACT_HASH_MISMATCH")
            calc = _calculation_inputs(rec)
            if not calc:
                pair_issues.append(f"{component}:{year}:TRANSLATION_FACTOR_UNBOUND")
            else:
                calc_series = (
                    calc.get("official_series_identifier") or calc.get("series_id") or table_series
                )
                if live_series is not None and str(calc_series) != live_series:
                    pair_issues.append(f"{component}:{year}:CALC_SERIES_MISMATCH")
                calc_target = calc.get("target_observation_period") or calc.get(
                    "observation_period"
                )
                if not _nonempty_str(calc_target):
                    pair_issues.append(f"{component}:{year}:CALC_TARGET_PERIOD_MISSING")
                elif live_period is not None and str(calc_target) != live_period:
                    pair_issues.append(f"{component}:{year}:OBSERVATION_PERIOD_MISMATCH")
                live_base = slot.get("base_observation_period")
                calc_base = calc.get("base_observation_period")
                if _nonempty_str(live_base):
                    if not _nonempty_str(calc_base) or str(calc_base) != str(live_base):
                        pair_issues.append(f"{component}:{year}:CALC_BASE_PERIOD_MISMATCH")
                elif not _nonempty_str(calc_base):
                    pair_issues.append(f"{component}:{year}:CALC_BASE_PERIOD_MISSING")
                calc_artifact = calc.get("source_artifact") or calc.get("api_identity")
                if _nonempty_str(calc_artifact) and not (
                    str(calc_artifact) == live_artifact
                    or (_nonempty_str(live_api) and str(calc_artifact) == str(live_api))
                ):
                    pair_issues.append(f"{component}:{year}:CALC_ARTIFACT_MISMATCH")
                calc_sha = _calc_identity_sha(calc)
                if _nonempty_str(calc_sha) and (
                    (live_sha and calc_sha != live_sha) or (table_sha and calc_sha != table_sha)
                ):
                    pair_issues.append(f"{component}:{year}:CALC_ARTIFACT_HASH_MISMATCH")
                live_base_value = slot.get("base_index_value")
                live_target_value = slot.get("target_index_value")
                if not _positive_finite_index(live_base_value):
                    pair_issues.append(f"{component}:{year}:INVALID_BASE_INDEX_VALUE")
                if not _positive_finite_index(live_target_value):
                    pair_issues.append(f"{component}:{year}:INVALID_TARGET_INDEX_VALUE")
                calc_base_value = calc.get("base_index_value")
                calc_target_value = calc.get("target_index_value")
                if not _positive_finite_index(calc_base_value):
                    pair_issues.append(f"{component}:{year}:INVALID_BASE_INDEX_VALUE")
                elif _positive_finite_index(live_base_value) and not index_values_equal(
                    calc_base_value, live_base_value
                ):
                    pair_issues.append(f"{component}:{year}:CALC_BASE_VALUE_MISMATCH")
                if not _positive_finite_index(calc_target_value):
                    pair_issues.append(f"{component}:{year}:INVALID_TARGET_INDEX_VALUE")
                elif _positive_finite_index(live_target_value) and not index_values_equal(
                    calc_target_value, live_target_value
                ):
                    pair_issues.append(f"{component}:{year}:CALC_TARGET_VALUE_MISMATCH")
                expected = recompute_cpi_updated_factor(live_base_value, live_target_value)
                record_factor = rec.get("translation_factor")
                calc_factor = calc.get("translation_factor")
                if expected is None:
                    pair_issues.append(f"{component}:{year}:TRANSLATION_FACTOR_MISMATCH")
                else:
                    if not factors_equal(record_factor, expected):
                        pair_issues.append(f"{component}:{year}:TRANSLATION_FACTOR_MISMATCH")
                    if (
                        calc_factor is None
                        or not factors_equal(calc_factor, expected)
                        or not factors_equal(calc_factor, record_factor)
                    ):
                        pair_issues.append(f"{component}:{year}:TRANSLATION_FACTOR_MISMATCH")
        issues.extend(pair_issues)
        normalized.append(
            _normalized_od010_cross_pair(component, year, rec, slot, cross_bound=not pair_issues)
        )
    unique = _unique_issue_strings(issues)
    return {
        "ok": not unique,
        "issues": unique,
        "required": required_labels,
        "normalized": normalized,
    }


def _unique_issue_strings(issues: list[str]) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    for issue in issues:
        if issue in seen:
            continue
        seen.add(issue)
        unique.append(issue)
    return unique


def evaluate_od010_translation_table(
    payload: Any,
    years: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Derive OD-010 completeness from frozen CPI_UPDATED pairs."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    generated = load_source_lag()
    if generated:
        assert_source_lag_preserves_frozen_od010(generated, years=years)
    required = required_cpi_updated_bindings(years=years)
    missing: list[str] = []
    if not isinstance(payload, dict):
        return {
            "bound": False,
            "missing": [f"{c}:{y}" for c, y in required],
            "required": [f"{c}:{y}" for c, y in required],
            "manual_bound_ignored": False,
        }
    records = _normalize_translation_records(payload)
    indexed: dict[tuple[str, int], dict[str, Any]] = {}
    for rec in records:
        component = rec.get("component")
        year = _year_int(rec.get("project_cost_year"))
        if isinstance(component, str) and year is not None:
            indexed[(component, year)] = rec
    for component, year in required:
        rec = indexed.get((component, year))
        if rec is None or not _translation_record_complete(rec, component=component, year=year):
            missing.append(f"{component}:{year}")
    return {
        "bound": not missing and bool(required),
        "missing": missing,
        "required": [f"{c}:{y}" for c, y in required],
        "manual_bound_ignored": payload.get("bound") is True,
    }


def _normalize_translation_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
    series = payload.get("series")
    if isinstance(series, list):
        return [item for item in series if isinstance(item, dict)]
    if not isinstance(series, dict):
        return []
    out: list[dict[str, Any]] = []
    for key, value in series.items():
        if isinstance(value, dict) and "component" in value:
            out.append(value)
            continue
        if isinstance(value, dict):
            looks_like_years = any(_year_int(k) is not None for k in value)
            if looks_like_years:
                for year_key, rec in value.items():
                    year = _year_int(year_key)
                    if year is None or not isinstance(rec, dict):
                        continue
                    merged = dict(rec)
                    merged.setdefault("component", key)
                    merged.setdefault("project_cost_year", year)
                    out.append(merged)
    return out


def _translation_record_complete(rec: dict[str, Any], *, component: str, year: int) -> bool:
    if rec.get("component") != component:
        return False
    if _year_int(rec.get("project_cost_year")) != year:
        return False
    if _year_int(rec.get("source_data_year")) is None:
        return False
    series_id = (
        rec.get("official_series_identifier") or rec.get("series_id") or rec.get("official_series")
    )
    if not _nonempty_str(series_id):
        return False
    if not _nonempty_str(rec.get("publisher")):
        return False
    period = rec.get("observation_period") or rec.get("period")
    if not _nonempty_str(period):
        return False
    provenance = rec.get("source_artifact") or rec.get("provenance") or rec.get("source_provenance")
    if not _nonempty_str(provenance):
        return False
    factor = rec.get("translation_factor")
    calc_inputs = rec.get("calculation_inputs")
    has_factor = isinstance(factor, (int, float)) and not isinstance(factor, bool)
    has_inputs = isinstance(calc_inputs, dict) and bool(calc_inputs)
    if not has_factor and not has_inputs:
        return False
    state = (
        rec.get("retrieval_validation_state")
        or rec.get("retrieval_validation_status")
        or rec.get("validation_state")
    )
    return state in PASSING_BINDING_EVIDENCE


@dataclass(frozen=True)
class CapturedJsonArtifact:
    path: str
    exists: bool
    raw_sha256: str | None
    payload: Any


def capture_json_artifact(path: Path) -> CapturedJsonArtifact:
    """Read file bytes once. Hash and parse those exact bytes."""
    rel = _relative_metadata_path(path)
    if not path.exists():
        return CapturedJsonArtifact(path=rel, exists=False, raw_sha256=None, payload=None)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = None
    return CapturedJsonArtifact(path=rel, exists=True, raw_sha256=digest, payload=payload)


def _load_json(path: Path) -> Any:
    return capture_json_artifact(path).payload


def candidate_inputs_are_bound(path: Path | None = None) -> bool:
    payload = _load_json(path or CANDIDATE_INPUT_BINDINGS)
    if payload is None:
        return False
    od010_payload = _load_json(OD010_TABLE)
    return evaluate_candidate_input_bindings(payload, od010_payload=od010_payload)["bound"] is True


def od010_translation_is_bound(path: Path | None = None) -> bool:
    payload = _load_json(path or OD010_TABLE)
    if payload is None:
        return False
    return evaluate_od010_translation_table(payload)["bound"] is True


def _relative_metadata_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.name


def _normalized_binding_identities(payload: Any, years: tuple[int, ...]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for component, year, rec in iter_binding_records(payload, years):
        if not isinstance(rec, dict):
            out.append({"component": component, "project_cost_year": year, "present": False})
            continue
        artifacts = []
        for item in rec.get("selected_artifacts") or []:
            if isinstance(item, dict):
                artifacts.append(
                    {
                        "artifact_id": item.get("artifact_id") or item.get("filename"),
                        "sha256": item.get("sha256"),
                    }
                )
        out.append(
            {
                "component": component,
                "project_cost_year": year,
                "present": True,
                "source_id": rec.get("source_id") or rec.get("source_family"),
                "source_data_year": rec.get("source_data_year"),
                "evidence_status": rec.get("evidence_status"),
                "translation_method": rec.get("translation_method"),
                "artifacts": artifacts,
            }
        )
    return out


def _normalized_od010_identities(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    out: list[dict[str, Any]] = []
    for rec in _normalize_translation_records(payload):
        calc = (
            rec.get("calculation_inputs") if isinstance(rec.get("calculation_inputs"), dict) else {}
        )
        out.append(
            {
                "component": rec.get("component"),
                "project_cost_year": rec.get("project_cost_year"),
                "source_data_year": rec.get("source_data_year"),
                "official_series_identifier": rec.get("official_series_identifier")
                or rec.get("series_id"),
                "publisher": rec.get("publisher"),
                "observation_period": rec.get("observation_period") or rec.get("period"),
                "source_artifact": rec.get("source_artifact") or rec.get("provenance"),
                "sha256": rec.get("sha256") or (calc.get("sha256") if calc else None),
                "translation_factor": rec.get("translation_factor"),
                "base_observation_period": calc.get("base_observation_period") if calc else None,
                "target_observation_period": calc.get("target_observation_period")
                if calc
                else None,
                "base_index_value": calc.get("base_index_value") if calc else None,
                "target_index_value": calc.get("target_index_value") if calc else None,
            }
        )
    return out


def candidate_input_binding_identity(
    path: Path | None = None,
    payload: Any | None = None,
    evaluation: dict[str, Any] | None = None,
    *,
    sha256: str | None = None,
    exists: bool | None = None,
    captured: bool = False,
) -> dict[str, Any]:
    target = path or CANDIDATE_INPUT_BINDINGS
    if not captured and payload is None:
        artifact = capture_json_artifact(target)
        payload = artifact.payload
        sha256 = artifact.raw_sha256
        exists = artifact.exists
    if evaluation is None:
        if payload is None:
            from foundation.living_cost.freshness import required_project_cost_years

            years = required_project_cost_years()
            missing = [
                f"{component}:{year}"
                for component in required_candidate_components()
                for year in years
            ]
            evaluation = {
                "bound": False,
                "missing": missing,
                "manual_bound_ignored": False,
                "years": list(years),
            }
        else:
            evaluation = evaluate_candidate_input_bindings(payload)
    years_raw = evaluation.get("years") or []
    years = tuple(int(year) for year in years_raw) if years_raw else ()
    return {
        "path": _relative_metadata_path(target),
        "exists": bool(exists) if exists is not None else bool(payload),
        "bound": evaluation["bound"],
        "missing": evaluation.get("missing", []),
        "sha256": sha256,
        "normalized": _normalized_binding_identities(payload, years) if years else [],
    }


def translation_binding_identity(
    path: Path | None = None,
    payload: Any | None = None,
    evaluation: dict[str, Any] | None = None,
    *,
    sha256: str | None = None,
    exists: bool | None = None,
    captured: bool = False,
) -> dict[str, Any]:
    target = path or OD010_TABLE
    if not captured and payload is None:
        artifact = capture_json_artifact(target)
        payload = artifact.payload
        sha256 = artifact.raw_sha256
        exists = artifact.exists
    if evaluation is None:
        if payload is None:
            required = [
                f"{component}:{year}" for component, year in required_cpi_updated_bindings()
            ]
            evaluation = {
                "bound": False,
                "missing": required or ["ABSENT"],
                "required": required,
                "manual_bound_ignored": False,
            }
        else:
            evaluation = evaluate_od010_translation_table(payload)
    return {
        "path": _relative_metadata_path(target),
        "exists": bool(exists) if exists is not None else bool(payload),
        "bound": evaluation["bound"],
        "missing": evaluation.get("missing", []),
        "required": evaluation.get("required", []),
        "sha256": sha256,
        "normalized": _normalized_od010_identities(payload),
    }


def load_candidate_binding_payload(path: Path | None = None) -> Any:
    return _load_json(path or CANDIDATE_INPUT_BINDINGS)


def load_od010_payload(path: Path | None = None) -> Any:
    return _load_json(path or OD010_TABLE)


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
