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


USDA_WORKBOOK_FILENAMES: dict[str, str] = {
    "low_cost": "usda-lowcostplan-sept2007-present.xlsx",
    "thrifty": "usda-thriftyplan-june2021-present.xlsx",
    "alaska": "usda-alaska-june2023-present.xlsx",
    "hawaii": "usda-hawaii-june2023-present.xlsx",
}

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
    html = ""
    checked = ""
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
    # VERIFIED_CURRENT for 2026 only if selected 2026 months come from official rows
    # and are not a 2024 twelve-month substitution.
    hist_months = list(hist.get("months_included") or [])
    substituted = bool(current_months) and current_months == hist_months and len(hist_months) == 12
    current_ok = bool(current_months) and not substituted
    status = "VERIFIED_CURRENT" if current_ok else "CHECK_FAILED"
    return FreshnessCheck(
        source_id="usda_food",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="USDA official monthly archives (2024 historical; 2026 YTD)",
        selected_vintage="USDA Low-Cost official monthly archive; 2026 uses official YTD months",
        selected_artifact=USDA_WORKBOOK_FILENAMES["low_cost"],
        newer_data_exists=False if current_ok else None,
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=(
            "Official FNS Cost of Food archive page checked. "
            "Workbook URLs are parsed hrefs, not constructed hostnames. "
            "2024 historical months and 2026 YTD months are stored separately. "
            "2024 full-year months are not used as 2026 months."
        ),
        freshness_check_status=status,
        publisher="USDA Center for Nutrition Policy and Promotion",
        landing_url=landing,
        selected_artifacts=tuple(arts),
        transformation_method="adult 19-50 midpoint × official 1.20 one-person factor",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        months_included=tuple(current_months),
        month_count=len(current_months) or None,
        first_month=current_months[0] if current_months else None,
        last_month=current_months[-1] if current_months else None,
        extra={
            "historical_2024": hist,
            "current_2026": current,
            "official_hrefs": hrefs,
            "substituted_2024_for_2026": substituted,
        },
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
    if both_ok and newer:
        family_status = "NEWER_AVAILABLE"
    elif both_ok:
        family_status = "VERIFIED_CURRENT"
    else:
        family_status = "CHECK_FAILED"
    checked = sbe.get("checked_at") or federal.get("checked_at") or _now_iso()
    reason = (
        "Combined CMS family requires BOTH the federal Exchange PUF listing and the "
        "standalone SBE QHP PUF listing. SBE-FP states use the federal Exchange PUF "
        "and are not treated as standalone SBE archives. "
        f"federal={federal['status']}; sbe={sbe['status']}."
    )
    return FreshnessCheck(
        source_id="cms_marketplace_sbe",
        latest_checked_at=checked,
        latest_authoritative_vintage_found="PY2024 / PY2026 Exchange PUF + standalone SBE",
        selected_vintage="PY2024 / PY2026 federal Exchange PUF + year-specific standalone SBE",
        selected_artifact="cms_rate_puf / plan_puf / service_area_puf + SBE archives",
        newer_data_exists=newer if both_ok else None,
        retrieval_validation_status="MODELED_FROM_MEASURED_INPUTS",
        reason_if_not_refreshed=reason,
        freshness_check_status=family_status,
        publisher="Centers for Medicare & Medicaid Services",
        landing_url=CMS_PUF_LANDING,
        selected_artifacts=tuple(arts),
        transformation_method="lowest Silver age-40 join of federal PUF + year-specific SBE",
        input_evidence_status="MODELED_FROM_MEASURED_INPUTS",
        extra={"federal_exchange": federal, "sbe": sbe},
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
        extra={"primary_error": primary_err, "used_url": used_url},
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


def parse_naic_report_identifier(html: str) -> str | None:
    """Discover the latest Auto Insurance Database Report identifier from official HTML."""
    match = re.search(
        r"(20\d{2}\s*/\s*20\d{2}\s+Auto Insurance Database Report)",
        html,
        re.IGNORECASE,
    )
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    match = re.search(r"(Auto Insurance Database Report[^.<]{0,40})", html, re.IGNORECASE)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    if "auto insurance database" in html.lower():
        years = re.findall(r"20\d{2}", html)
        if years:
            return (
                f"Auto Insurance Database Report (years mentioned: {', '.join(sorted(set(years)))})"
            )
        return "Auto Insurance Database Report"
    return None


def discover_naic() -> FreshnessCheck:
    sidecar = _sidecar("publication-aut-pb-auto-insurance-database.pdf")
    landing = NAIC_PUBLICATIONS_LANDING
    art = _artifact_record(
        artifact_id="publication-aut-pb-auto-insurance-database.pdf",
        url=landing,
        sha256=(sidecar or {}).get("sha256"),
        retrieved_at=(sidecar or {}).get("retrieved_at"),
        validation_status="RETRIEVED_UNVALIDATED",
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
    identifier = parse_naic_report_identifier(html)
    if identifier is None:
        return _failed(
            "naic_auto_insurance",
            publisher="NAIC",
            landing_url=landing,
            evidence="RETRIEVED_UNVALIDATED",
            vintage="NAIC Auto Insurance Database Report",
            artifact="publication-aut-pb-auto-insurance-database.pdf",
            artifacts=[art],
            reason="NAIC Publications page retrieved but Auto Insurance Database Report was not identified.",
        )
    return FreshnessCheck(
        source_id="naic_auto_insurance",
        latest_checked_at=checked,
        latest_authoritative_vintage_found=identifier,
        selected_vintage=identifier,
        selected_artifact="publication-aut-pb-auto-insurance-database.pdf",
        newer_data_exists=False,
        retrieval_validation_status="RETRIEVED_UNVALIDATED",
        reason_if_not_refreshed=(
            "Official NAIC Publications listing checked. Latest report identifier parsed "
            "from the page (not hard-coded). PDF retrieve exists. "
            "State-table extraction is not a validated numeric series."
        ),
        freshness_check_status="VERIFIED_CURRENT",
        publisher="National Association of Insurance Commissioners",
        landing_url=landing,
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
