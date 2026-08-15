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


def retrieve_bls_cpi_series(
    series_ids: list[str],
    *,
    start_year: int = 2023,
    end_year: int | None = None,
    timeout: float = 40.0,
) -> dict[str, Any]:
    """POST official BLS public API. Returns parsed JSON plus byte identity."""
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
    return {
        "http_status": response.status_code,
        "retrieved_at": retrieved_at,
        "request_url": BLS_V2_URL,
        "request_payload": payload,
        "byte_size": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
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


def build_od010_records(
    retrieve: dict[str, Any],
    *,
    source_years: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Build a real translation table from an official BLS retrieve payload."""
    source_years = source_years or DEFAULT_SOURCE_DATA_YEAR
    by_series = observations_by_series(retrieve["body"])
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
            "sha256": retrieve["sha256"],
        }
        rec = {
            "component": component,
            "project_cost_year": year,
            "source_data_year": source_year,
            "official_series_identifier": sid,
            "publisher": "BLS",
            "observation_period": period_label(target_obs),
            "source_artifact": BLS_API_IDENTITY,
            "sha256": retrieve["sha256"],
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
            "sha256": retrieve["sha256"],
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
        "retrieve_sha256": retrieve["sha256"],
        "retrieve_byte_size": retrieve["byte_size"],
        "bound": all_covered,
        "series": series_rows,
        "series_coverage": coverage,
        "calculates_mslc": False,
    }


def write_od010_artifacts(retrieve: dict[str, Any], table: dict[str, Any]) -> None:
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    persist = {
        "report_type": "living_cost_od010_bls_retrieve",
        "retrieved_at": retrieve["retrieved_at"],
        "http_status": retrieve["http_status"],
        "request_url": retrieve["request_url"],
        "request_payload": retrieve["request_payload"],
        "byte_size": retrieve["byte_size"],
        "sha256": retrieve["sha256"],
        "body": retrieve["body"],
    }
    OD010_RETRIEVE.write_text(json.dumps(persist, indent=2), encoding="utf-8")
    if table.get("bound") is True:
        OD010_TABLE.write_text(json.dumps(table, indent=2), encoding="utf-8")
    elif OD010_TABLE.exists():
        # Do not leave a stale fake-bound table.
        pass


def load_retrieved_series_coverage() -> dict[str, Any] | None:
    if not OD010_TABLE.exists():
        return None
    try:
        payload = json.loads(OD010_TABLE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    coverage = payload.get("series_coverage")
    return coverage if isinstance(coverage, dict) else None
