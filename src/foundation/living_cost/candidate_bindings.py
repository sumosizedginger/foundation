"""Structural validators for candidate-input and OD-010 translation bindings.

bound=true is DERIVED from complete valid records. A manually asserted
top-level boolean is never trusted. This module does not calculate an MSLC
and does not create fake bindings.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def load_source_lag() -> dict[str, Any]:
    """Canonical source-lag / translation-method metadata."""
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
    """Prefer coverage metadata; fall back to the frozen component list."""
    if SOURCE_COVERAGE.exists():
        try:
            payload = json.loads(SOURCE_COVERAGE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload = None
        if isinstance(payload, dict):
            listed = payload.get("required_components")
            if isinstance(listed, list) and listed and all(isinstance(x, str) for x in listed):
                return tuple(listed)
    return REQUIRED_CANDIDATE_COMPONENTS


def required_cpi_updated_bindings(
    source_lag: dict[str, Any] | None = None,
    years: tuple[int, ...] | None = None,
) -> list[tuple[str, int]]:
    """Component/year pairs whose source-lag method is CPI_UPDATED."""
    if source_lag is None:
        source_lag = load_source_lag()
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    required: list[tuple[str, int]] = []
    for component, rec in source_lag.items():
        if not isinstance(rec, dict):
            continue
        method = rec.get("translation_method")
        for year in years:
            if isinstance(method, dict):
                year_method = method.get(str(year), method.get(year))
            else:
                year_method = method
            if year_method == "CPI_UPDATED":
                required.append((str(component), int(year)))
    return required


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


def _binding_record_complete(
    rec: Any,
    *,
    component: str,
    year: int,
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
    if _year_int(rec.get("source_data_year")) is None:
        return False
    if not _artifacts_complete(rec.get("selected_artifacts")):
        return False
    model = rec.get("model_method") or rec.get("transformation_method")
    if not _nonempty_str(model):
        return False
    if not _nonempty_str(rec.get("evidence_status")):
        return False
    return _nonempty_str(rec.get("translation_method"))


def _connectivity_complete(rec: Any, *, year: int) -> bool:
    if not _binding_record_complete(rec, component="connectivity", year=year):
        return False
    subs = rec.get("sub_bindings")
    if not isinstance(subs, dict):
        return False
    for sub in CONNECTIVITY_SUBCOMPONENTS:
        if not _binding_record_complete(subs.get(sub), component=sub, year=year):
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


def evaluate_candidate_input_bindings(
    payload: Any,
    years: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Derive completeness. Ignore a manually asserted top-level bound flag."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
    components = required_candidate_components()
    missing: list[str] = []
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
                _connectivity_complete(rec, year=year)
                if component == "connectivity"
                else _binding_record_complete(rec, component=component, year=year)
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


def evaluate_od010_translation_table(
    payload: Any,
    years: tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Derive OD-010 completeness from required CPI_UPDATED pairs."""
    if years is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
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
            # component -> year -> record
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
                continue
        # bare {"foo": "..."} is not a binding record
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
    return _nonempty_str(state)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def candidate_inputs_are_bound(path: Path | None = None) -> bool:
    payload = _load_json(path or CANDIDATE_INPUT_BINDINGS)
    if payload is None:
        return False
    return evaluate_candidate_input_bindings(payload)["bound"] is True


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


def candidate_input_binding_identity(path: Path | None = None) -> dict[str, Any]:
    target = path or CANDIDATE_INPUT_BINDINGS
    payload = _load_json(target)
    if payload is None:
        from foundation.living_cost.freshness import required_project_cost_years

        years = required_project_cost_years()
        missing = [
            f"{component}:{year}" for component in required_candidate_components() for year in years
        ]
        evaluation = {
            "bound": False,
            "missing": missing,
            "manual_bound_ignored": False,
        }
    else:
        evaluation = evaluate_candidate_input_bindings(payload)
    return {
        "path": _relative_metadata_path(target),
        "exists": target.exists(),
        "bound": evaluation["bound"],
        "missing": evaluation.get("missing", []),
        "sha256": _file_sha256(target),
    }


def translation_binding_identity(path: Path | None = None) -> dict[str, Any]:
    target = path or OD010_TABLE
    payload = _load_json(target)
    if payload is None:
        required = [f"{component}:{year}" for component, year in required_cpi_updated_bindings()]
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
        "exists": target.exists(),
        "bound": evaluation["bound"],
        "missing": evaluation.get("missing", []),
        "required": evaluation.get("required", []),
        "sha256": _file_sha256(target),
    }


def _file_sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    try:
        import hashlib

        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None
