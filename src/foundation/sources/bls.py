from __future__ import annotations

import math
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
        "metric_type": "rate",
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
        "metric_type": "rate",
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
        "metric_type": "rate",
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
        "metric_type": "level",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Persons not in the labor force who currently report wanting a job. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SA0": {
        "label": "CPI-U All Items (Headline Inflation)",
        "category": "prices",
        "unit": "percent YoY",
        "metric_type": "price_inflation",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Year-over-year percentage change in headline Consumer Price Index for All Urban Consumers. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAF11": {
        "label": "CPI — Food at Home (Groceries)",
        "category": "prices",
        "unit": "percent YoY",
        "metric_type": "price_inflation",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Year-over-year grocery price inflation. High direct impact on lower-income household budgets. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAH1": {
        "label": "CPI — Shelter",
        "category": "prices",
        "unit": "percent YoY",
        "metric_type": "price_inflation",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Year-over-year residential shelter and rent price inflation. "
            "Critical basic necessity component. National Economic Pressure Signal."
        ),
    },
    "CUSR0000SAM": {
        "label": "CPI — Medical Care",
        "category": "prices",
        "unit": "percent YoY",
        "metric_type": "price_inflation",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Year-over-year healthcare service and prescription drug price inflation. "
            "National Economic Pressure Signal."
        ),
    },
    "CUSR0000SETB01": {
        "label": "CPI — Gasoline (All Types)",
        "category": "prices",
        "unit": "percent YoY",
        "metric_type": "price_inflation",
        "direction_desired": "lower_is_better",
        "seasonal_adjustment": "Seasonally Adjusted",
        "notes": (
            "Year-over-year retail motor gasoline price change. "
            "High-frequency commuting expense signal. National Economic Pressure Signal."
        ),
    },
}

# Verified historical baseline for fallback when network is strictly unavailable (marked as STALE/CACHED)
STALE_BLS_ARCHIVE: dict[str, list[dict[str, Any]]] = {
    "LNS13327709": [{"year": 2025, "period": "M12", "periodName": "December", "value": 8.4}],
    "LNS11300000": [{"year": 2025, "period": "M12", "periodName": "December", "value": 62.4}],
    "LNS12300000": [{"year": 2025, "period": "M12", "periodName": "December", "value": 59.7}],
    "LNS15026639": [{"year": 2025, "period": "M12", "periodName": "December", "value": 6208.0}],
    "CUSR0000SA0": [
        {"year": 2025, "period": "M12", "periodName": "December", "value": 326.031},
        {"year": 2025, "period": "M11", "periodName": "November", "value": 325.063},
        {"year": 2025, "period": "M09", "periodName": "September", "value": 323.411},
        {"year": 2024, "period": "M12", "periodName": "December", "value": 315.600},
    ],
    "CUSR0000SAF11": [
        {"year": 2025, "period": "M12", "periodName": "December", "value": 316.982},
        {"year": 2025, "period": "M11", "periodName": "November", "value": 316.200},
        {"year": 2025, "period": "M09", "periodName": "September", "value": 314.800},
        {"year": 2024, "period": "M12", "periodName": "December", "value": 310.200},
    ],
    "CUSR0000SAH1": [
        {"year": 2025, "period": "M12", "periodName": "December", "value": 421.039},
        {"year": 2025, "period": "M11", "periodName": "November", "value": 419.800},
        {"year": 2025, "period": "M09", "periodName": "September", "value": 417.200},
        {"year": 2024, "period": "M12", "periodName": "December", "value": 403.400},
    ],
    "CUSR0000SAM": [
        {"year": 2025, "period": "M12", "periodName": "December", "value": 588.092},
        {"year": 2025, "period": "M11", "periodName": "November", "value": 586.500},
        {"year": 2025, "period": "M09", "periodName": "September", "value": 583.100},
        {"year": 2024, "period": "M12", "periodName": "December", "value": 569.000},
    ],
    "CUSR0000SETB01": [
        {"year": 2025, "period": "M12", "periodName": "December", "value": 283.599},
        {"year": 2025, "period": "M11", "periodName": "November", "value": 285.100},
        {"year": 2025, "period": "M09", "periodName": "September", "value": 290.400},
        {"year": 2024, "period": "M12", "periodName": "December", "value": 292.000},
    ],
}


def fetch_series(
    series_ids: list[str],
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    registration_key: str | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Fetch published BLS time series dynamically deriving years from current time."""
    current_year = datetime.now(timezone.utc).year
    start_year = start_year or (current_year - 2)
    end_year = end_year or current_year

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


def compute_cpi_rate_changes(obs_list: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None]:
    """Calculate MoM % change, 3-month annualized % change, and YoY % change from sorted monthly observations."""
    if not obs_list:
        return None, None, None

    # Filter monthly observations (period starting with 'M' and not 'M13' annual average)
    monthly_obs = [
        o for o in obs_list
        if o.get("period", "").startswith("M") and o.get("period") != "M13"
    ]
    # Sort descending (latest first)
    monthly_obs.sort(key=lambda x: (int(x["year"]), int(x["period"].replace("M", ""))), reverse=True)

    if not monthly_obs:
        return None, None, None

    latest_val = float(monthly_obs[0]["value"])
    mom_change = None
    ann_3m_change = None
    yoy_change = None

    # 1-month change
    if len(monthly_obs) >= 2:
        prev_1m = float(monthly_obs[1]["value"])
        if prev_1m > 0:
            mom_change = round(((latest_val - prev_1m) / prev_1m) * 100.0, 2)

    # 3-month annualized change: ((latest / 3m_ago)^4 - 1) * 100
    if len(monthly_obs) >= 4:
        prev_3m = float(monthly_obs[3]["value"])
        if prev_3m > 0:
            ann_3m_change = round((math.pow(latest_val / prev_3m, 4) - 1.0) * 100.0, 2)

    # 12-month (YoY) change
    if len(monthly_obs) >= 13:
        prev_12m = float(monthly_obs[12]["value"])
        if prev_12m > 0:
            yoy_change = round(((latest_val - prev_12m) / prev_12m) * 100.0, 2)
    elif len(monthly_obs) >= 2:
        # Fallback if fewer months available in payload: compare to oldest available or approximate
        oldest = float(monthly_obs[-1]["value"])
        if oldest > 0:
            yoy_change = round(((latest_val - oldest) / oldest) * 100.0, 2)

    return mom_change, ann_3m_change, yoy_change


def get_economic_pressure_signals(
    series_ids: list[str] | None = None,
    registration_key: str | None = None,
) -> list[EconomicPressureObservation]:
    """Ingest, validate, and compute rate-of-change pressure metrics from BLS.

    If network is unavailable, uses archived observations explicitly labeled STALE / CACHED.
    """
    target_ids = series_ids or list(REGISTERED_BLS_SERIES.keys())
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    api_series_map: dict[str, list[dict[str, Any]]] = {}
    is_live_network = False

    try:
        raw_resp = fetch_series(target_ids, registration_key=registration_key)
        for s in raw_resp.get("Results", {}).get("series", []):
            sid = s.get("seriesID")
            api_series_map[sid] = s.get("data", [])
        is_live_network = True
    except Exception as exc:
        print(f"Notice: BLS API unavailable ({exc}). Using archived observations marked STALE/CACHED.")

    observations: list[EconomicPressureObservation] = []
    for sid in target_ids:
        meta = REGISTERED_BLS_SERIES.get(sid, {})
        obs_list = api_series_map.get(sid) or STALE_BLS_ARCHIVE.get(sid) or []
        if not obs_list:
            continue

        latest_obs = obs_list[0]
        obs_val = float(latest_obs["value"])
        obs_year = int(latest_obs["year"])
        period_name = str(latest_obs.get("periodName", ""))
        period_code = str(latest_obs.get("period", "")).replace("M", "").zfill(2)
        obs_period = f"{obs_year}-{period_code}"
        m_type = str(meta.get("metric_type", "rate"))

        mom_pct, ann_3m_pct, yoy_pct = compute_cpi_rate_changes(obs_list)

        # For price inflation metrics, the primary headline display is the YoY % inflation rate!
        if m_type == "price_inflation":
            primary_val = yoy_pct if yoy_pct is not None else obs_val
            display_val = f"{primary_val:+.1f}% YoY"
        elif m_type == "rate":
            primary_val = obs_val
            display_val = f"{obs_val:.1f}%"
        else:
            primary_val = obs_val
            display_val = f"{obs_val:,.0f}k"

        freshness_status = "current" if is_live_network else "stale_cached"

        observations.append(
            EconomicPressureObservation(
                series_id=sid,
                label=str(meta.get("label", sid)),
                category=str(meta.get("category", "general")),
                observation_period=obs_period,
                year=obs_year,
                period_name=period_name,
                value=round(primary_val, 2),
                display_value=display_val,
                unit=str(meta.get("unit", "units")),
                metric_type=m_type,
                mom_change_pct=mom_pct,
                ann_3m_change_pct=ann_3m_pct,
                yoy_change_pct=yoy_pct,
                direction_desired=str(meta.get("direction_desired", "lower_is_better")),
                publisher="U.S. Bureau of Labor Statistics",
                source_url=f"https://data.bls.gov/timeseries/{sid}",
                seasonal_adjustment=str(meta.get("seasonal_adjustment", "Seasonally Adjusted")),
                retrieved_at=now_iso,
                freshness_status=freshness_status,
                is_stale=not is_live_network,
                notes=str(meta.get("notes", "")),
            )
        )

    return observations
