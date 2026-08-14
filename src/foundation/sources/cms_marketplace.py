"""CMS Health Insurance Marketplace Source Adapter.

Ingests and parses official CMS Marketplace Public Use Files (PUF) for Federally-facilitated
Marketplaces (FFM) and official State-Based Exchange (SBE) public rate files to deterministically
select the Lowest-Cost Adequate Silver Plan for an independent single adult (Age 40, non-tobacco).

LOWEST-COST ADEQUATE SILVER SELECTION CRITERIA:
1. Standard individual-market major medical plan (HMO, PPO, EPO, POS) covering Essential Health Benefits.
2. Metal Level = "Silver" (70% actuarial value benchmark).
3. Excludes: Catastrophic plans, dental-only, vision-only, child-only, and non-ACA indemnity plans.
4. Profile: Single adult age 40, non-smoker / standard non-tobacco rate.
5. Geography: Validated plan availability in the specific rating area.
6. Pricing: 100% unsubsidized gross premium (zero ACA Advance Premium Tax Credits).
7. Deterministic Tie-Breaker:
   - Primary: Lowest monthly unsubsidized premium ($/mo).
   - Secondary: Lower medical in-network individual deductible.
   - Tertiary: Alphabetical Plan ID (StandardComponentId) ascending.
"""

from __future__ import annotations

import csv
import io
import logging
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

CMS_PUF_LANDING = "https://www.cms.gov/marketplace/resources/data/public-use-files"
CMS_SBE_PUF_LANDING = "https://www.cms.gov/marketplace/resources/data/state-based-public-use-files"

CMS_PUF_SLUGS = {
    "rate_puf": "rate-puf",
    "plan_attributes_puf": "plan-attributes-puf",
    "service_area_puf": "service-area-puf",
    "benefits_puf": "benefits-and-cost-sharing-puf",
}

CMS_PUF_URLS: dict[int, dict[str, str]] = {
    year: {
        key: f"https://download.cms.gov/marketplace-puf/{year}/{slug}.zip"
        for key, slug in CMS_PUF_SLUGS.items()
    }
    for year in (2024, 2026)
}


def download_cms_marketplace_artifacts(
    year: int, cache_dir: Path, force_download: bool = False
) -> dict[str, Any]:
    """Download required CMS PUFs for a given year."""
    if year not in CMS_PUF_URLS:
        raise ValueError(f"Unsupported CMS PUF reference year: {year}")

    config = CMS_PUF_URLS[year]
    cache_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {}
    for puf_type, url in config.items():
        artifact = acquire_source(
            source_id=f"cms_{puf_type}_{year}",
            url=url,
            cache_dir=cache_dir,
            expected_filename=f"cms_{year}_{puf_type}.zip",
            force_download=force_download,
        )
        if artifact is None:
            raise RuntimeError(f"Required CMS PUF {puf_type} for {year} is UNAVAILABLE.")
        artifacts[puf_type] = artifact

    return artifacts


# Year-specific standalone SBE states. Do not copy 2024 onto 2026 or vice versa.
# Federal-platform PUF files include FFE + SBE-FP only.
SBE_STANDALONE_STATES: dict[int, frozenset[str]] = {
    2024: frozenset(
        {
            "CA",
            "CO",
            "CT",
            "DC",
            "ID",
            "KY",
            "ME",
            "MD",
            "MA",
            "MN",
            "NV",
            "NM",
            "NY",
            "PA",
            "RI",
            "VT",
            "WA",
        }
    ),
    2026: frozenset(
        {
            "CA",
            "CO",
            "CT",
            "DC",
            "ID",
            "KY",
            "ME",
            "MD",
            "MA",
            "MN",
            "NV",
            "NM",
            "NY",
            "PA",
            "RI",
            "VT",
            "WA",
        }
    ),
}

SBE_QHP_ZIP: dict[int, str] = {
    2024: "https://download.cms.gov/marketplace-puf/2024/sbe-puf-files-2024.zip",
    2026: "https://download.cms.gov/marketplace-puf/2026/sbe-puf-files-2026.zip",
}


def download_cms_sbe_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official CMS SBE QHP PUF zip if published. Dictionaries-only zips fail closed."""
    if year not in SBE_QHP_ZIP:
        raise ValueError(f"Unsupported CMS SBE reference year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = acquire_source(
        source_id=f"cms_sbe_puf_{year}",
        url=SBE_QHP_ZIP[year],
        cache_dir=cache_dir,
        expected_filename=f"sbe-puf-files-{year}.zip",
        force_download=force_download,
    )
    if artifact is None:
        return record_unretrieved(
            f"cms_sbe_puf_{year}",
            status="SOURCE_GAP",
            resolved_url=CMS_SBE_PUF_LANDING,
            notes=(
                f"Official year-specific SBE QHP PUF zip for {year} was not retrieved. "
                "Do not infer 2024 SBE coverage from 2026 or vice versa."
            ),
        )
    path = cache_dir / artifact.local_cache_filename
    csv_members = 0
    if path.is_file():
        try:
            with zipfile.ZipFile(path) as archive:
                csv_members = sum(1 for name in archive.namelist() if name.lower().endswith(".csv"))
        except zipfile.BadZipFile:
            csv_members = 0
    if csv_members == 0:
        from dataclasses import replace

        return replace(
            artifact,
            validation_status="SOURCE_GAP",
            notes=(
                f"SBE archive {path.name} contains documentation only "
                f"({csv_members} CSV members). Rate/plan/service-area data for "
                f"standalone SBE states in {year} remain a source gap."
            ),
        )
    return artifact


def _open_puf_table(path: Path) -> Iterator[dict[str, str]]:
    """Yield rows from a CMS PUF CSV or a zip that contains one CSV."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            members = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if not members:
                return
            with archive.open(members[0]) as raw:
                yield from csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                )
        return
    with path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        yield from csv.DictReader(fh)


def _puf_path(cache_dir: Path, year: int, puf_type: str) -> Path | None:
    zip_path = cache_dir / f"cms_{year}_{puf_type}.zip"
    csv_path = cache_dir / f"cms_{year}_{puf_type}.csv"
    if zip_path.exists():
        return zip_path
    if csv_path.exists():
        return csv_path
    return None


def parse_cms_marketplace_multi_puf(
    year: int,
    cache_dir: Path,
) -> list[LivingCostComponentObservation]:
    """Join Plan Attributes, Benefits, and Rates PUFs to select Lowest-Cost Adequate Silver."""
    config = CMS_PUF_URLS.get(year)
    if not config:
        raise ValueError(f"Unsupported CMS PUF reference year: {year}")

    rate_file = _puf_path(cache_dir, year, "rate_puf")
    plan_file = _puf_path(cache_dir, year, "plan_attributes_puf")
    service_file = _puf_path(cache_dir, year, "service_area_puf")
    benefits_file = _puf_path(cache_dir, year, "benefits_puf")

    if rate_file is None or plan_file is None or benefits_file is None:
        logger.warning(f"CMS PUF files missing for {year}, returning empty list.")
        return []

    # 1. Parse Plan Attributes to find valid Silver major medical plans and their deductibles.
    # We map PlanId -> { "deductible": float, "metal": "Silver" }
    valid_plans: dict[str, dict[str, Any]] = {}
    for row in _open_puf_table(plan_file):
        metal = str(row.get("MetalLevel", "")).strip().lower()
        if metal != "silver":
            continue

        plan_type = str(row.get("PlanType", "")).strip().upper()
        if "DENTAL" in plan_type or "CATASTROPHIC" in plan_type:
            continue

        market_cov = str(row.get("MarketCoverage", "")).strip().upper()
        if market_cov == "SHOP":  # Exclude small business
            continue

        plan_id = str(row.get("StandardComponentId", "")).strip()
        if not plan_id:
            continue

        ded_str = row.get("TEHBDedInnTier1Individual", "")
        try:
            # E.g. "$5,000" or "Not Applicable"
            ded = float(str(ded_str).replace("$", "").replace(",", "").strip())
        except ValueError:
            ded = None

        if ded is None:
            continue  # Missing deductible means it fails closed for 'adequate' tie-breaker

        service_area_id = str(row.get("ServiceAreaId") or "").strip()
        issuer_id = str(row.get("IssuerId") or "").strip()
        if not service_area_id or not issuer_id:
            continue  # Fail closed: cannot join to service geography.
        valid_plans[plan_id] = {
            "deductible": ded,
            "metal": "Silver",
            "service_area_id": service_area_id,
            "issuer_id": issuer_id,
            "state": str(row.get("StateCode") or "").strip().upper(),
        }

    benefit_plan_ids: set[str] = set()
    for row in _open_puf_table(benefits_file):
        dental = str(row.get("DentalOnlyPlan") or "").strip().lower()
        if dental in {"yes", "y", "true", "1"}:
            continue
        bid = str(row.get("StandardComponentId") or row.get("PlanId") or "").strip()[:14]
        if bid:
            benefit_plan_ids.add(bid)
    if not benefit_plan_ids:
        logger.warning("CMS Benefits PUF produced no join keys for %s", year)
        return []
    valid_plans = {pid: meta for pid, meta in valid_plans.items() if pid in benefit_plan_ids}
    if not valid_plans:
        logger.warning("CMS Benefits join removed every Silver plan for %s", year)
        return []

    service_keys: set[tuple[str, str, str]] = set()
    if service_file is not None:
        for row in _open_puf_table(service_file):
            dental = str(row.get("DentalOnlyPlan") or "").strip().lower()
            if dental in {"yes", "y", "true", "1"}:
                continue
            issuer_id = str(row.get("IssuerId") or "").strip()
            service_area_id = str(row.get("ServiceAreaId") or "").strip()
            state_alpha = str(row.get("StateCode") or "").strip().upper()
            if not issuer_id or not service_area_id or not state_alpha:
                continue
            cover_state = str(row.get("CoverEntireState") or "").strip().lower()
            county = str(row.get("County") or "").strip()
            if cover_state not in {"yes", "y", "true", "1"} and not county:
                continue
            service_keys.add((state_alpha, issuer_id, service_area_id))

    # 2. Parse Rates PUF for Age 40, non-tobacco, joining against valid_plans
    candidates_by_area: dict[tuple[str, str], list[dict[str, Any]]] = {}

    for row in _open_puf_table(rate_file):
        age = str(row.get("Age", "")).strip()
        if age != "40" and age != "Age 40":
            continue

        tobacco = str(row.get("Tobacco", "")).strip().upper()
        if "TOBACCO" in tobacco and "NON" not in tobacco:
            # We want standard or non-tobacco rates only
            continue

        plan_id = str(row.get("PlanId", "")).strip()
        # The rate PUF PlanId is often 14 chars. StandardComponentId is 14 chars.
        base_plan_id = plan_id[:14] if len(plan_id) >= 14 else plan_id

        if base_plan_id not in valid_plans:
            continue

        plan_meta = valid_plans[base_plan_id]
        if service_keys:
            join_key = (
                str(row.get("StateCode") or "").strip().upper() or plan_meta["state"],
                plan_meta["issuer_id"],
                plan_meta["service_area_id"],
            )
            if join_key not in service_keys:
                continue

        rating_area = str(row.get("RatingAreaId", "")).strip()
        state_alpha = str(row.get("StateCode", "")).strip().upper()

        if not state_alpha or not rating_area:
            continue  # Fail closed on missing geography

        rate_str = row.get("IndividualRate", "0")
        try:
            monthly_prem = float(str(rate_str).replace("$", "").replace(",", "").strip())
        except ValueError:
            continue

        if monthly_prem <= 0:
            continue

        deductible = valid_plans[base_plan_id]["deductible"]

        key = (state_alpha, rating_area)
        candidates_by_area.setdefault(key, []).append(
            {
                "plan_id": plan_id,
                "monthly_premium": monthly_prem,
                "deductible": deductible,
                "state": state_alpha,
                "rating_area": rating_area,
            }
        )

    observations: list[LivingCostComponentObservation] = []

    # 3. Deterministic Selection
    for (state_alpha, rating_area), candidates in sorted(candidates_by_area.items()):
        # Sort by: (1) monthly_premium asc, (2) deductible asc, (3) plan_id asc
        sorted_candidates = sorted(
            candidates, key=lambda c: (c["monthly_premium"], c["deductible"], c["plan_id"])
        )
        selected = sorted_candidates[0]
        annual_prem = round(selected["monthly_premium"] * 12.0, 2)
        geo_id = f"{state_alpha}_{rating_area.replace(' ', '_')}"

        obs = LivingCostComponentObservation(
            component_id="healthcare_silver_unsubsidized",
            category="healthcare",
            geography_type="rating_area",
            geography_id=geo_id,
            geography_name=f"{state_alpha} {rating_area}",
            state=state_alpha,
            reference_year=year,
            value_annual=annual_prem,
            value_monthly=round(selected["monthly_premium"], 2),
            unit="USD",
            status=ComponentStatus.MEASURED,
            source_id=f"cms_rate_puf_{year}",
            source_variable="IndividualRate_Age40_Silver_Adequate",
            source_url=config["rate_puf"],
            source_release=f"CMS Marketplace PUF ({year})",
            source_reference_period=str(year),
            retrieved_at="",  # Will be populated by pipeline artifact tracker
            source_artifact_sha256="",  # Will be populated by pipeline artifact tracker
            methodology_version="0.2.0-draft",
            notes=(
                f"Lowest-Cost Adequate Silver Plan: {selected['plan_id']} "
                f"(${selected['monthly_premium']:,.2f}/mo, Deductible: ${selected['deductible']:,.0f}) "
                f"in {state_alpha} {rating_area}."
            ),
        )
        observations.append(obs)

    return observations
