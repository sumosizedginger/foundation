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
from foundation.living_cost.freshness_currentness import (
    download_temp_bytes,
    eia_currentness_status,
    latest_month_from_names,
    local_pdf_matches_naic,
    mutable_artifact_status,
    parse_naic_report_identifiers,
    parse_usda_latest_report_month,
    select_latest_naic_report,
    usda_currentness_status,
)
from foundation.living_cost.manifest import (
    ACS_LANDING,
    BEA_RPP_LANDING,
    BLS_CE_LANDING,
    CMS_PUF_LANDING,
    EIA_GAS_LANDING,
    HUD_FMR_LANDING,
    NHTS_LANDING,
    USDA_FOOD_LANDING,
)
from foundation.sources.cms_marketplace import CMS_SBE_PUF_LANDING
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
        listing_freshness_status="CHECK_FAILED",
        artifact_currentness_status="CHECK_FAILED",
        selected_artifact_matches_latest=None,
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
        listing_freshness_status="SOURCE_GAP",
        artifact_currentness_status="SOURCE_GAP",
        selected_artifact_matches_latest=None,
        year_coverage={
            "2024": {"covered": False, "reason": "SOURCE_GAP"},
            "2026": {"covered": False, "reason": "SOURCE_GAP"},
        },
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
        listing_freshness_status=status,
        artifact_currentness_status="VERIFIED_CURRENT" if has_2024 else "CHECK_FAILED",
        selected_artifact_matches_latest=has_2024,
        year_coverage=_year_coverage(
            {
                "covered": has_2024,
                "source_data_year": 2024,
                "artifact": "acsdt5y2024-b01001.dat",
                "sha256": selected.get("sha256"),
                "note": "2024 ACS 5-Year B01001",
            },
            {
                "covered": has_2024,
                "source_data_year": 2024,
                "artifact": "acsdt5y2024-b01001.dat",
                "sha256": selected.get("sha256"),
                "note": "newest appropriate ACS; currently 2024; do not relabel as 2026",
            },
        ),
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
        listing_freshness_status="NEWER_AVAILABLE" if newer else "VERIFIED_CURRENT",
        artifact_currentness_status="VERIFIED_CURRENT"
        if (has_2024 and has_2026)
        else "CHECK_FAILED",
        selected_artifact_matches_latest=bool(has_2024 and has_2026),
        year_coverage=_year_coverage(
            {
                "covered": has_2024,
                "source_data_year": 2024,
                "artifact": "FMR2024_final_revised.xlsx",
                "sha256": arts[0].get("sha256") if arts else None,
                "note": "FY2024",
            },
            {
                "covered": has_2026,
                "source_data_year": 2026,
                "artifact": "FY26_FMRs_revised.xlsx",
                "sha256": arts[1].get("sha256") if len(arts) > 1 else None,
                "note": "FY2026",
            },
        ),
    )


USDA_WORKBOOK_FILENAMES: dict[str, str] = {
    "low_cost": "usda-lowcostplan-sept2007-present.xlsx",
    "thrifty": "usda-thriftyplan-june2021-present.xlsx",
    "alaska": "usda-alaska-june2023-present.xlsx",
    "hawaii": "usda-hawaii-june2023-present.xlsx",
}


def _normalize_year_record(year: int, rec: dict[str, Any]) -> dict[str, Any]:
    out = dict(rec)
    out["project_cost_year"] = year
    artifacts = out.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        ident = out.get("artifact")
        if ident:
            item = {"artifact_id": ident}
            if out.get("sha256"):
                item["sha256"] = out["sha256"]
            out["artifacts"] = [item]
    return out


def _year_coverage(y2024: dict[str, Any], y2026: dict[str, Any]) -> dict[str, Any]:
    return {
        "2024": _normalize_year_record(2024, y2024),
        "2026": _normalize_year_record(2026, y2026),
    }


def inspect_usda_official_workbook(url: str) -> dict[str, Any]:
    """Retrieve official USDA workbook bytes to a temp file. Do not write cache."""
    from foundation.sources.usda_food import canonicalize_month_label, parse_usda_official_xlsx

    path, digest = download_temp_bytes(
        url,
        headers=_BROWSER_HEADERS,
        suffix=".xlsx",
    )
    try:
        months_2026: list[str] = []
        for row in parse_usda_official_xlsx(path, reference_year=2026, plan_key="low_cost"):
            name = canonicalize_month_label(row.get("month"))
            if name and name not in months_2026:
                months_2026.append(name)
        return {
            "sha256": digest,
            "months_2026": months_2026,
            "latest_2026": latest_month_from_names(2026, months_2026),
        }
    finally:
        path.unlink(missing_ok=True)


def inspect_eia_official_workbook(url: str) -> dict[str, Any]:
    """Retrieve official EIA workbook bytes to a temp file. Do not write cache."""
    from foundation.sources.eia import max_eia_observation_date

    path, digest = download_temp_bytes(
        url,
        headers=_BROWSER_HEADERS,
        suffix=".xls",
    )
    try:
        return {
            "sha256": digest,
            "max_date": max_eia_observation_date(path),
        }
    finally:
        path.unlink(missing_ok=True)


NAIC_PUBLICATIONS_LANDING = "https://content.naic.org/publications"
NHTS_FHWA_LANDING = "https://www.fhwa.dot.gov/policyinformation/nhts.cfm"


def parse_usda_official_hrefs(html: str, *, page_url: str) -> dict[str, str]:
    """Map official workbook filenames to hrefs found on the Cost of Food page.

    Does not construct guessed hostnames from filenames.
    """
    from urllib.parse import urljoin

    found: dict[str, str] = {}
    for href in re.findall(r"""href=["']([^"']+)["']""", html, re.IGNORECASE):
        for filename in USDA_WORKBOOK_FILENAMES.values():
            if filename in href and filename not in found:
                found[filename] = urljoin(page_url, href)
    return found


def usda_year_month_records(
    artifacts: list[dict[str, Any]] | None = None,
) -> dict[int, dict[str, Any]]:
    """Separate historical 2024 months from current 2026 YTD months.

    A complete 2024 series must never overwrite or stand in for 2026 YTD.
    """
    by_year: dict[int, dict[str, Any]] = {}
    rows = artifacts if artifacts is not None else _coverage_artifacts()
    for art in rows:
        source_id = str(art.get("source_id") or "")
        if not source_id.startswith("usda_food_"):
            continue
        year_token = source_id.rsplit("_", 1)[-1]
        if not year_token.isdigit():
            continue
        year = int(year_token)
        notes = str(art.get("notes") or "")
        match = re.search(r"months_included=(\[[^\]]+\])", notes)
        months: list[str] = []
        if match:
            try:
                months = [str(m) for m in ast_literal_list(match.group(1))]
            except (ValueError, SyntaxError, TypeError):
                months = []
        key = source_id.replace("usda_food_", "").rsplit("_", 1)[0]
        filename = USDA_WORKBOOK_FILENAMES.get(key, source_id)
        sidecar = _sidecar(filename)
        year_rec = by_year.setdefault(
            year,
            {
                "source_year": year,
                "months_included": [],
                "month_count": 0,
                "first_month": None,
                "last_month": None,
                "plans": {},
            },
        )
        if key == "low_cost" and months:
            year_rec["months_included"] = list(months)
            year_rec["month_count"] = len(months)
            year_rec["first_month"] = months[0] if months else None
            year_rec["last_month"] = months[-1] if months else None
        year_rec["plans"][key] = {
            "filename": filename,
            "sha256": art.get("sha256") or (sidecar or {}).get("sha256"),
            "retrieved_at": art.get("retrieved_at") or (sidecar or {}).get("retrieved_at"),
            "months_included": months,
            "month_count": len(months),
            "first_month": months[0] if months else None,
            "last_month": months[-1] if months else None,
        }
    return by_year


def ast_literal_list(raw: str) -> list[Any]:
    import ast

    value = ast.literal_eval(raw)
    if not isinstance(value, list):
        raise TypeError("not a list")
    return value


def discover_usda() -> FreshnessCheck:
    landing = USDA_FOOD_LANDING
    years = usda_year_month_records()
    hist = years.get(2024) or {}
    current = years.get(2026) or {}
    current_months = list(current.get("months_included") or [])
    hrefs: dict[str, str] = {}
    try:
        html, checked = fetch_text(landing)
        hrefs = parse_usda_official_hrefs(html, page_url=landing)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "usda_food",
            publisher="USDA CNPP",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="USDA Low-Cost / Thrifty official archives",
            artifact="usda-lowcostplan-sept2007-present.xlsx",
            reason=f"USDA Cost of Food archive page could not be retrieved: {exc}",
            extra={"historical_2024": hist, "current_2026": current},
        )
    arts = []
    for filename in USDA_WORKBOOK_FILENAMES.values():
        sidecar = _sidecar(filename)
        official_url = hrefs.get(filename)
        arts.append(
            _artifact_record(
                artifact_id=filename,
                url=official_url,
                sha256=(sidecar or {}).get("sha256"),
                retrieved_at=(sidecar or {}).get("retrieved_at"),
                validation_status="VALIDATED" if official_url else "RETRIEVED_UNVALIDATED",
            )
        )
    if not hrefs:
        return _failed(
            "usda_food",
            publisher="USDA CNPP",
            landing_url=landing,
            evidence="MODELED_FROM_MEASURED_INPUTS",
            vintage="USDA Low-Cost / Thrifty official archives",
            artifact="usda-lowcostplan-sept2007-present.xlsx",
            artifacts=arts,
            reason="USDA page retrieved but official workbook hrefs were not parsed. No guessed URLs.",
            extra={"historical_2024": hist, "current_2026": current},
        )
    hist_months = list(hist.get("months_included") or [])
    substituted = bool(current_months) and current_months == hist_months and len(hist_months) == 12
    official_latest = parse_usda_latest_report_month(html)
    selected_latest = latest_month_from_names(2026, current_months)
    low_cost_url = hrefs.get(USDA_WORKBOOK_FILENAMES["low_cost"])
    selected_sha = (_sidecar(USDA_WORKBOOK_FILENAMES["low_cost"]) or {}).get("sha256")
    official_sha = None
    official_inspect: dict[str, object] | None = None
    if low_cost_url:
        try:
            official_inspect = inspect_usda_official_workbook(low_cost_url)
            official_sha = official_inspect.get("sha256")
            if official_inspect.get("latest_2026"):
                official_latest = official_inspect["latest_2026"] or official_latest
        except (OSError, RuntimeError, ValueError, requests.RequestException):
            official_inspect = None
            official_sha = None
    currentness = usda_currentness_status(
        official_latest=official_latest,
        selected_latest=selected_latest,
        official_sha=official_sha,
        selected_sha=selected_sha,
    )
    if substituted:
        currentness = {
            "listing_freshness_status": "CHECK_FAILED",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": "2024 full-year months cannot stand in for 2026 YTD.",
        }
    year_coverage = _year_coverage(
        {
            "covered": len(hist_months) == 12,
            "months_included": hist_months,
            "note": "full official 2024 months",
        },
        {
            "covered": bool(current_months) and not substituted,
            "months_included": current_months,
            "official_latest": official_latest,
            "selected_latest": selected_latest,
            "note": "2026 official YTD; not a 2024 substitution",
        },
    )
    extra = {
        "historical_2024": hist,
        "current_2026": current,
        "official_hrefs": hrefs,
        "substituted_2024_for_2026": substituted,
        "official_latest_month": official_latest,
        "selected_latest_month": selected_latest,
        "official_inspect": official_inspect,
        "year_coverage": year_coverage,
    }
    return FreshnessCheck(
        source_id="usda_food",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=(
            f"USDA official monthly archives (2024 historical; official latest {official_latest})"
        ),
        selected_vintage="USDA Low-Cost official monthly archive; 2026 uses official YTD months",
        selected_artifact=USDA_WORKBOOK_FILENAMES["low_cost"],
        newer_data_exists=currentness["newer_data_exists"],
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=(
            "Official FNS Cost of Food archive page checked. "
            "Workbook URLs are parsed hrefs, not constructed hostnames. "
            "2024 historical months and 2026 YTD months are stored separately. "
            f"{currentness['reason']}"
        ),
        freshness_check_status=str(currentness["freshness_check_status"]),
        publisher="USDA Center for Nutrition Policy and Promotion",
        landing_url=landing,
        selected_artifacts=tuple(arts),
        transformation_method="adult 19-50 midpoint x official 1.20 one-person factor",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        months_included=tuple(current_months),
        month_count=len(current_months) or None,
        first_month=current_months[0] if current_months else None,
        last_month=current_months[-1] if current_months else None,
        listing_freshness_status=currentness["listing_freshness_status"],
        artifact_currentness_status=currentness["artifact_currentness_status"],
        selected_artifact_matches_latest=currentness["selected_artifact_matches_latest"],
        year_coverage=year_coverage,
        extra=extra,
    )


def _cms_page_check(url: str, *, kind: str) -> dict[str, Any]:
    try:
        html, checked = fetch_text(url)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return {
            "kind": kind,
            "landing_url": url,
            "checked_at": _now_iso(),
            "status": "CHECK_FAILED",
            "plan_years_found": [],
            "error": str(exc),
        }
    years = sorted({int(y) for y in re.findall(r"\b(202[0-9])\b", html)})
    looks_official = (
        "public use" in html.lower() or "puf" in html.lower() or "exchange" in html.lower()
    )
    if not looks_official or not years:
        return {
            "kind": kind,
            "landing_url": url,
            "checked_at": checked,
            "status": "CHECK_FAILED",
            "plan_years_found": years,
            "error": f"{kind} page retrieved but official PUF/year markers were not found.",
        }
    return {
        "kind": kind,
        "landing_url": url,
        "checked_at": checked,
        "status": "VERIFIED_CURRENT",
        "plan_years_found": years,
        "has_2024": 2024 in years,
        "has_2026": 2026 in years,
        "has_2027": 2027 in years,
        "error": None,
    }


def discover_cms() -> FreshnessCheck:
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
    federal = _cms_page_check(CMS_PUF_LANDING, kind="federal_exchange")
    sbe = _cms_page_check(CMS_SBE_PUF_LANDING, kind="sbe")
    both_ok = federal["status"] == "VERIFIED_CURRENT" and sbe["status"] == "VERIFIED_CURRENT"
    newer = bool(federal.get("has_2027") or sbe.get("has_2027"))
    hashed = [a for a in arts if a.get("sha256")]
    # PY2024 filenames are version-addressed. Current PY2026 archives are mutable
    # and cannot be VERIFIED_CURRENT from a landing-page filename alone.
    artifact_status = "VERIFIED_CURRENT" if hashed else "CHECK_FAILED"
    if both_ok and newer:
        family_status = "NEWER_AVAILABLE"
        listing_status = "NEWER_AVAILABLE"
        matches = False
    elif both_ok:
        listing_status = "VERIFIED_CURRENT"
        family_status = "CHECK_FAILED"
        artifact_status = "CHECK_FAILED"
        matches = None
    else:
        listing_status = "CHECK_FAILED"
        family_status = "CHECK_FAILED"
        artifact_status = "CHECK_FAILED"
        matches = None
    checked = sbe.get("checked_at") or federal.get("checked_at") or _now_iso()
    year_coverage = _year_coverage(
        {
            "covered": bool(federal.get("has_2024") and hashed),
            "plan_year": 2024,
            "note": "PY2024 federal Exchange PUF + standalone SBE",
        },
        {
            "covered": bool(federal.get("has_2026") and hashed),
            "plan_year": 2026,
            "note": "PY2026 current-year PUF archives are mutable; listing is not byte proof",
        },
    )
    reason = (
        "Combined CMS family requires BOTH the federal Exchange PUF listing and the "
        "standalone SBE QHP PUF listing. SBE-FP states use the federal Exchange PUF "
        "and are not treated as standalone SBE archives. "
        f"federal={federal['status']}; sbe={sbe['status']}. "
        "Current plan-year PUF archives can change behind stable year labels; "
        "listing success is not artifact-byte currentness."
    )
    return FreshnessCheck(
        source_id="cms_marketplace_sbe",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="PY2024 / PY2026 Exchange PUF + standalone SBE",
        selected_vintage="PY2024 / PY2026 federal Exchange PUF + year-specific standalone SBE",
        selected_artifact="cms_rate_puf / plan_puf / service_area_puf + SBE archives",
        newer_data_exists=True if family_status == "NEWER_AVAILABLE" else None,
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=reason,
        freshness_check_status=family_status,
        publisher="Centers for Medicare & Medicaid Services",
        landing_url=CMS_PUF_LANDING,
        selected_artifacts=tuple(arts),
        transformation_method="lowest Silver age-40 join of federal PUF + year-specific SBE",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        listing_freshness_status=listing_status,
        artifact_currentness_status=artifact_status,
        selected_artifact_matches_latest=matches,
        year_coverage=year_coverage,
        extra={"federal_exchange": federal, "sbe": sbe, "hashed_artifact_count": len(hashed)},
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
    from foundation.living_cost.evidence_validators import (
        MEPS_CACHE_NAME,
        selected_cache_sha,
        validate_meps_derivation,
    )
    from foundation.sources.meps import load_meps_oop_derivation

    meps_validation = validate_meps_derivation(selected_sha=selected_cache_sha(MEPS_CACHE_NAME))
    derivation = load_meps_oop_derivation() if meps_validation.ok else None
    derived = meps_validation.ok
    evidence = meps_validation.evidence_status
    art = _artifact_record(
        artifact_id="h251dat.zip",
        url="https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status=evidence,
    )
    if derived:
        reason = (
            "MEPS HEALTH OOP DERIVATION: MODELED_FROM_MEASURED_INPUTS from official HC-251. "
            f"OD-002 weighted mean TOTSLF23={derivation['weighted_mean']}; "
            f"n={derivation['in_universe_n']}; source_data_year={MEPS_DATA_YEAR}. "
            "Filter: adults 18-64 with INSCOV23=1 (ANY PRIVATE). "
            f"Official PUF listing checked at {MEPS_LISTING_URL}. {notes} "
            "Download is not derivation. 2024 FYC remains unreleased."
        )
        method = "OD-002 weighted mean of TOTSLF23; AGELAST 18-64; INSCOV23=1 (ANY PRIVATE)"
    else:
        reason = (
            "MEPS HEALTH OOP DERIVATION: RETRIEVED_UNVALIDATED. "
            f"Official PUF listing checked at {MEPS_LISTING_URL}. {notes} "
            "Scheduled future releases do not count as released. "
            "HC-251 download is not derivation-ready."
        )
        method = "weighted-mean OOP pending; not yet derived"
    return FreshnessCheck(
        source_id="meps_full_year_consolidated",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=(
            str(refresh.get("listed_puf_id")) if released else f"{MEPS_PUF_ID} / {MEPS_DATA_YEAR}"
        ),
        selected_vintage=f"{MEPS_PUF_ID} / {MEPS_DATA_YEAR}",
        selected_artifact="h251dat.zip",
        newer_data_exists=newer,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status=status,
        publisher="AHRQ MEPS",
        landing_url=MEPS_LISTING_URL,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method=method,
        input_evidence_status=evidence,
        year_coverage=_year_coverage(
            {
                "covered": True,
                "source_data_year": MEPS_DATA_YEAR,
                "artifact": "h251dat.zip",
                "sha256": art.get("sha256"),
                "note": "MEPS source year 2023; 2024 uses OD-010 translation",
            },
            {
                "covered": True,
                "source_data_year": MEPS_DATA_YEAR,
                "artifact": "h251dat.zip",
                "sha256": art.get("sha256"),
                "note": "MEPS source year 2023; 2026 uses OD-010 translation",
            },
        ),
        extra={"listing": refresh, "derivation": derivation if derived else None},
    )


def _nhts_page_has_2022(html: str) -> tuple[bool, bool]:
    has_2022 = "2022" in html and ("nhts" in html.lower() or "household travel" in html.lower())
    has_newer = bool(re.search(r"2024 NHTS|NHTS 2024|2024 NextGen", html, re.IGNORECASE))
    return has_2022, has_newer


def discover_nhts() -> FreshnessCheck:
    sidecar = _sidecar("nhts_2022_csv.zip")
    art = _artifact_record(
        artifact_id="nhts_2022_csv.zip",
        url=NHTS_LANDING,
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED",
    )
    html = ""
    checked = ""
    used_url = NHTS_LANDING
    primary_err: str | None = None
    try:
        html, checked = fetch_text(NHTS_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        primary_err = str(exc)
        try:
            html, checked = fetch_text(NHTS_FHWA_LANDING)
            used_url = NHTS_FHWA_LANDING
        except (OSError, RuntimeError, ValueError, requests.RequestException) as exc2:
            return _failed(
                "nhts_mileage",
                publisher="FHWA / ORNL NHTS",
                landing_url=NHTS_LANDING,
                evidence="VALIDATED",
                vintage="2022 NHTS V2.1",
                artifact="nhts_2022_csv.zip",
                artifacts=[art],
                reason=(
                    f"NHTS downloads page failed ({exc}); FHWA corroboration page failed ({exc2})."
                ),
            )
    has_2022, has_newer = _nhts_page_has_2022(html)
    if not has_2022:
        return _failed(
            "nhts_mileage",
            publisher="FHWA / ORNL NHTS",
            landing_url=used_url,
            evidence="VALIDATED",
            vintage="2022 NHTS V2.1",
            artifact="nhts_2022_csv.zip",
            artifacts=[art],
            reason=(
                "Official NHTS page(s) retrieved but 2022 survey vintage was not found. "
                f"Primary error={primary_err!r}."
            ),
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
        landing_url=used_url,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="weighted median of filtered one-person one-worker licensed households",
        input_evidence_status="VALIDATED",
        year_coverage=_year_coverage(
            {
                "covered": has_2022,
                "source_data_year": 2022,
                "artifact": "nhts_2022_csv.zip",
                "sha256": art.get("sha256"),
                "note": "2022 NHTS structural survey applies to 2024",
            },
            {
                "covered": has_2022,
                "source_data_year": 2022,
                "artifact": "nhts_2022_csv.zip",
                "sha256": art.get("sha256"),
                "note": "2022 NHTS structural survey applies to 2026",
            },
        ),
        extra={"primary_error": primary_err, "used_url": used_url},
    )


def discover_epa() -> FreshnessCheck:
    sidecar = _sidecar("epa_fueleconomy_vehicles.csv.zip") or _sidecar("vehicles.csv.zip")
    from foundation.living_cost.evidence_validators import (
        EPA_CACHE_NAME,
        selected_cache_sha,
        validate_epa_cohorts,
    )

    epa_validation = validate_epa_cohorts(selected_sha=selected_cache_sha(EPA_CACHE_NAME))
    derived_mpg = epa_validation.ok
    epa_evidence = epa_validation.evidence_status
    art = _artifact_record(
        artifact_id="epa_fueleconomy_vehicles.csv.zip",
        url="https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip",
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status=epa_evidence,
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
    currentness = mutable_artifact_status(
        listing_ok=True,
        official_sha=None,
        selected_sha=(sidecar or {}).get("sha256"),
        official_identifier="vehicles.csv.zip",
        selected_identifier="vehicles.csv.zip",
    )
    return FreshnessCheck(
        source_id="epa_vehicle",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="EPA/DOE fueleconomy.gov vehicles.csv.zip",
        selected_vintage="EPA/DOE fueleconomy.gov vehicles.csv.zip",
        selected_artifact="epa_fueleconomy_vehicles.csv.zip",
        newer_data_exists=currentness["newer_data_exists"],
        retrieval_validation_status=epa_evidence,
        reason_if_not_refreshed=(
            "OD-004 methodology is FROZEN. "
            + (
                "EPA MPG evidence is MODELED_FROM_MEASURED_INPUTS from official "
                "fueleconomy.gov vehicles.csv.zip using cost_year-12..cost_year-8 "
                "gasoline compact+midsize comb08 medians. "
                if derived_mpg
                else "EPA MPG evidence is RETRIEVED_UNVALIDATED. "
            )
            + "Official fueleconomy.gov download page still lists vehicles.csv. "
            "The URL is mutable. Listing the filename is not byte currentness. "
            f"{currentness['reason']}"
        ),
        freshness_check_status=str(currentness["freshness_check_status"]),
        publisher="EPA / DOE",
        landing_url=EPA_FUELEconomy_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method=(
            "OD-004 used compact+midsize gasoline median comb08"
            if derived_mpg
            else "median combined MPG cohort pending validation"
        ),
        input_evidence_status=epa_evidence,
        listing_freshness_status=currentness["listing_freshness_status"],
        artifact_currentness_status=currentness["artifact_currentness_status"],
        selected_artifact_matches_latest=currentness["selected_artifact_matches_latest"],
        year_coverage=_year_coverage(
            {"covered": True, "note": "rolling EPA/DOE cohort applies to 2024 window"},
            {"covered": True, "note": "rolling EPA/DOE cohort applies to 2026 window"},
        ),
    )


def discover_eia() -> FreshnessCheck:
    from foundation.sources.eia import (
        EIA_GAS_XLS_URL,
        EIA_WORKBOOK_FILENAME,
        max_eia_observation_date,
        selected_eia_workbook_sha256,
        summarize_eia_year,
    )

    sidecar = _sidecar(EIA_WORKBOOK_FILENAME)
    local_path = CACHE_DIR / EIA_WORKBOOK_FILENAME
    # Identity is the selected workbook bytes. Sidecar SHA must not override.
    selected_sha = selected_eia_workbook_sha256(local_path)
    selected_max = max_eia_observation_date(local_path) if local_path.is_file() else None
    year_2024 = summarize_eia_year(local_path, reference_year=2024, sha256=selected_sha)
    year_2026 = summarize_eia_year(local_path, reference_year=2026, sha256=selected_sha)
    year_coverage = _year_coverage(year_2024, year_2026)
    art = _artifact_record(
        artifact_id=EIA_WORKBOOK_FILENAME,
        url=EIA_GAS_XLS_URL,
        sha256=selected_sha,
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="VALIDATED" if selected_sha else "UNAVAILABLE",
    )
    try:
        html, checked = fetch_text(EIA_GAS_LANDING)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "eia_gasoline",
            publisher="U.S. Energy Information Administration",
            landing_url=EIA_GAS_LANDING,
            evidence="VALIDATED" if selected_sha else "UNAVAILABLE",
            vintage="EIA weekly retail gasoline",
            artifact=EIA_WORKBOOK_FILENAME,
            artifacts=[art],
            reason=f"EIA gasoline/diesel page could not be retrieved: {exc}",
            extra={"year_coverage": year_coverage, "selected_sha256": selected_sha},
        )
    has_xls = "pswrgvwall" in html.lower() or "gasdiesel" in html.lower()
    if not has_xls:
        return _failed(
            "eia_gasoline",
            publisher="U.S. Energy Information Administration",
            landing_url=EIA_GAS_LANDING,
            evidence="VALIDATED" if selected_sha else "UNAVAILABLE",
            vintage="EIA weekly retail gasoline",
            artifact=EIA_WORKBOOK_FILENAME,
            artifacts=[art],
            reason="EIA page retrieved but pswrgvwall.xls / weekly gasoline workbook was not found.",
            extra={"year_coverage": year_coverage, "selected_sha256": selected_sha},
        )
    official_max = None
    official_sha = None
    try:
        inspected = inspect_eia_official_workbook(EIA_GAS_XLS_URL)
        official_max = inspected.get("max_date")
        official_sha = inspected.get("sha256")
    except (OSError, RuntimeError, ValueError, requests.RequestException):
        official_max = None
        official_sha = None
    if official_max is not None:
        year_2026 = {
            **year_2026,
            "official_max_date": official_max.isoformat(),
        }
        year_coverage = _year_coverage(year_2024, year_2026)
    currentness = eia_currentness_status(
        official_max_date=official_max,
        selected_max_date=selected_max,
        official_sha=official_sha,
        selected_sha=selected_sha,
    )
    return FreshnessCheck(
        source_id="eia_gasoline",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=(
            None
            if official_max is None
            else f"EIA weekly retail gasoline through {official_max.isoformat()}"
        ),
        selected_vintage=(
            None
            if selected_max is None
            else f"EIA weekly retail gasoline through {selected_max.isoformat()}"
        ),
        selected_artifact=EIA_WORKBOOK_FILENAME,
        newer_data_exists=currentness["newer_data_exists"],
        retrieval_validation_status="VALIDATED" if selected_sha else "UNAVAILABLE",
        reason_if_not_refreshed=(
            "Official EIA gasoline/diesel page checked. pswrgvwall.xls is a mutable URL. "
            f"{currentness['reason']}"
        ),
        freshness_check_status=str(currentness["freshness_check_status"]),
        publisher="U.S. Energy Information Administration",
        landing_url=EIA_GAS_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="target-year / YTD weekly retail regular gasoline",
        input_evidence_status="VALIDATED" if selected_sha else "UNAVAILABLE",
        listing_freshness_status=currentness["listing_freshness_status"],
        artifact_currentness_status=currentness["artifact_currentness_status"],
        selected_artifact_matches_latest=currentness["selected_artifact_matches_latest"],
        year_coverage=year_coverage,
        extra={
            "official_max_date": None if official_max is None else official_max.isoformat(),
            "selected_max_date": None if selected_max is None else selected_max.isoformat(),
            "selected_sha256": selected_sha,
            "official_sha256": official_sha,
        },
    )


def discover_naic() -> FreshnessCheck:
    from foundation.living_cost.evidence_validators import (
        naic_evidence_status,
        validate_naic_derivation,
    )
    from foundation.sources.naic_report import identify_naic_pdf, selected_naic_pdf_sha256

    sidecar = _sidecar("publication-aut-pb-auto-insurance-database.pdf")
    landing = NAIC_PUBLICATIONS_LANDING
    local_pdf = CACHE_DIR / "publication-aut-pb-auto-insurance-database.pdf"
    selected_sha = selected_naic_pdf_sha256(local_pdf)
    pdf_identity = identify_naic_pdf(local_pdf) if local_pdf.is_file() else {}
    naic_validation = validate_naic_derivation(selected_sha=selected_sha)
    naic_status = naic_evidence_status(selected_sha=selected_sha)
    art = _artifact_record(
        artifact_id="publication-aut-pb-auto-insurance-database.pdf",
        url="https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf",
        sha256=selected_sha,
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status=naic_status,
    )
    try:
        html, checked = fetch_text(landing)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        return _failed(
            "naic_auto_insurance",
            publisher="NAIC",
            landing_url=landing,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="NAIC Auto Insurance Database Report",
            artifact="publication-aut-pb-auto-insurance-database.pdf",
            artifacts=[art],
            reason=f"NAIC Publications listing could not be retrieved: {exc}",
        )
    reports = parse_naic_report_identifiers(html)
    latest = select_latest_naic_report(reports)
    if latest is None:
        return _failed(
            "naic_auto_insurance",
            publisher="NAIC",
            landing_url=landing,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="NAIC Auto Insurance Database Report",
            artifact="publication-aut-pb-auto-insurance-database.pdf",
            artifacts=[art],
            reason=(
                "NAIC Publications page retrieved but no Auto Insurance Database "
                "Report year range (for example AUT-PB 2022-2023) was identified."
            ),
        )
    pdf_ident = pdf_identity.get("publication_identifier")
    bound = bool(pdf_ident) and pdf_ident == latest.display_identifier
    if not bound:
        raw_bound = local_pdf_matches_naic(local_pdf, latest)
        bound = raw_bound is True
    if not bound:
        currentness = {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": False,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": (
                f"Latest listing is {latest.display_identifier} but the local PDF "
                f"identifier is {pdf_ident!r}."
            ),
        }
    elif not naic_validation.ok:
        currentness = {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": True,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": False,
            "reason": (
                f"PDF is bound to {latest.display_identifier} but NAIC table "
                f"validation failed: {naic_validation.issues}."
            ),
        }
    elif selected_sha is None:
        currentness = {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "CHECK_FAILED",
            "selected_artifact_matches_latest": None,
            "freshness_check_status": "CHECK_FAILED",
            "newer_data_exists": None,
            "reason": "Selected NAIC PDF bytes are absent.",
        }
    else:
        currentness = {
            "listing_freshness_status": "VERIFIED_CURRENT",
            "artifact_currentness_status": "VERIFIED_CURRENT",
            "selected_artifact_matches_latest": True,
            "freshness_check_status": "VERIFIED_CURRENT",
            "newer_data_exists": False,
            "reason": (
                f"Live listing {latest.display_identifier} matches the selected PDF "
                "identifier and Table 5 derivation binds to the selected-byte SHA."
            ),
        }
    year_note = (
        f"lagged NAIC report {latest.display_identifier}; source_data_year={latest.end_year}"
    )
    return FreshnessCheck(
        source_id="naic_auto_insurance",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=latest.display_identifier,
        selected_vintage=latest.display_identifier if bound else None,
        selected_artifact="publication-aut-pb-auto-insurance-database.pdf",
        newer_data_exists=currentness["newer_data_exists"],
        retrieval_validation_status=naic_status,
        reason_if_not_refreshed=(
            "Official NAIC Publications listing checked. Latest report identifier "
            f"is {latest.display_identifier}. {currentness['reason']}"
        ),
        freshness_check_status=str(currentness["freshness_check_status"]),
        publisher="National Association of Insurance Commissioners",
        landing_url=landing,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="Table 5 combined average premium extract; no MSLC",
        input_evidence_status=naic_status,
        listing_freshness_status=currentness["listing_freshness_status"],
        artifact_currentness_status=currentness["artifact_currentness_status"],
        selected_artifact_matches_latest=currentness["selected_artifact_matches_latest"],
        year_coverage=_year_coverage(
            {
                "covered": naic_validation.ok,
                "source_data_year": latest.end_year,
                "artifact": "publication-aut-pb-auto-insurance-database.pdf",
                "sha256": selected_sha,
                "note": year_note,
            },
            {
                "covered": naic_validation.ok,
                "source_data_year": latest.end_year,
                "artifact": "publication-aut-pb-auto-insurance-database.pdf",
                "sha256": selected_sha,
                "note": year_note,
            },
        ),
        extra={
            "publication_code": latest.publication_code,
            "start_year": latest.start_year,
            "end_year": latest.end_year,
            "display_identifier": latest.display_identifier,
            "pdf_identifier": pdf_ident,
            "identifiers_found": [item.display_identifier for item in reports],
            "local_pdf_bound": bound,
            "selected_sha256": selected_sha,
            "validation_issues": naic_validation.issues,
            "jurisdiction_count": (naic_validation.payload or {}).get("jurisdiction_count"),
        },
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
        year_coverage=_year_coverage(
            {"covered": has_24, "artifact": "intrvw24.zip", "note": "2024 Interview PUMD"},
            {"covered": False, "note": "2026 Interview PUMD not bound"},
        ),
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
    official_sha = None
    try:
        remote = download_temp_bytes(
            "https://apps.bea.gov/regional/zip/SARPP.zip",
            headers=_BROWSER_HEADERS,
            suffix=".zip",
            max_bytes=30_000_000,
        )
        official_sha = remote[1]
        remote[0].unlink(missing_ok=True)
    except (OSError, RuntimeError, ValueError, requests.RequestException):
        official_sha = None
    currentness = mutable_artifact_status(
        listing_ok=bool(current_rel or has_2024),
        official_sha=official_sha,
        selected_sha=(sidecar or {}).get("sha256"),
        official_identifier=current_rel,
        selected_identifier=current_rel,
    )
    return FreshnessCheck(
        source_id="bea_rpp",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=vintage,
        selected_vintage=vintage,
        selected_artifact="SARPP.zip",
        newer_data_exists=currentness["newer_data_exists"],
        retrieval_validation_status="VALIDATED",
        reason_if_not_refreshed=(
            f"Official BEA RPP landing checked. Current release={current_rel!r}; "
            f"Next release={next_rel!r}. SARPP.zip is a mutable URL. "
            f"{currentness['reason']} "
            "2026 cost year reuses 2024 as LATEST_AVAILABLE and does not relabel the source year."
        ),
        freshness_check_status=str(currentness["freshness_check_status"]),
        publisher="U.S. Bureau of Economic Analysis",
        landing_url=BEA_RPP_LANDING,
        selected_artifacts=(art,),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        transformation_method="LATEST_AVAILABLE All-items state RPP; source year not relabeled",
        input_evidence_status="VALIDATED",
        listing_freshness_status=currentness["listing_freshness_status"],
        artifact_currentness_status=currentness["artifact_currentness_status"],
        selected_artifact_matches_latest=currentness["selected_artifact_matches_latest"],
        year_coverage=_year_coverage(
            {"covered": True, "note": "BEA 2024 All-items RPP"},
            {
                "covered": True,
                "note": "2026 reuses 2024 as LATEST_AVAILABLE; source year not relabeled",
            },
        ),
        extra={"current_release": current_rel, "next_release": next_rel},
    )


def discover_federal_tax() -> FreshnessCheck:
    from foundation.living_cost.evidence_validators import (
        federal_tax_evidence_status,
        validate_federal_tax_inventory,
    )
    from foundation.living_cost.taxes import FEDERAL_TAX_RULES
    from foundation.sources.federal_tax import (
        IRS_PUBLICATIONS_LISTING_URL,
        discover_federal_tax_live,
        evaluate_federal_tax_freshness,
    )

    years = sorted(FEDERAL_TAX_RULES)
    validation = validate_federal_tax_inventory()
    evidence = federal_tax_evidence_status()
    payload = validation.payload or {}
    year_recs = payload.get("years") if isinstance(payload.get("years"), dict) else {}
    artifacts = []
    for item in payload.get("retrieved_artifacts") or []:
        if not isinstance(item, dict) or not item.get("sha256"):
            continue
        artifacts.append(
            _artifact_record(
                artifact_id=str(item.get("filename") or item.get("key")),
                url=item.get("url"),
                sha256=item.get("sha256"),
                retrieved_at=item.get("retrieved_at"),
                validation_status="VALIDATED" if item.get("http_ok") else "UNAVAILABLE",
            )
        )
    checked = _now_iso()
    try:
        live, live_error = discover_federal_tax_live(payload)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        live, live_error = None, str(exc)
    status, newer, reason = evaluate_federal_tax_freshness(
        inventory_valid=validation.ok,
        live=live,
        live_error=live_error,
    )
    if not validation.ok and status == "VERIFIED_CURRENT":
        status = "CHECK_FAILED"
        newer = None
        reason = f"Inventory is not validated: {validation.issues}."
    y2024_ok = bool((year_recs.get("2024") or {}).get("parsed_ok"))
    y2026_ok = bool((year_recs.get("2026") or {}).get("parsed_ok"))
    auth_2024 = (year_recs.get("2024") or {}).get("standard_deduction", {}).get("authority_id")
    auth_2026 = (year_recs.get("2026") or {}).get("standard_deduction", {}).get("authority_id")
    return FreshnessCheck(
        source_id="federal_tax_law",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=f"{auth_2024} / {auth_2026}",
        selected_vintage="2024 and 2026 statutory tables in code",
        selected_artifact="living_cost_federal_tax_inventory.json",
        newer_data_exists=newer,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status=status,
        publisher="Internal Revenue Service",
        landing_url=IRS_PUBLICATIONS_LISTING_URL,
        selected_artifacts=tuple(artifacts),
        transformation_method="RULE_YEAR; field-level IRS artifact provenance; no MSLC",
        input_evidence_status=evidence,
        year_coverage=_year_coverage(
            {
                "covered": y2024_ok and validation.ok,
                "source_data_year": 2024,
                "note": "federal 2024 inventory vs FEDERAL_TAX_RULES; historical RULE_YEAR",
            },
            {
                "covered": y2026_ok and validation.ok,
                "source_data_year": 2026,
                "note": "federal 2026 inventory vs FEDERAL_TAX_RULES",
            },
        ),
        extra={
            "rule_years_present": years,
            "validation_issues": validation.issues,
            "inventory_generated_at": payload.get("generated_at"),
            "live_currentness": live,
            "live_error": live_error,
        },
    )


def discover_state_tax() -> FreshnessCheck:
    from foundation.living_cost.evidence_validators import (
        state_tax_evidence_status,
        validate_state_tax_inventory,
    )
    from foundation.sources.state_tax import (
        discover_state_tax_live,
        evaluate_state_tax_freshness,
    )

    validation = validate_state_tax_inventory()
    evidence = state_tax_evidence_status()
    payload = validation.payload or {}
    artifacts = []
    for item in payload.get("retrieved_artifacts") or []:
        if not isinstance(item, dict) or not item.get("sha256"):
            continue
        artifacts.append(
            _artifact_record(
                artifact_id=str(item.get("filename") or item.get("key")),
                url=item.get("url"),
                sha256=item.get("sha256"),
                retrieved_at=item.get("retrieved_at"),
                validation_status="VALIDATED" if item.get("http_ok") else "UNAVAILABLE",
            )
        )
    try:
        live, live_error = discover_state_tax_live(payload)
    except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
        live, live_error = None, str(exc)
    status, newer, reason = evaluate_state_tax_freshness(
        inventory_valid=validation.ok,
        live=live,
        live_error=live_error,
    )
    if not validation.ok and status == "VERIFIED_CURRENT":
        status = "CHECK_FAILED"
        newer = None
        reason = f"Inventory is not family-validated: {validation.issues[:6]}"
    y2024 = int(payload.get("validated_2024_count") or 0)
    y2026 = int(payload.get("validated_2026_count") or 0)
    return FreshnessCheck(
        source_id="state_tax_law",
        latest_checked_at=_now_iso(),
        latest_authoritative_vintage_found=f"validated_cells_2024={y2024}/51 2026={y2026}/51",
        selected_vintage="2024 and 2026 RULE_YEAR official inventory",
        selected_artifact="living_cost_state_tax_inventory.json",
        newer_data_exists=newer,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status=status,
        publisher="State revenue departments / District of Columbia OTR",
        landing_url=None,
        selected_artifacts=tuple(artifacts),
        transformation_method="RULE_YEAR; field-level official artifact provenance; no MSLC",
        input_evidence_status=evidence,
        year_coverage=_year_coverage(
            {
                "covered": y2024 == 51 and validation.ok,
                "source_data_year": 2024,
                "note": "historical RULE_YEAR; family VALIDATED only if 51/51",
            },
            {
                "covered": y2026 == 51 and validation.ok,
                "source_data_year": 2026,
                "note": "current RULE_YEAR; family VALIDATED only if 51/51",
            },
        ),
        extra={"live_currentness": live, "live_error": live_error, "issues": validation.issues[:20]},
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
        year_coverage=_year_coverage(
            {"covered": False, "note": "most FIPS unresolved"},
            {"covered": False, "note": "most FIPS unresolved"},
        ),
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


def _od010_selected_artifacts(
    selected: str | None, *, observation_sha: str | None = None, raw_sha: str | None = None
) -> tuple[dict[str, Any], ...]:
    if not selected:
        return ()
    return (
        {
            "artifact_id": selected,
            "sha256": observation_sha or raw_sha,
            "observation_set_sha256": observation_sha,
            "raw_response_sha256": raw_sha,
        },
    )


def _od010_latest_target_label(coverage: dict[str, Any] | None) -> str | None:
    if not isinstance(coverage, dict):
        return None
    latest: tuple[int, str] | None = None
    latest_label: str | None = None
    from foundation.living_cost.od010_cpi import period_tuple_from_label

    for block in coverage.values():
        if not isinstance(block, dict):
            continue
        for rec in block.values():
            if not isinstance(rec, dict):
                continue
            label = rec.get("target_observation_period") or rec.get("latest_observation_period")
            key = period_tuple_from_label(str(label) if label else None)
            if key is None:
                continue
            if latest is None or key > latest:
                latest = key
                latest_label = str(label)
    return latest_label


def discover_od010() -> FreshnessCheck:
    """Live official BLS freshness. Cached table bytes are not VERIFIED_CURRENT."""
    from foundation.living_cost.candidate_bindings import (
        od010_series_inventory_is_specific,
        od010_translation_is_bound,
        unbound_od010_series_coverage,
        validate_od010_bindings_against_snapshot,
    )
    from foundation.living_cost.od010_cpi import (
        BLS_API_IDENTITY,
        BLS_CPI_LANDING,
        build_od010_records,
        load_od010_table,
        persisted_table_matches_live,
        retrieve_bls_cpi_series,
        write_od010_live_currentness,
        write_od010_retrieve,
    )

    checked = _now_iso()
    table_path = METADATA_DIR / "living_cost_od010_translation_table.json"
    persisted = load_od010_table()
    structural_bound = od010_translation_is_bound(table_path)

    try:
        retrieve = retrieve_bls_cpi_series()
        write_od010_retrieve(retrieve)
        live_table = build_od010_records(retrieve)
    except (
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
        KeyError,
        requests.RequestException,
    ) as exc:
        write_od010_live_currentness(
            {
                "freshness_check_status": "CHECK_FAILED",
                "currentness_status": "CHECK_FAILED",
                "translation_index_bound": False,
                "reason": f"live BLS retrieve failed: {exc}",
                "structural_table_bound": structural_bound,
            }
        )
        return FreshnessCheck(
            source_id="od010_price_index",
            latest_checked_at=checked,
            latest_authoritative_vintage_found=None,
            selected_vintage=None,
            selected_artifact=None,
            newer_data_exists=None,
            retrieval_validation_status="INVENTORY_NOT_VALIDATED",
            reason_if_not_refreshed=(
                "Live official BLS CPI request failed. Cached translation-table "
                "evidence is not marked VERIFIED_CURRENT. "
                f"{exc}"
            ),
            freshness_check_status="CHECK_FAILED",
            publisher="BLS",
            landing_url=BLS_CPI_LANDING,
            selected_artifacts=(),
            transformation_method="CPI_UPDATED target/base",
            input_evidence_status="INVENTORY_NOT_VALIDATED",
            listing_freshness_status="CHECK_FAILED",
            artifact_currentness_status="CHECK_FAILED",
            selected_artifact_matches_latest=None,
            year_coverage=_year_coverage(
                {"covered": False, "note": "live BLS retrieve failed"},
                {"covered": False, "note": "live BLS retrieve failed"},
            ),
            series_coverage=unbound_od010_series_coverage(),
            extra={
                "translation_table_bound": False,
                "structural_table_bound": structural_bound,
                "series_inventory_status": "NOT_INVENTORIED",
                "series_inventory_specific": False,
                "live_bls_request": "FAILED",
            },
        )

    live_coverage = live_table.get("series_coverage") or unbound_od010_series_coverage()
    live_obs_sha = live_table.get("observation_set_sha256")
    live_raw_sha = live_table.get("raw_response_sha256") or retrieve.get("raw_response_sha256")
    live_check = FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="BLS CPI-U official API",
        selected_vintage="BLS CPI-U official API",
        selected_artifact=BLS_API_IDENTITY,
        newer_data_exists=False,
        retrieval_validation_status="VALIDATED",
        freshness_check_status="VERIFIED_CURRENT",
        publisher="BLS",
        landing_url=BLS_CPI_LANDING,
        series_coverage=live_coverage,
    )
    specific = od010_series_inventory_is_specific(live_check)
    cross = validate_od010_bindings_against_snapshot(persisted, {"od010_price_index": live_check})
    matches, match_issues = persisted_table_matches_live(persisted, live_table)
    newer_issues = [item for item in match_issues if item.endswith("NEWER_TARGET_AVAILABLE")]
    live_latest = _od010_latest_target_label(live_coverage)
    table_latest = _od010_latest_target_label(
        persisted.get("series_coverage") if isinstance(persisted, dict) else None
    )

    if specific and matches and cross["ok"] is True and structural_bound:
        status = "VERIFIED_CURRENT"
        evidence = "VALIDATED"
        listing = "VERIFIED_CURRENT"
        artifact = "VERIFIED_CURRENT"
        match = True
        newer = False
        live_bound = True
        reason = (
            "Live official BLS CPI-U NSA request succeeded. Persisted translation "
            "table uses the same series, source years, base/target periods, values, "
            "and canonical observation identity. Target/base factors recompute."
        )
    elif specific and newer_issues:
        status = "NEWER_AVAILABLE"
        evidence = "VALIDATED"
        listing = "NEWER_AVAILABLE"
        artifact = "NEWER_AVAILABLE"
        match = False
        newer = True
        live_bound = False
        reason = (
            "Live official BLS request returned a newer target observation than "
            "the persisted translation table. translation_index_bound is false "
            "until the table is refreshed from the new official observations. "
            f"live={live_latest}; table={table_latest}."
        )
    else:
        status = "MANUAL_VERIFICATION_REQUIRED"
        evidence = "VALIDATED" if specific else "INVENTORY_NOT_VALIDATED"
        listing = "VERIFIED_CURRENT" if specific else None
        artifact = None
        match = False if persisted else None
        newer = False if specific and not newer_issues else None
        live_bound = False
        reason = (
            "Live official BLS inventory does not current-bind the persisted "
            f"translation table (specific={specific}, structural_bound={structural_bound}, "
            f"cross_ok={cross['ok']}, issues={match_issues[:8] or cross.get('issues')})."
        )

    write_od010_live_currentness(
        {
            "freshness_check_status": status,
            "currentness_status": status,
            "translation_index_bound": live_bound,
            "structural_table_bound": structural_bound,
            "live_bls_request": "SUCCEEDED",
            "raw_response_sha256": live_raw_sha,
            "observation_set_sha256": live_obs_sha,
            "table_observation_set_sha256": None
            if not isinstance(persisted, dict)
            else persisted.get("observation_set_sha256"),
            "live_latest_target_observation": live_latest,
            "table_target_observation": table_latest,
            "match_issues": match_issues,
            "cross_binding_ok": cross["ok"],
            "cross_binding_issues": cross.get("issues") or [],
        }
    )
    return FreshnessCheck(
        source_id="od010_price_index",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="BLS CPI-U official API",
        selected_vintage="BLS CPI-U official API" if specific else None,
        selected_artifact=BLS_API_IDENTITY,
        newer_data_exists=newer,
        retrieval_validation_status=evidence,
        reason_if_not_refreshed=reason,
        freshness_check_status=status,
        publisher="BLS",
        landing_url=BLS_CPI_LANDING,
        selected_artifacts=_od010_selected_artifacts(
            BLS_API_IDENTITY, observation_sha=live_obs_sha, raw_sha=live_raw_sha
        ),
        transformation_method="CPI_UPDATED target/base",
        input_evidence_status=evidence,
        listing_freshness_status=listing,
        artifact_currentness_status=artifact,
        selected_artifact_matches_latest=match,
        year_coverage=_year_coverage(
            {"covered": specific, "note": "live BLS OD-010 inventory"},
            {"covered": specific, "note": "live BLS OD-010 inventory"},
        ),
        series_coverage=live_coverage,
        extra={
            "translation_table_bound": live_bound,
            "structural_table_bound": structural_bound,
            "series_inventory_status": "INVENTORIED" if specific else "NOT_INVENTORIED",
            "series_inventory_specific": specific,
            "live_bls_request": "SUCCEEDED",
            "raw_response_sha256": live_raw_sha,
            "observation_set_sha256": live_obs_sha,
            "live_latest_target_observation": live_latest,
            "table_target_observation": table_latest,
        },
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
