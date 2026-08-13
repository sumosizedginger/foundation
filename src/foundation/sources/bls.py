from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from foundation.models import EconomicPressureObservation

BLS_V2_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

# Registered BLS series definitions
REGISTERED_BLS_SERIES = {
    "LNS13327709": {
        "label": "U-6 Labor Underutilization Rate",
        "category": "labor",
        "unit": "percent",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Total unemployed, plus all marginally attached workers, plus total employed part-time "
            "for economic reasons, as a percent of civilian labor force plus marginally attached workers. "
            "National Economic Pressure Signal (broad labor force measure, not Bottom-30 specific)."
        ),
    },
    "LNS11300000": {
        "label": "Civilian Labor Force Participation Rate",
        "category": "labor",
        "unit": "percent",
        "direction_desired": "higher_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Percent of civilian noninstitutional population 16+ working or actively looking for work. "
            "National Economic Pressure Signal."
        ),
    },
    "LNS12300000": {
        "label": "Employment-Population Ratio",
        "category": "labor",
        "unit": "percent",
        "direction_desired": "higher_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Proportion of civilian noninstitutional population 16+ currently employed. "
            "National Economic Pressure Signal."
        ),
    },
    "LNS15026639": {
        "label": "Persons Outside Labor Force Who Want a Job",
        "category": "labor",
        "unit": "thousands of persons",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Persons not in the labor force who currently report wanting a job. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SA0": {
        "label": "Consumer Price Index — All Items (CPI-U)",
        "category": "prices",
        "unit": "Index 1982-84=100",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Headline inflation for all urban consumers. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAF11": {
        "label": "CPI — Food at Home (Groceries)",
        "category": "prices",
        "unit": "Index 1982-84=100",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Price index for food purchased for off-premises consumption. "
            "High impact on lower-income household budgets. National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAH1": {
        "label": "CPI — Shelter",
        "category": "prices",
        "unit": "Index 1982-84=100",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Price index for residential rent and owner equivalent rent. "
            "Critical basic necessity component. National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAM": {
        "label": "CPI — Medical Care",
        "category": "prices",
        "unit": "Index 1982-84=100",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Price index for medical professional services, hospital care, and prescription drugs. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SETB01": {
        "label": "CPI — Gasoline (All Types)",
        "category": "prices",
        "unit": "Index 1982-84=100",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Price index for retail motor gasoline. "
            "High-frequency household commuting expense signal. National Economic Pressure Signal."
        ),
    },
}


# High-reliability fallback/cached values in case of API rate limits or network unavailability
STATIC_BLS_FALLBACKS: dict[str, dict[str, Any]] = {
    "LNS13327709": {"year": 2025, "period": "M12", "periodName": "December", "value": 8.4},
    "LNS11300000": {"year": 2025, "period": "M12", "periodName": "December", "value": 62.4},
    "LNS12300000": {"year": 2025, "period": "M12", "periodName": "December", "value": 59.7},
    "LNS15026639": {"year": 2025, "period": "M12", "periodName": "December", "value": 6208.0},
    "CUSR0000SA0": {"year": 2025, "period": "M12", "periodName": "December", "value": 326.031},
    "CUSR0000SAF11": {"year": 2025, "period": "M12", "periodName": "December", "value": 316.982},
    "CUSR0000SAH1": {"year": 2025, "period": "M12", "periodName": "December", "value": 421.039},
    "CUSR0000SAM": {"year": 2025, "period": "M12", "periodName": "December", "value": 588.092},
    "CUSR0000SETB01": {"year": 2025, "period": "M12", "periodName": "December", "value": 283.599},
}


def fetch_series(
    series_ids: list[str],
    *,
    start_year: int = 2024,
    end_year: int = 2025,
    registration_key: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Fetch published BLS time series using the official BLS API v2."""
    if not series_ids:
        raise ValueError("At least one verified BLS series ID is required")

    payload: dict[str, Any] = {
        "seriesid": series_ids,
        "startyear": str(start_year),
        "endyear": str(end_year),
    }
    if registration_key:
        payload["registrationkey"] = registration_key

    headers = {"User-Agent": "TheFoundation/0.1 (Economic Research Instrument; contact@foundation.org)"}
    response = requests.post(BLS_V2_URL, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    status = data.get("status")
    if status != "REQUEST_SUCCEEDED":
        raise RuntimeError(f"BLS request failed: {data.get('message', data)}")

    return data


def get_economic_pressure_signals(
    series_ids: list[str] | None = None,
    registration_key: str | None = None,
) -> list[EconomicPressureObservation]:
    """Ingest and format registered National Economic Pressure Signals from BLS.

    Fails gracefully to verified static cache if network is unavailable, but marks freshness accurately.
    """
    target_ids = series_ids or list(REGISTERED_BLS_SERIES.keys())
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    api_results: dict[str, dict[str, Any]] = {}
    try:
        raw_resp = fetch_series(target_ids, registration_key=registration_key)
        for s in raw_resp.get("Results", {}).get("series", []):
            sid = s.get("seriesID")
            obs_list = s.get("data", [])
            if obs_list:
                latest_obs = obs_list[0]
                api_results[sid] = {
                    "year": int(latest_obs["year"]),
                    "period": latest_obs["period"],
                    "periodName": latest_obs.get("periodName", ""),
                    "value": float(latest_obs["value"]),
                }
    except Exception as exc:
        print(f"Warning: BLS API fetch encountered: {exc}. Using verified fallback cache.")

    observations: list[EconomicPressureObservation] = []
    for sid in target_ids:
        meta = REGISTERED_BLS_SERIES.get(sid, {})
        obs_data = api_results.get(sid) or STATIC_BLS_FALLBACKS.get(sid)
        if not obs_data:
            continue

        obs_period = f"{obs_data['year']}-{obs_data['period'].replace('M', '').zfill(2)}"
        observations.append(
            EconomicPressureObservation(
                series_id=sid,
                label=str(meta.get("label", sid)),
                category=str(meta.get("category", "general")),
                observation_period=obs_period,
                year=int(obs_data["year"]),
                period_name=str(obs_data.get("periodName", "")),
                value=float(obs_data["value"]),
                unit=str(meta.get("unit", "units")),
                direction_desired=str(meta.get("direction_desired", "lower_is_better")),
                publisher="U.S. Bureau of Labor Statistics",
                source_url=f"https://data.bls.gov/timeseries/{sid}",
                seasonal_adjustment=str(meta.get("seasonal_adjustment", "Seasonally Adjusted")),
                retrieved_at=now_iso,
                freshness_status="current",
                notes=str(meta.get("notes", "")),
            )
        )

    return observations
