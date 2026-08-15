"""Source-specific freshness discovery for a future PRIVATE candidate.

Does not calculate or publish an MSLC. Each family has its own check against
an official landing/listing page. A timestamp is recorded only after that
check runs. newer_data_exists is None when currentness was not established.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests

from foundation.living_cost.freshness import FreshnessCheck
from foundation.living_cost.manifest import (
    ACS_LANDING,
    BEA_RPP_LANDING,
    BLS_CE_LANDING,
    CMS_PUF_LANDING,
    EIA_GAS_LANDING,
    HUD_FMR_LANDING,
    NAIC_LANDING,
    NHTS_LANDING,
    USDA_FOOD_LANDING,
)
from foundation.sources.epa_mpg import EPA_FUELEconomy_LANDING
from foundation.sources.fcc_urs import FCC_URS_LANDING
from foundation.sources.meps import (
    MEPS_DATA_YEAR,
    MEPS_LISTING_URL,
    MEPS_PUF_ID,
    check_meps_2024_full_year_listing,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CACHE_DIR = PROJECT_ROOT / "data" / "cache"
METADATA_DIR = PROJECT_ROOT / "data" / "metadata"

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; The-Foundation/0.2; "
        "+https://github.com/sumosizedginger/foundation)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_text(url: str, *, timeout: tuple[float, float] = (12.0, 40.0)) -> tuple[str, str]:
    """GET an official page. Returns (text, retrieved_at). Raises on failure."""
    response = requests.get(
        url,
        timeout=timeout,
        headers=_BROWSER_HEADERS,
        allow_redirects=True,
    )
    response.raise_for_status()
    text = response.text or ""
    if not text.strip():
        raise RuntimeError(f"empty body from {url}")
    return text, _now_iso()


def _sidecar(filename: str) -> dict[str, Any] | None:
    path = CACHE_DIR / f"{filename}.provenance.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _coverage_artifacts() -> list[dict[str, Any]]:
    path = METADATA_DIR / "living_cost_source_coverage.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    arts = payload.get("retrieved_artifacts") or []
    return [a for a in arts if isinstance(a, dict)]


def _artifact_record(
    *,
    artifact_id: str,
    url: str | None = None,
    sha256: str | None = None,
    retrieved_at: str | None = None,
    validation_status: str | None = None,
    filename: str | None = None,
) -> dict[str, Any]:
    return {
        "artifact_id": artifact_id,
        "filename": filename or artifact_id,
        "url": url,
        "sha256": sha256,
        "retrieved_at": retrieved_at,
        "validation_status": validation_status,
    }


def _failed(
    source_id: str,
    *,
    publisher: str,
    landing_url: str,
    evidence: str,
    reason: str,
    vintage: str | None = None,
    artifact: str | None = None,
    artifacts: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> FreshnessCheck:
    return FreshnessCheck(
        source_id=source_id,
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=vintage,
        selected_vintage=vintage,
        selected_artifact=artifact,
        newer_data_exists=None,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status="CHECK_FAILED",
        publisher=publisher,
        landing_url=landing_url,
        selected_artifacts=tuple(artifacts or ()),
        transformation_method=None,
        input_evidence_status=evidence,
        extra=extra,
    )


def _gap(
    source_id: str,
    *,
    publisher: str,
    landing_url: str | None,
    evidence: str,
    reason: str,
) -> FreshnessCheck:
    return FreshnessCheck(
        source_id=source_id,
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=None,
        selected_vintage=None,
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status="SOURCE_GAP",
        publisher=publisher,
        landing_url=landing_url,
        selected_artifacts=(),
        transformation_method=None,
        input_evidence_status=evidence,
    )


def discover_acs() -> FreshnessCheck:
    listing = "https://www2.census.gov/programs-surveys/acs/summary_file/"
    sidecar = _sidecar("acsdt5y2024-b01001.dat")
    selected = _artifact_record(
        artifact_id="acsdt5y2024-b01001.dat",
        url=ACS_LANDING,
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED",
    )
    try:
        html, checked = fetch_text(listing)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "acs_population_weights",
            publisher="U.S. Census Bureau",
            landing_url=listing,
            evidence="VALIDATED",
            vintage="2024 ACS 5-Year B01001",
            artifact="acsdt5y2024-b01001.dat",
            artifacts=[selected],
            reason=f"ACS summary_file listing could not be retrieved: {exc}",
        )
    years = {int(y) for y in re.findall(r"href=['\"]?(20[0-9]{2})/['\"]?", html)}
    years.update(int(y) for y in re.findall(r"summary_file/(20[0-9]{2})/", html))
    newest = max(years) if years else None
    has_2024 = 2024 in years or "acsdt5y2024" in html or "2024/" in html
    newer = newest is not None and newest > 2024
    if not has_2024 and newest is None:
        return _failed(
            "acs_population_weights",
            publisher="U.S. Census Bureau",
            landing_url=listing,
            evidence="VALIDATED",
            vintage="2024 ACS 5-Year B01001",
            artifact="acsdt5y2024-b01001.dat",
            artifacts=[selected],
            reason="ACS listing retrieved but no year folders could be parsed.",
        )
    status = "NEWER_AVAILABLE" if newer else "VERIFIED_CURRENT"
    vintage = f"ACS 5-Year listing years={sorted(years)}; selected 2024 B01001"
    return FreshnessCheck(
        source_id="acs_population_weights",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=str(newest) if newest else "2024",
        selected_vintage="2024 ACS 5-Year B01001",
        selected_artifact="acsdt5y2024-b01001.dat",
        newer_data_exists=newer,
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            f"Official ACS summary_file listing checked at {listing}. {vintage}. "
            "Selected county adult weights remain 2024 ACS 5-Year B01001. "
            "Do not relabel 2024 as a later year."
        ),
        freshness_check_status=status,
        publisher="U.S. Census Bureau",
        landing_url=listing,
        selected_artifacts=(selected,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="LATEST_AVAILABLE county adult 18+ weights; historical 2024 fixed",
        input_evidence_status="VALIDATED",
        extra={"listed_years": sorted(years)},
    )


def discover_hud() -> FreshnessCheck:
    arts = [
        _artifact_record(
            artifact_id="FMR2024_final_revised.xlsx",
            url="https://www.huduser.gov/portal/datasets/fmr/fmr2024/FMR2024_final_revised.xlsx",
            sha256=(_sidecar("FMR2024_final_revised.xlsx") or {}).get("sha256"),
            retrieved_at=(_sidecar("FMR2024_final_revised.xlsx") or {}).get("retrieved_at"),
            validation_status="VALIDATED",
        ),
        _artifact_record(
            artifact_id="FY26_FMRs_revised.xlsx",
            url="https://www.huduser.gov/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.xlsx",
            sha256=(_sidecar("FY26_FMRs_revised.xlsx") or {}).get("sha256"),
            retrieved_at=(_sidecar("FY26_FMRs_revised.xlsx") or {}).get("retrieved_at"),
            validation_status="VALIDATED",
        ),
    ]
    try:
        html, checked = fetch_text(HUD_FMR_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "hud_fmr",
            publisher="U.S. Department of Housing and Urban Development",
            landing_url=HUD_FMR_LANDING,
            evidence="VALIDATED",
            vintage="FY2024 / FY2026",
            artifact="FMR2024_final_revised.xlsx / FY26_FMRs_revised.xlsx",
            artifacts=arts,
            reason=f"HUD FMR landing page could not be retrieved: {exc}",
        )
    has_2024 = "FMR2024_final_revised" in html or "fmr2024" in html.lower()
    has_2026 = "FY26_FMRs" in html or "fmr2026" in html.lower() or "fy2026" in html.lower()
    has_2027 = bool(re.search(r"fy\s*2027|fmr2027|FY27_FMR", html, re.IGNORECASE))
    if not (has_2024 or has_2026):
        return _failed(
            "hud_fmr",
            publisher="U.S. Department of Housing and Urban Development",
            landing_url=HUD_FMR_LANDING,
            evidence="VALIDATED",
            vintage="FY2024 / FY2026",
            artifact="FMR2024_final_revised.xlsx / FY26_FMRs_revised.xlsx",
            artifacts=arts,
            reason="HUD FMR page retrieved but selected FY2024/FY2026 filenames were not found.",
        )
    newer = has_2027
    return FreshnessCheck(
        source_id="hud_fmr",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="FY2027" if newer else "FY2024 / FY2026",
        selected_vintage="FY2024 / FY2026",
        selected_artifact="FMR2024_final_revised.xlsx / FY26_FMRs_revised.xlsx",
        newer_data_exists=newer,
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            "Official HUD FMR dataset page checked. Selected historical FY2024 "
            f"present={has_2024}; target FY2026 present={has_2026}; FY2027 listed={has_2027}."
        ),
        freshness_check_status="NEWER_AVAILABLE" if newer else "VERIFIED_CURRENT",
        publisher="U.S. Department of Housing and Urban Development",
        landing_url=HUD_FMR_LANDING,
        selected_artifacts=tuple(arts),
        transformation_method="NONE (year-specific FMR workbooks)",
        input_evidence_status="VALIDATED",
    )


def _usda_months_from_coverage() -> dict[str, Any]:
    by_plan: dict[str, Any] = {}
    for art in _coverage_artifacts():
        source_id = str(art.get("source_id") or "")
        if not source_id.startswith("usda_food_"):
            continue
        notes = str(art.get("notes") or "")
        match = re.search(r"months_included=(\[[^\]]+\])", notes)
        months: list[str] = []
        if match:
            try:
                months = [str(m) for m in ast_literal_list(match.group(1))]
            except (ValueError, SyntaxError, TypeError):
                months = []
        key = source_id.replace("usda_food_", "").rsplit("_", 1)[0]
        year_token = source_id.rsplit("_", 1)[-1]
        filename = {
            "low_cost": "usda-lowcostplan-sept2007-present.xlsx",
            "thrifty": "usda-thriftyplan-june2021-present.xlsx",
            "alaska": "usda-alaska-june2023-present.xlsx",
            "hawaii": "usda-hawaii-june2023-present.xlsx",
        }.get(key, source_id)
        sidecar = _sidecar(filename)
        # Prefer a complete 2024 year over a later YTD overwrite.
        if key in by_plan and year_token != "2024" and by_plan[key].get("month_count", 0) >= 12:
            continue
        by_plan[key] = {
            "filename": filename,
            "sha256": art.get("sha256") or (sidecar or {}).get("sha256"),
            "retrieved_at": art.get("retrieved_at") or (sidecar or {}).get("retrieved_at"),
            "months_included": months,
            "month_count": len(months),
            "first_month": months[0] if months else None,
            "last_month": months[-1] if months else None,
            "url": f"https://www.fna.usda.gov/sites/default/files/resource-files/{filename}",
        }
    return by_plan


def _usda_months_from_cache() -> dict[str, Any]:
    from_coverage = _usda_months_from_coverage()
    try:
        from foundation.sources.usda_food import USDA_ARCHIVES
    except ImportError:
        return from_coverage
    for key, spec in USDA_ARCHIVES.items():
        path = CACHE_DIR / spec["filename"]
        sidecar = _sidecar(spec["filename"])
        existing = from_coverage.get(key, {})
        if key not in from_coverage:
            from_coverage[key] = {
                "filename": spec["filename"],
                "sha256": (sidecar or {}).get("sha256"),
                "retrieved_at": (sidecar or {}).get("retrieved_at"),
                "months_included": [],
                "month_count": 0,
                "first_month": None,
                "last_month": None,
                "url": f"https://www.fna.usda.gov/sites/default/files/resource-files/{spec['filename']}",
            }
        elif sidecar:
            existing["sha256"] = existing.get("sha256") or sidecar.get("sha256")
            existing["retrieved_at"] = existing.get("retrieved_at") or sidecar.get("retrieved_at")
        if path.exists() and not from_coverage[key].get("months_included"):
            from_coverage[key]["filename"] = spec["filename"]
    return from_coverage


def ast_literal_list(raw: str) -> list[Any]:
    import ast

    value = ast.literal_eval(raw)
    if not isinstance(value, list):
        raise TypeError("not a list")
    return value


def discover_usda() -> FreshnessCheck:
    landing = USDA_FOOD_LANDING
    alt = "https://www.fna.usda.gov/research/cnpp/usda-food-plans/cost-food-monthly-reports"
    plans = _usda_months_from_cache()
    arts = [
        _artifact_record(
            artifact_id=spec["filename"],
            url=spec.get("url"),
            sha256=spec.get("sha256"),
            retrieved_at=spec.get("retrieved_at"),
            validation_status="VALIDATED",
        )
        for spec in plans.values()
    ]
    low = plans.get("low_cost") or {}
    months = list(low.get("months_included") or [])
    html = ""
    checked = ""
    err: str | None = None
    for url in (landing, alt):
        try:
            html, checked = fetch_text(url)
            landing = url
            err = None
            break
        except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
            err = str(exc)
    if err and not html:
        return _failed(
            "usda_food",
            publisher="USDA CNPP",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="USDA Low-Cost / Thrifty official archives",
            artifact="usda-lowcostplan-sept2007-present.xlsx",
            artifacts=arts,
            reason=f"USDA Cost of Food archive page could not be retrieved: {err}",
            extra={"months_included": months, "month_count": len(months)},
        )
    listed = any(
        name in html
        for name in (
            "usda-lowcostplan",
            "lowcostplan",
            "cost-food-monthly",
            "Cost of Food",
        )
    )
    if not listed:
        return _failed(
            "usda_food",
            publisher="USDA CNPP",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="USDA Low-Cost / Thrifty official archives",
            artifact="usda-lowcostplan-sept2007-present.xlsx",
            artifacts=arts,
            reason="USDA page retrieved but official food-plan archive identifiers were not found.",
            extra={"months_included": months},
        )
    return FreshnessCheck(
        source_id="usda_food",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="USDA Low-Cost / Thrifty monthly archives",
        selected_vintage="USDA official monthly archives (2024 full year; 2026 YTD if incomplete)",
        selected_artifact="usda-lowcostplan-sept2007-present.xlsx / usda-thriftyplan-june2021-present.xlsx",
        newer_data_exists=False,
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=(
            "Official USDA Cost of Food archive page checked. "
            "Canonical plan is Low-Cost; Thrifty is sensitivity. "
            "Months below are from parsed official workbook rows, not a label."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="USDA Center for Nutrition Policy and Promotion",
        landing_url=landing,
        selected_artifacts=tuple(arts),
        transformation_method="adult 19-50 midpoint × official 1.20 one-person factor",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        months_included=tuple(months),
        month_count=len(months) or None,
        first_month=months[0] if months else None,
        last_month=months[-1] if months else None,
        extra={
            "plans": {k: {kk: vv for kk, vv in v.items() if kk != "url"} for k, v in plans.items()}
        },
    )


def discover_cms() -> FreshnessCheck:
    landing = CMS_PUF_LANDING
    sbe_landing = "https://www.cms.gov/marketplace/resources/data/state-based-public-use-files"
    coverage_arts = [
        a
        for a in _coverage_artifacts()
        if str(a.get("source_id") or "").startswith(("cms_", "sbe_"))
    ]
    arts = [
        _artifact_record(
            artifact_id=str(a.get("source_id")),
            sha256=a.get("sha256"),
            retrieved_at=a.get("retrieved_at"),
            validation_status=a.get("validation_status"),
        )
        for a in coverage_arts
    ]
    try:
        html, checked = fetch_text(landing)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "cms_marketplace_sbe",
            publisher="Centers for Medicare & Medicaid Services",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="PY2024 / PY2026 Exchange PUF + SBE",
            artifact="cms rate/plan/service-area PUF zips",
            artifacts=arts,
            reason=f"CMS Marketplace PUF landing could not be retrieved: {exc}",
        )
    has_2024 = "2024" in html and ("rate-puf" in html.lower() or "public-use-files" in html.lower())
    has_2026 = "2026" in html
    has_2027 = bool(re.search(r"2027\s*(rate|plan|puf)", html, re.IGNORECASE))
    if not (has_2024 or has_2026):
        return _failed(
            "cms_marketplace_sbe",
            publisher="Centers for Medicare & Medicaid Services",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="PY2024 / PY2026 Exchange PUF + SBE",
            artifact="federal Exchange PUF + SBE QHP archives",
            artifacts=arts,
            reason="CMS PUF landing retrieved but plan-year 2024/2026 markers were not found.",
        )
    return FreshnessCheck(
        source_id="cms_marketplace_sbe",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="PY2027" if has_2027 else "PY2024 / PY2026",
        selected_vintage="PY2024 / PY2026 Exchange PUF + year-specific SBE",
        selected_artifact="cms_rate_puf / plan_puf / service_area_puf + SBE archives",
        newer_data_exists=has_2027,
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=(
            f"Official CMS Marketplace PUF page checked ({landing}). "
            f"SBE listing: {sbe_landing}. Selected artifacts listed with hashes "
            "from the current coverage retrieve record. Not a published healthcare headline."
        ),
        freshness_check_status="NEWER_AVAILABLE" if has_2027 else "VERIFIED_CURRENT",
        publisher="Centers for Medicare & Medicaid Services",
        landing_url=landing,
        selected_artifacts=tuple(arts),
        transformation_method="lowest Silver age-40 join of federal PUF + year-specific SBE",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        extra={"sbe_landing": sbe_landing, "has_2024": has_2024, "has_2026": has_2026},
    )


def discover_meps() -> FreshnessCheck:
    refresh = check_meps_2024_full_year_listing()
    checked = _now_iso()
    released = bool(refresh.get("released"))
    notes = str(refresh.get("notes") or "")
    if "Could not retrieve" in notes:
        status = "CHECK_FAILED"
        newer: bool | None = None
    elif released:
        status = "NEWER_AVAILABLE"
        newer = True
    else:
        status = "VERIFIED_CURRENT"
        newer = False
    sidecar = _sidecar("h251dat.zip")
    art = _artifact_record(
        artifact_id="h251dat.zip",
        url="https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="RETRIEVED_UNVALIDATED",
    )
    return FreshnessCheck(
        source_id="meps_full_year_consolidated",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=(
            str(refresh.get("listed_puf_id")) if released else f"{MEPS_PUF_ID} / {MEPS_DATA_YEAR}"
        ),
        selected_vintage=f"{MEPS_PUF_ID} / {MEPS_DATA_YEAR}",
        selected_artifact="h251dat.zip",
        newer_data_exists=newer,
        retrieval_validation_status="RETRIEVED_UNVALIDATED",
        reason_if_not_refreshed=(
            "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
            f"Official PUF listing checked at {MEPS_LISTING_URL}. {notes} "
            "Scheduled future releases do not count as released. "
            "HC-251 download is not derivation-ready."
        ),
        freshness_check_status=status,
        publisher="AHRQ MEPS",
        landing_url=MEPS_LISTING_URL,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="weighted-mean OOP pending; not yet derived",
        input_evidence_status="RETRIEVED_UNVALIDATED",
        extra={"listing": refresh},
    )


def discover_nhts() -> FreshnessCheck:
    sidecar = _sidecar("nhts_2022_csv.zip")
    art = _artifact_record(
        artifact_id="nhts_2022_csv.zip",
        url=NHTS_LANDING,
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED",
    )
    try:
        html, checked = fetch_text(NHTS_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "nhts_mileage",
            publisher="FHWA / ORNL NHTS",
            landing_url=NHTS_LANDING,
            evidence="VALIDATED",
            vintage="2022 NHTS V2.1",
            artifact="nhts_2022_csv.zip",
            artifacts=[art],
            reason=f"NHTS downloads page could not be retrieved: {exc}",
        )
    has_2022 = "2022" in html
    has_newer = bool(re.search(r"2024 NHTS|NHTS 2024|2024 NextGen", html, re.IGNORECASE))
    if not has_2022:
        return _failed(
            "nhts_mileage",
            publisher="FHWA / ORNL NHTS",
            landing_url=NHTS_LANDING,
            evidence="VALIDATED",
            vintage="2022 NHTS V2.1",
            artifact="nhts_2022_csv.zip",
            artifacts=[art],
            reason="NHTS page retrieved but 2022 survey vintage was not found.",
        )
    return FreshnessCheck(
        source_id="nhts_mileage",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="2024 NHTS" if has_newer else "2022 NHTS V2.1",
        selected_vintage="2022 NHTS V2.1",
        selected_artifact="nhts_2022_csv.zip",
        newer_data_exists=has_newer,
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            "Official NHTS downloads page checked. Selected structural survey is 2022 V2.1. "
            "Foundation Mobility Standard is weighted median. Do not inflate miles."
        ),
        freshness_check_status="NEWER_AVAILABLE" if has_newer else "VERIFIED_CURRENT",
        publisher="FHWA / Oak Ridge National Laboratory",
        landing_url=NHTS_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="weighted median of filtered one-person one-worker licensed households",
        input_evidence_status="VALIDATED",
    )


def discover_epa() -> FreshnessCheck:
    sidecar = _sidecar("epa_fueleconomy_vehicles.csv.zip") or _sidecar("vehicles.csv.zip")
    art = _artifact_record(
        artifact_id="epa_fueleconomy_vehicles.csv.zip",
        url="https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="RETRIEVED_UNVALIDATED",
    )
    try:
        html, checked = fetch_text(EPA_FUELEconomy_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "epa_vehicle",
            publisher="EPA / DOE fueleconomy.gov",
            landing_url=EPA_FUELEconomy_LANDING,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="EPA/DOE fueleconomy.gov vehicles.csv.zip",
            artifact="epa_fueleconomy_vehicles.csv.zip",
            artifacts=[art],
            reason=f"EPA/DOE download page could not be retrieved: {exc}",
        )
    has_vehicles = "vehicles.csv" in html.lower()
    if not has_vehicles:
        return _failed(
            "epa_vehicle",
            publisher="EPA / DOE fueleconomy.gov",
            landing_url=EPA_FUELEconomy_LANDING,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="EPA/DOE fueleconomy.gov vehicles.csv.zip",
            artifact="epa_fueleconomy_vehicles.csv.zip",
            artifacts=[art],
            reason="fueleconomy.gov download page retrieved but vehicles.csv was not listed.",
        )
    return FreshnessCheck(
        source_id="epa_vehicle",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="EPA/DOE fueleconomy.gov vehicles.csv.zip",
        selected_vintage="EPA/DOE fueleconomy.gov vehicles.csv.zip",
        selected_artifact="epa_fueleconomy_vehicles.csv.zip",
        newer_data_exists=False,
        retrieval_validation_status="RETRIEVED_UNVALIDATED",
        reason_if_not_refreshed=(
            "OD-004 methodology is FROZEN; EPA MPG evidence is RETRIEVED_UNVALIDATED. "
            "Official fueleconomy.gov download page still lists vehicles.csv. "
            "Frozen methodology is not VALIDATED cohort extraction."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="EPA / DOE",
        landing_url=EPA_FUELEconomy_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="median combined MPG cohort pending validation",
        input_evidence_status="RETRIEVED_UNVALIDATED",
    )


def discover_eia() -> FreshnessCheck:
    sidecar = _sidecar("pswrgvwall.xls")
    art = _artifact_record(
        artifact_id="pswrgvwall.xls",
        url="https://www.eia.gov/petroleum/gasdiesel/xls/pswrgvwall.xls",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED",
    )
    try:
        html, checked = fetch_text(EIA_GAS_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "eia_gasoline",
            publisher="U.S. Energy Information Administration",
            landing_url=EIA_GAS_LANDING,
            evidence="VALIDATED",
            vintage="EIA weekly retail gasoline",
            artifact="pswrgvwall.xls",
            artifacts=[art],
            reason=f"EIA gasoline/diesel page could not be retrieved: {exc}",
        )
    has_xls = "pswrgvwall" in html.lower() or "gasdiesel" in html.lower()
    if not has_xls:
        return _failed(
            "eia_gasoline",
            publisher="U.S. Energy Information Administration",
            landing_url=EIA_GAS_LANDING,
            evidence="VALIDATED",
            vintage="EIA weekly retail gasoline",
            artifact="pswrgvwall.xls",
            artifacts=[art],
            reason="EIA page retrieved but pswrgvwall.xls / weekly gasoline workbook was not found.",
        )
    return FreshnessCheck(
        source_id="eia_gasoline",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="EIA weekly retail gasoline pswrgvwall.xls",
        selected_vintage="EIA weekly retail gasoline",
        selected_artifact="pswrgvwall.xls",
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            "Official EIA gasoline/diesel page checked. Selected workbook is still pswrgvwall.xls. "
            "Use target-year observations / YTD. Do not relabel source year."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="U.S. Energy Information Administration",
        landing_url=EIA_GAS_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="target-year / YTD weekly retail regular gasoline",
        input_evidence_status="VALIDATED",
    )


def discover_naic() -> FreshnessCheck:
    sidecar = _sidecar("publication-aut-pb-auto-insurance-database.pdf")
    art = _artifact_record(
        artifact_id="publication-aut-pb-auto-insurance-database.pdf",
        url=NAIC_LANDING,
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="RETRIEVED_UNVALIDATED",
    )
    try:
        html, checked = fetch_text(NAIC_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "naic_auto_insurance",
            publisher="NAIC",
            landing_url=NAIC_LANDING,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="2022/2023 Auto Insurance Database Report",
            artifact="publication-aut-pb-auto-insurance-database.pdf",
            artifacts=[art],
            reason=f"NAIC Auto Insurance Database Report page could not be retrieved: {exc}",
        )
    has_report = (
        "auto insurance database" in html.lower() or "auto-insurance-database" in html.lower()
    )
    if not has_report:
        return _failed(
            "naic_auto_insurance",
            publisher="NAIC",
            landing_url=NAIC_LANDING,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="NAIC Auto Insurance Database Report",
            artifact="publication-aut-pb-auto-insurance-database.pdf",
            artifacts=[art],
            reason="NAIC page retrieved but Auto Insurance Database Report was not identified.",
        )
    return FreshnessCheck(
        source_id="naic_auto_insurance",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="NAIC Auto Insurance Database Report (data through 2023)",
        selected_vintage="2022/2023 Auto Insurance Database Report / data through 2023",
        selected_artifact="publication-aut-pb-auto-insurance-database.pdf",
        newer_data_exists=False,
        retrieval_validation_status="RETRIEVED_UNVALIDATED",
        reason_if_not_refreshed=(
            "Official NAIC report page checked. PDF retrieved. "
            "State-table extraction is not a validated numeric series."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="National Association of Insurance Commissioners",
        landing_url=NAIC_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="state-table extraction pending validation",
        input_evidence_status="RETRIEVED_UNVALIDATED",
    )


def discover_bls_ce() -> FreshnessCheck:
    sidecar = _sidecar("intrvw24.zip")
    art = _artifact_record(
        artifact_id="intrvw24.zip",
        url="https://www.bls.gov/cex/pumd/data/csv/intrvw24.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="INCOMPLETE_PROVENANCE",
    )
    try:
        html, checked = fetch_text(BLS_CE_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "bls_ce",
            publisher="U.S. Bureau of Labor Statistics",
            landing_url=BLS_CE_LANDING,
            evidence="INCOMPLETE_PROVENANCE",
            vintage="2024 Interview PUMD",
            artifact="intrvw24.zip",
            artifacts=[art],
            reason=f"BLS CE PUMD listing could not be retrieved: {exc}",
        )
    has_24 = "intrvw24" in html.lower()
    has_25 = "intrvw25" in html.lower()
    if not (has_24 or "pumd" in html.lower()):
        return _failed(
            "bls_ce",
            publisher="U.S. Bureau of Labor Statistics",
            landing_url=BLS_CE_LANDING,
            evidence="INCOMPLETE_PROVENANCE",
            vintage="2024 Interview PUMD",
            artifact="intrvw24.zip",
            artifacts=[art],
            reason="BLS CE PUMD page retrieved but Interview ZIP identifiers were not found.",
        )
    return FreshnessCheck(
        source_id="bls_ce",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="intrvw25.zip"
        if has_25
        else "2024 Interview PUMD intrvw24.zip",
        selected_vintage="2024 Interview PUMD cache",
        selected_artifact="intrvw24.zip",
        newer_data_exists=has_25,
        retrieval_validation_status="INCOMPLETE_PROVENANCE",
        reason_if_not_refreshed=(
            "Official BLS CE PUMD listing checked. Newest listed Interview vintage recorded. "
            "Official automated re-retrieve of the ZIP historically HTTP 403. "
            "CHECKED_BUT_RETRIEVAL_FAILED for the bytes; cached parse is not VALIDATED. "
            "Maintenance / essentials / recreation remain INCOMPLETE_PROVENANCE."
        ),
        freshness_check_status="NEWER_AVAILABLE" if has_25 else "VERIFIED_CURRENT",
        publisher="U.S. Bureau of Labor Statistics",
        landing_url=BLS_CE_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="Interview FMLI / MTBI / VQB parse from cache",
        input_evidence_status="INCOMPLETE_PROVENANCE",
        extra={"listing_has_intrvw24": has_24, "listing_has_intrvw25": has_25},
    )


def discover_fcc() -> FreshnessCheck:
    try:
        html, checked = fetch_text(FCC_URS_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "fcc_broadband",
            publisher="Federal Communications Commission",
            landing_url=FCC_URS_LANDING,
            evidence="SOURCE_GAP",
            reason=(
                f"FCC Urban Rate Survey page retrieve failed: {exc}. "
                "Historical retrieve HTTP 403 / incomplete. Broadband price remains SOURCE_GAP."
            ),
        )
    has_urs = "urban rate" in html.lower() or "urs" in html.lower()
    return FreshnessCheck(
        source_id="fcc_broadband",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="FCC Urban Rate Survey" if has_urs else None,
        selected_vintage=None,
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status="SOURCE_GAP",
        reason_if_not_refreshed=(
            "Official FCC URS page was reached but production broadband PRICE "
            "evidence remains SOURCE_GAP / incomplete. Do not invent a price."
        ),
        freshness_check_status="SOURCE_GAP",
        publisher="Federal Communications Commission",
        landing_url=FCC_URS_LANDING,
        selected_artifacts=(),
        transformation_method=None,
        input_evidence_status="SOURCE_GAP",
    )


def discover_bea() -> FreshnessCheck:
    sidecar = _sidecar("SARPP.zip")
    art = _artifact_record(
        artifact_id="SARPP.zip",
        url="https://apps.bea.gov/regional/zip/SARPP.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED",
    )
    try:
        html, checked = fetch_text(BEA_RPP_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "bea_rpp",
            publisher="U.S. Bureau of Economic Analysis",
            landing_url=BEA_RPP_LANDING,
            evidence="VALIDATED",
            vintage="BEA SARPP All-items",
            artifact="SARPP.zip",
            artifacts=[art],
            reason=f"BEA RPP landing page could not be retrieved: {exc}",
        )
    current = re.search(r"Current Release:\s*</strong>\s*([^<\n]+)", html, re.IGNORECASE)
    if current is None:
        current = re.search(r"Current Release:</strong>\s*([^<\n]+)", html, re.IGNORECASE)
    if current is None:
        current = re.search(r"Current Release:\s*([A-Za-z]+ \d{1,2}, \d{4})", html, re.IGNORECASE)
    nxt = re.search(r"Next release:\s*</strong>\s*([^<\n]+)", html, re.IGNORECASE)
    if nxt is None:
        nxt = re.search(r"Next release:</strong>\s*([^<\n]+)", html, re.IGNORECASE)
    if nxt is None:
        nxt = re.search(r"Next release:\s*([A-Za-z]+ \d{1,2}, \d{4})", html, re.IGNORECASE)
    current_rel = current.group(1).strip() if current else None
    next_rel = nxt.group(1).strip() if nxt else None
    has_2024 = "2024" in html and ("RPP" in html or "Regional price parities" in html)
    if not current_rel and not has_2024:
        return _failed(
            "bea_rpp",
            publisher="U.S. Bureau of Economic Analysis",
            landing_url=BEA_RPP_LANDING,
            evidence="VALIDATED",
            vintage="BEA SARPP",
            artifact="SARPP.zip",
            artifacts=[art],
            reason="BEA RPP page retrieved but current-release / 2024 data year could not be parsed.",
        )
    vintage = (
        f"BEA SARPP All-items 2024 / current release {current_rel}"
        if current_rel
        else "BEA SARPP All-items 2024"
    )
    return FreshnessCheck(
        source_id="bea_rpp",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=vintage,
        selected_vintage=vintage,
        selected_artifact="SARPP.zip",
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            f"Official BEA RPP landing checked. Current release={current_rel!r}; "
            f"Next release={next_rel!r}. Selected artifact SARPP.zip. "
            "2026 cost year reuses 2024 as LATEST_AVAILABLE and does not relabel the source year."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="U.S. Bureau of Economic Analysis",
        landing_url=BEA_RPP_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="LATEST_AVAILABLE All-items state RPP; source year not relabeled",
        input_evidence_status="VALIDATED",
        extra={"current_release": current_rel, "next_release": next_rel},
    )


def discover_federal_tax() -> FreshnessCheck:
    from foundation.living_cost.taxes import FEDERAL_TAX_RULES

    years = sorted(FEDERAL_TAX_RULES)
    irs = "https://www.irs.gov/irb"
    try:
        html, checked = fetch_text(irs)
        fetched = True
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        html = ""
        checked = _now_iso()
        fetched = False
        fetch_err = str(exc)
    else:
        fetch_err = None
    if not fetched:
        status = "CHECK_FAILED"
        newer: bool | None = None
        reason = (
            f"IRS IRB landing could not be retrieved ({fetch_err}). "
            f"Code tables exist for {years} only. Inventory not validated against primary IRS/SSA artifacts."
        )
    else:
        status = "MANUAL_VERIFICATION_REQUIRED"
        newer = None
        reason = (
            "IRS IRB page was reached, but presence of in-code 2024/2026 tables is not "
            "proof they remain the newest applicable Rev. Proc. Manual verification required. "
            f"Years present in code: {years}."
        )
        if "html" not in html.lower() and "irs" not in html.lower():
            status = "CHECK_FAILED"
            reason = "IRS IRB response did not look like the official bulletin page."
    return FreshnessCheck(
        source_id="federal_tax_law",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=f"code tables {years}",
        selected_vintage="2024 and 2026 statutory tables in code",
        selected_artifact=None,
        newer_data_exists=newer,
        retrieval_validation_status="INVENTORY_NOT_VALIDATED",
        reason_if_not_refreshed=reason,
        freshness_check_status=status,
        publisher="Internal Revenue Service / SSA",
        landing_url=irs,
        selected_artifacts=(),
        transformation_method="RULE_YEAR; no silent fallback to another year",
        input_evidence_status="INVENTORY_NOT_VALIDATED",
        extra={"rule_years_present": years},
    )


def discover_state_tax() -> FreshnessCheck:
    return FreshnessCheck(
        source_id="state_tax_law",
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found="2024 and 2026 schedules in code",
        selected_vintage="2024 and 2026 schedules in code",
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status="SOURCE_GAP",
        reason_if_not_refreshed=(
            "State schedule inventory is incomplete / unvalidated. "
            "No programmatic 51-state official discovery of current-year statutes is bound. "
            "MANUAL_VERIFICATION_REQUIRED for remaining states; evidence stays SOURCE_GAP."
        ),
        freshness_check_status="MANUAL_VERIFICATION_REQUIRED",
        publisher="State revenue departments",
        landing_url=None,
        selected_artifacts=(),
        transformation_method="RULE_YEAR",
        input_evidence_status="SOURCE_GAP",
    )


def discover_local_tax() -> FreshnessCheck:
    return FreshnessCheck(
        source_id="local_tax_law",
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=(
            "MD county / NYC / Philadelphia verified; Harris County TX verified no local EIT"
        ),
        selected_vintage="partial verified inventory",
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status="SOURCE_GAP",
        reason_if_not_refreshed=(
            "Most county FIPS remain UNRESOLVED_SOURCE_GAP. "
            "Place-level class-C overlay not generally implemented. "
            "No complete official local-tax discovery is bound."
        ),
        freshness_check_status="MANUAL_VERIFICATION_REQUIRED",
        publisher="Local jurisdictions / state revenue agencies",
        landing_url=None,
        selected_artifacts=(),
        transformation_method="typed LocalTaxResult; unresolved ≠ 0",
        input_evidence_status="SOURCE_GAP",
    )


def discover_mobile() -> FreshnessCheck:
    return _gap(
        "mobile_price",
        publisher="none accepted",
        landing_url=None,
        evidence="SOURCE_GAP",
        reason="No accepted authoritative mobile PRICE source. Do not invent a price.",
    )


def discover_registration() -> FreshnessCheck:
    return _gap(
        "vehicle_registration",
        publisher="state DMVs",
        landing_url=None,
        evidence="SOURCE_GAP",
        reason="No accepted 51-state official registration-fee inventory.",
    )


def discover_replacement() -> FreshnessCheck:
    return FreshnessCheck(
        source_id="vehicle_replacement",
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=None,
        selected_vintage=None,
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status="FORMULA_FROZEN_INPUTS_PENDING",
        reason_if_not_refreshed=(
            "OD-005 formula frozen: (acquisition - residual) / usable remaining years. "
            "Acquisition price, residual/salvage value, and usable remaining years are not bound. "
            "Do not invent numeric values."
        ),
        freshness_check_status="SOURCE_GAP",
        publisher=None,
        landing_url=None,
        selected_artifacts=(),
        transformation_method="(acquisition - residual) / usable remaining years",
        input_evidence_status="FORMULA_FROZEN_INPUTS_PENDING",
    )


def discover_od010() -> FreshnessCheck:
    table = METADATA_DIR / "living_cost_od010_translation_table.json"
    bound = False
    if table.exists():
        try:
            payload = json.loads(table.read_text(encoding="utf-8"))
            bound = bool(payload.get("bound") is True and payload.get("series"))
        except (OSError, json.JSONDecodeError):
            bound = False
    return FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=None,
        selected_vintage=None,
        selected_artifact=None,
        newer_data_exists=None,
        retrieval_validation_status="INVENTORY_NOT_VALIDATED",
        reason_if_not_refreshed=(
            "Component-specific CPI/index series for lagged nominal dollars are not bound "
            f"into a live translation table (bound={bound}). "
            "translation_index_bound remains false until a real series table exists."
        ),
        freshness_check_status="MANUAL_VERIFICATION_REQUIRED",
        publisher="BLS CPI / medical / motor-vehicle indexes",
        landing_url="https://www.bls.gov/cpi/",
        selected_artifacts=(),
        transformation_method="CPI_UPDATED pending binding",
        input_evidence_status="INVENTORY_NOT_VALIDATED",
        extra={"translation_table_bound": bound},
    )


DISCOVERERS = {
    "acs_population_weights": discover_acs,
    "hud_fmr": discover_hud,
    "usda_food": discover_usda,
    "cms_marketplace_sbe": discover_cms,
    "meps_full_year_consolidated": discover_meps,
    "nhts_mileage": discover_nhts,
    "epa_vehicle": discover_epa,
    "eia_gasoline": discover_eia,
    "naic_auto_insurance": discover_naic,
    "bls_ce": discover_bls_ce,
    "fcc_broadband": discover_fcc,
    "mobile_price": discover_mobile,
    "bea_rpp": discover_bea,
    "federal_tax_law": discover_federal_tax,
    "state_tax_law": discover_state_tax,
    "local_tax_law": discover_local_tax,
    "vehicle_registration": discover_registration,
    "vehicle_replacement": discover_replacement,
    "od010_price_index": discover_od010,
}


def discover_all_families() -> dict[str, FreshnessCheck]:
    """Run every source-specific check. Does not calculate an MSLC."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, FreshnessCheck] = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fn): family for family, fn in DISCOVERERS.items()}
        for future in as_completed(futures):
            family = futures[future]
            try:
                results[family] = future.result()
            except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
                results[family] = _failed(
                    family,
                    publisher="unknown",
                    landing_url="",
                    evidence="UNAVAILABLE",
                    reason=f"discovery raised {exc}",
                )
    return {family: results[family] for family in DISCOVERERS}
