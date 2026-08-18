"""Official BLS CPI series inventory for frozen OD-010 CPI_UPDATED pairs.

Does not calculate an MSLC. Series IDs are official BLS CPI-U NSA identifiers
documented by BLS, not invented.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import requests

from foundation.living_cost.candidate_bindings import (
    FROZEN_CPI_UPDATED_PAIRS,
    recompute_cpi_updated_factor,
)
from foundation.sources.bls import BLS_V2_URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"
OD010_TABLE = METADATA_DIR / "living_cost_od010_translation_table.json"
OD010_RETRIEVE = METADATA_DIR / "living_cost_od010_bls_retrieve.json"
OD010_LIVE_CURRENTNESS = METADATA_DIR / "living_cost_od010_live_currentness.json"
OD010_TABLE_HISTORY_DIR = METADATA_DIR / "history"

_MONTH_PERIOD: dict[str, str] = {
    "january": "M01",
    "february": "M02",
    "march": "M03",
    "april": "M04",
    "may": "M05",
    "june": "M06",
    "july": "M07",
    "august": "M08",
    "september": "M09",
    "october": "M10",
    "november": "M11",
    "december": "M12",
    "annual": "M13",
}
INVALIDATING_CURRENTNESS = frozenset({"NEWER_AVAILABLE", "STALE", "INVALIDATED"})

BLS_CPI_LANDING = "https://www.bls.gov/cpi/"
BLS_API_IDENTITY = BLS_V2_URL

# Official BLS CPI-U, U.S. city average, not seasonally adjusted.
# Item codes from BLS CU series format (https://www.bls.gov/help/hlpforma.htm#CU)
# and official BLS timeseries / fact sheets.
FROZEN_OD010_SERIES: dict[str, dict[str, str]] = {
    "health_oop": {
        "official_series_identifier": "CUUR0000SAM",
        "item": "Medical care",
        "publisher": "BLS",
        "landing_url": "https://data.bls.gov/timeseries/CUUR0000SAM",
        "rationale": "OD-010: medical-care index for lagged MEPS OOP dollars.",
        "disclosure": None,
    },
    "insurance": {
        "official_series_identifier": "CUUR0000SETE",
        "item": "Motor vehicle insurance",
        "publisher": "BLS",
        "landing_url": "https://data.bls.gov/timeseries/CUUR0000SETE",
        "rationale": (
            "OD-010 / OD-006: motor-vehicle-insurance CPI. Official BLS fact sheet "
            "https://www.bls.gov/cpi/factsheets/motor-vehicle-insurance.htm"
        ),
        "disclosure": None,
    },
    "maintenance": {
        "official_series_identifier": "CUUR0000SETD",
        "item": "Motor vehicle maintenance and repair",
        "publisher": "BLS",
        "landing_url": "https://data.bls.gov/timeseries/CUUR0000SETD",
        "rationale": "OD-010: motor vehicle maintenance/repair index for lagged CE maintenance.",
        "disclosure": None,
    },
    "recreation": {
        "official_series_identifier": "CUUR0000SAR",
        "item": "Recreation",
        "publisher": "BLS",
        "landing_url": "https://data.bls.gov/timeseries/CUUR0000SAR",
        "rationale": "OD-010: recreation CPI is defensible for CE recreation/social dollars.",
        "disclosure": None,
    },
    "essentials": {
        "official_series_identifier": "CUUR0000SA0",
        "item": "All items",
        "publisher": "BLS",
        "landing_url": "https://data.bls.gov/timeseries/CUUR0000SA0",
        "rationale": (
            "OD-010: essentials is a mixed CE necessity basket (hygiene, cleaning, "
            "toiletries, basic apparel). No single more-specific official index "
            "covers the frozen allowlist without a new owner series choice. "
            "CPI-U All items is the disclosed fallback the freeze permits."
        ),
        "disclosure": "CPI-U All items fallback; mixed essentials basket.",
    },
}

# Source data years currently implied by frozen evidence (not relabeled).
# MEPS newest released FYC = 2023; NAIC AUT-PB 2022-2023 = 2023; CE 2024.
DEFAULT_SOURCE_DATA_YEAR: dict[str, int] = {
    "health_oop": 2023,
    "insurance": 2023,
    "maintenance": 2024,
    "essentials": 2024,
    "recreation": 2024,
}

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; The-Foundation/0.2; "
        "+https://github.com/sumosizedginger/foundation)"
    ),
    "Accept": "application/json",
}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def required_od010_series_ids() -> list[str]:
    """Official BLS series currently selected for frozen OD-010 pairs."""
    return [
        FROZEN_OD010_SERIES[name]["official_series_identifier"]
        for name in ("health_oop", "insurance", "maintenance", "recreation", "essentials")
    ]


def retrieve_bls_cpi_series(
    series_ids: list[str] | None = None,
    *,
    start_year: int = 2023,
    end_year: int | None = None,
    timeout: float = 40.0,
) -> dict[str, Any]:
    """POST official BLS public API. Returns parsed JSON plus byte identity."""
    if series_ids is None:
        series_ids = required_od010_series_ids()
    if end_year is None:
        end_year = datetime.now(UTC).year
    payload = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
        "annualaverage": True,
    }
    response = requests.post(
        BLS_V2_URL,
        json=payload,
        headers=_BROWSER_HEADERS,
        timeout=timeout,
    )
    raw = response.content
    retrieved_at = _now_iso()
    if response.status_code != 200 or not raw:
        raise RuntimeError(f"BLS API HTTP {response.status_code} empty={not raw} url={BLS_V2_URL}")
    data = json.loads(raw.decode("utf-8"))
    if data.get("status") != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS API status={data.get('status')} message={data.get('message')}")
    raw_sha = hashlib.sha256(raw).hexdigest()
    return {
        "http_status": response.status_code,
        "retrieved_at": retrieved_at,
        "request_url": BLS_V2_URL,
        "request_payload": payload,
        "byte_size": len(raw),
        "sha256": raw_sha,
        "raw_response_sha256": raw_sha,
        "observation_set_sha256": compute_observation_set_sha256(data),
        "body": data,
    }


def _obs_sort_key(obs: dict[str, Any]) -> tuple[int, str]:
    return (int(obs.get("year", 0)), str(obs.get("period", "")))


def observations_by_series(body: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for series in (body.get("Results") or {}).get("series") or []:
        sid = series.get("seriesID")
        if not isinstance(sid, str):
            continue
        rows = []
        for item in series.get("data") or []:
            if not isinstance(item, dict):
                continue
            value = item.get("value")
            if value in {None, "", "-"}:
                continue
            try:
                float(value)
            except (TypeError, ValueError):
                continue
            rows.append(item)
        rows.sort(key=_obs_sort_key)
        out[sid] = rows
    return out


def annual_average(rows: list[dict[str, Any]], year: int) -> dict[str, Any] | None:
    for item in rows:
        if int(item.get("year", 0)) == year and item.get("period") == "M13":
            return item
    return None


def latest_monthly(rows: list[dict[str, Any]], year: int) -> dict[str, Any] | None:
    monthly = [
        item
        for item in rows
        if int(item.get("year", 0)) == year
        and str(item.get("period", "")).startswith("M")
        and item.get("period") != "M13"
    ]
    return monthly[-1] if monthly else None


def period_label(obs: dict[str, Any] | None) -> str | None:
    if not obs:
        return None
    year = obs.get("year")
    period = obs.get("period")
    name = obs.get("periodName")
    if period == "M13":
        return f"{year} annual"
    if name:
        return f"{year} {name}"
    return f"{year} {period}"


def index_value(obs: dict[str, Any] | None) -> Decimal | None:
    if not obs:
        return None
    try:
        return Decimal(str(obs["value"]).strip())
    except (InvalidOperation, ArithmeticError, ValueError, TypeError, KeyError):
        return None


def select_target_observation(
    rows: list[dict[str, Any]], project_cost_year: int
) -> dict[str, Any] | None:
    """2024 uses official annual average. 2026 uses newest available 2026 monthly."""
    if project_cost_year < 2026:
        return annual_average(rows, project_cost_year)
    return latest_monthly(rows, project_cost_year) or annual_average(rows, project_cost_year)


def _canonical_observation(series_id: str, obs: dict[str, Any]) -> dict[str, str]:
    return {
        "seriesID": str(series_id),
        "year": str(obs.get("year", "")),
        "period": str(obs.get("period", "")),
        "periodName": str(obs.get("periodName") or ""),
        "value": str(obs.get("value", "")).strip(),
    }


def selected_canonical_observations(
    by_series: dict[str, list[dict[str, Any]]],
    *,
    source_years: dict[str, int] | None = None,
) -> list[dict[str, str]]:
    """Observations needed for the seven frozen CPI_UPDATED pairs.

    Includes each pair's base observation, selected target observation, and
    the newest applicable target-year observation. Volatile API metadata is
    excluded.
    """
    source_years = source_years or DEFAULT_SOURCE_DATA_YEAR
    seen: dict[tuple[str, str, str], dict[str, str]] = {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        sid = FROZEN_OD010_SERIES[component]["official_series_identifier"]
        rows = by_series.get(sid) or []
        base_obs = annual_average(rows, source_years[component])
        target_obs = select_target_observation(rows, year)
        latest_target_year = latest_monthly(rows, year) or annual_average(rows, year)
        for obs in (base_obs, target_obs, latest_target_year):
            if not obs:
                continue
            rec = _canonical_observation(sid, obs)
            key = (rec["seriesID"], rec["year"], rec["period"])
            seen[key] = rec
    return [seen[key] for key in sorted(seen)]


def compute_observation_set_sha256(
    body: dict[str, Any],
    *,
    source_years: dict[str, int] | None = None,
) -> str:
    observations = selected_canonical_observations(
        observations_by_series(body), source_years=source_years
    )
    encoded = json.dumps(observations, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def period_tuple_from_obs(obs: dict[str, Any] | None) -> tuple[int, str] | None:
    if not obs:
        return None
    try:
        year = int(obs.get("year", 0))
    except (TypeError, ValueError):
        return None
    period = str(obs.get("period") or "")
    if not period:
        return None
    return (year, period)


def period_tuple_from_label(label: str | None) -> tuple[int, str] | None:
    if not label:
        return None
    text = str(label).strip()
    if not text:
        return None
    parts = text.split()
    try:
        year = int(parts[0])
    except (ValueError, IndexError):
        return None
    if len(parts) == 1:
        return None
    rest = " ".join(parts[1:]).strip().lower()
    if rest in _MONTH_PERIOD:
        return (year, _MONTH_PERIOD[rest])
    if rest.startswith("m") and len(rest) <= 3:
        return (year, rest.upper())
    return None


def target_observation_is_newer(
    live_obs: dict[str, Any] | None, table_period_label: str | None
) -> bool:
    live_key = period_tuple_from_obs(live_obs)
    table_key = period_tuple_from_label(table_period_label)
    if live_key is None or table_key is None:
        return False
    return live_key > table_key


def build_od010_records(
    retrieve: dict[str, Any],
    *,
    source_years: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a real translation table from an official BLS retrieve payload."""
    source_years = source_years or DEFAULT_SOURCE_DATA_YEAR
    by_series = observations_by_series(retrieve["body"])
    raw_sha = str(retrieve.get("raw_response_sha256") or retrieve["sha256"])
    obs_sha = retrieve.get("observation_set_sha256")
    if not obs_sha:
        obs_sha = compute_observation_set_sha256(retrieve["body"], source_years=source_years)
    series_rows: list[dict[str, Any]] = []
    coverage: dict[str, dict[str, dict[str, Any]]] = {}
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        meta = FROZEN_OD010_SERIES[component]
        sid = meta["official_series_identifier"]
        rows = by_series.get(sid) or []
        source_year = source_years[component]
        base_obs = annual_average(rows, source_year)
        target_obs = select_target_observation(rows, year)
        base_val = index_value(base_obs)
        target_val = index_value(target_obs)
        factor = recompute_cpi_updated_factor(base_val, target_val)
        covered = (
            base_obs is not None
            and target_obs is not None
            and base_val is not None
            and target_val is not None
            and factor is not None
        )
        calc = {
            "base_observation_period": period_label(base_obs),
            "base_index_value": None if base_val is None else format(base_val, "f"),
            "target_observation_period": period_label(target_obs),
            "target_index_value": None if target_val is None else format(target_val, "f"),
            "translation_factor": None if factor is None else format(factor, "f"),
            "official_series_identifier": sid,
            "source_artifact": BLS_API_IDENTITY,
            "sha256": obs_sha,
            "raw_response_sha256": raw_sha,
            "observation_set_sha256": obs_sha,
        }
        rec = {
            "component": component,
            "project_cost_year": year,
            "source_data_year": source_year,
            "official_series_identifier": sid,
            "publisher": "BLS",
            "observation_period": period_label(target_obs),
            "source_artifact": BLS_API_IDENTITY,
            "sha256": obs_sha,
            "raw_response_sha256": raw_sha,
            "observation_set_sha256": obs_sha,
            "translation_factor": None if factor is None else float(factor),
            "retrieval_validation_state": "VALIDATED" if covered else "RETRIEVED_UNVALIDATED",
            "calculation_inputs": calc,
            "item": meta["item"],
            "rationale": meta["rationale"],
            "disclosure": meta["disclosure"],
            "landing_url": meta["landing_url"],
        }
        series_rows.append(rec)
        coverage.setdefault(component, {})[str(year)] = {
            "covered": covered,
            "official_series_identifier": sid,
            "publisher": "BLS",
            "latest_observation_period": period_label(target_obs),
            "target_observation_period": period_label(target_obs),
            "base_observation_period": period_label(base_obs),
            "source_data_year": source_year,
            "selected_artifact": BLS_API_IDENTITY,
            "api_identity": BLS_API_IDENTITY,
            "sha256": obs_sha,
            "raw_response_sha256": raw_sha,
            "observation_set_sha256": obs_sha,
            "target_period": None if target_obs is None else target_obs.get("period"),
            "target_year": None if target_obs is None else target_obs.get("year"),
            "base_index_value": None if base_val is None else format(base_val, "f"),
            "target_index_value": None if target_val is None else format(target_val, "f"),
        }
    all_covered = all(
        coverage[component][str(year)]["covered"] for component, year in FROZEN_CPI_UPDATED_PAIRS
    )
    return {
        "report_type": "living_cost_od010_translation_table",
        "generated_at": retrieve["retrieved_at"],
        "publisher": "BLS",
        "landing_url": BLS_CPI_LANDING,
        "api_identity": BLS_API_IDENTITY,
        "retrieve_sha256": raw_sha,
        "raw_response_sha256": raw_sha,
        "observation_set_sha256": obs_sha,
        "retrieve_byte_size": retrieve["byte_size"],
        "bound": all_covered,
        "currentness_status": "CURRENT" if all_covered else "INCOMPLETE",
        "series": series_rows,
        "series_coverage": coverage,
        "calculates_mslc": False,
    }


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp.replace(path)


def archive_od010_table(path: Path | None = None) -> Path | None:
    """Preserve the prior canonical table under an immutable archival name."""
    source = path or OD010_TABLE
    if not source.exists():
        return None
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()[:16]
    generated = "unknown"
    try:
        payload = json.loads(raw.decode("utf-8"))
        stamp = str(payload.get("generated_at") or "").strip()
        if stamp:
            generated = stamp.replace(":", "").replace("+", "").replace(".", "").replace(" ", "T")
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
        generated = "unreadable"
    OD010_TABLE_HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    dest = (
        OD010_TABLE_HISTORY_DIR / f"living_cost_od010_translation_table_{generated}_{digest}.json"
    )
    dest.write_bytes(raw)
    return dest


def write_od010_retrieve(retrieve: dict[str, Any]) -> None:
    persist = {
        "report_type": "living_cost_od010_bls_retrieve",
        "retrieved_at": retrieve["retrieved_at"],
        "http_status": retrieve.get("http_status"),
        "request_url": retrieve.get("request_url"),
        "request_payload": retrieve.get("request_payload"),
        "byte_size": retrieve["byte_size"],
        "sha256": retrieve.get("raw_response_sha256") or retrieve["sha256"],
        "raw_response_sha256": retrieve.get("raw_response_sha256") or retrieve["sha256"],
        "observation_set_sha256": retrieve.get("observation_set_sha256")
        or compute_observation_set_sha256(retrieve["body"]),
        "body": retrieve["body"],
    }
    _atomic_write_json(OD010_RETRIEVE, persist)


def write_od010_artifacts(retrieve: dict[str, Any], table: dict[str, Any]) -> None:
    """Persist retrieve bytes and the canonical current table.

    A prior bound table is archived. The canonical file is always rewritten so
    a newly retrieved incomplete/obsolete inventory cannot leave a stale
    bound pointer in place.
    """
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    write_od010_retrieve(retrieve)
    if OD010_TABLE.exists():
        archive_od010_table(OD010_TABLE)
    payload = dict(table)
    if payload.get("bound") is not True:
        payload["bound"] = False
        payload.setdefault("currentness_status", "INCOMPLETE")
    _atomic_write_json(OD010_TABLE, payload)


def write_od010_live_currentness(payload: dict[str, Any]) -> None:
    record = dict(payload)
    record.setdefault("report_type", "living_cost_od010_live_currentness")
    record.setdefault("generated_at", _now_iso())
    record["calculates_mslc"] = False
    _atomic_write_json(OD010_LIVE_CURRENTNESS, record)


def load_od010_live_currentness() -> dict[str, Any] | None:
    if not OD010_LIVE_CURRENTNESS.exists():
        return None
    try:
        payload = json.loads(OD010_LIVE_CURRENTNESS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def live_currentness_unbinds_table() -> bool:
    """True when a live official check has invalidated the canonical table."""
    payload = load_od010_live_currentness()
    if not payload:
        return False
    status = payload.get("freshness_check_status") or payload.get("currentness_status")
    if status in INVALIDATING_CURRENTNESS:
        return True
    return payload.get("translation_index_bound") is False and status == "NEWER_AVAILABLE"


def load_retrieved_series_coverage() -> dict[str, Any] | None:
    if not OD010_TABLE.exists():
        return None
    try:
        payload = json.loads(OD010_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    coverage = payload.get("series_coverage")
    return coverage if isinstance(coverage, dict) else None


def load_od010_table() -> dict[str, Any] | None:
    if not OD010_TABLE.exists():
        return None
    try:
        payload = json.loads(OD010_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def persisted_table_matches_live(
    persisted: dict[str, Any] | None, live_table: dict[str, Any]
) -> tuple[bool, list[str]]:
    """Compare persisted table to an ephemeral live inventory (observation identity)."""
    issues: list[str] = []
    if not isinstance(persisted, dict):
        return False, ["OD010_TABLE_ABSENT"]
    live_obs = live_table.get("observation_set_sha256")
    table_obs = persisted.get("observation_set_sha256")
    if table_obs and live_obs and table_obs != live_obs:
        issues.append("OBSERVATION_IDENTITY_MISMATCH")
    live_cov = live_table.get("series_coverage") or {}
    table_cov = persisted.get("series_coverage") or {}
    newer = False
    for component, year in FROZEN_CPI_UPDATED_PAIRS:
        live_slot = (live_cov.get(component) or {}).get(str(year)) or {}
        table_slot = (table_cov.get(component) or {}).get(str(year)) or {}
        if live_slot.get("official_series_identifier") != table_slot.get(
            "official_series_identifier"
        ):
            issues.append(f"{component}:{year}:SERIES_MISMATCH")
        if live_slot.get("source_data_year") != table_slot.get("source_data_year"):
            issues.append(f"{component}:{year}:SOURCE_YEAR_MISMATCH")
        if live_slot.get("base_observation_period") != table_slot.get("base_observation_period"):
            issues.append(f"{component}:{year}:BASE_PERIOD_MISMATCH")
        if live_slot.get("target_observation_period") != table_slot.get(
            "target_observation_period"
        ):
            issues.append(f"{component}:{year}:TARGET_PERIOD_MISMATCH")
        if live_slot.get("base_index_value") != table_slot.get("base_index_value"):
            issues.append(f"{component}:{year}:BASE_VALUE_MISMATCH")
        if live_slot.get("target_index_value") != table_slot.get("target_index_value"):
            issues.append(f"{component}:{year}:TARGET_VALUE_MISMATCH")
        live_period = live_slot.get("target_observation_period")
        table_period = table_slot.get("target_observation_period")
        live_key = period_tuple_from_label(str(live_period) if live_period else None)
        table_key = period_tuple_from_label(str(table_period) if table_period else None)
        if live_key and table_key and live_key > table_key:
            newer = True
            issues.append(f"{component}:{year}:NEWER_TARGET_AVAILABLE")
    return (not issues and not newer), issues
