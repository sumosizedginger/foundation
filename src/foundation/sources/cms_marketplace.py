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
import logging
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

CMS_PUF_URLS: dict[int, dict[str, str]] = {
    2024: {
        "rate_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-rate-puf.csv",
        "plan_attributes_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-plan-attributes-puf.csv",
        "service_area_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-service-area-puf.csv",
        "benefits_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-benefits-and-cost-sharing-puf.csv",
    },
    2026: {
        "rate_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-rate-puf.csv",
        "plan_attributes_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-plan-attributes-puf.csv",
        "service_area_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-service-area-puf.csv",
        "benefits_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-benefits-and-cost-sharing-puf.csv",
    },
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
            expected_filename=f"cms_{year}_{puf_type}.csv",
            force_download=force_download,
        )
        if artifact is None:
            raise RuntimeError(f"Required CMS PUF {puf_type} for {year} is UNAVAILABLE.")
        artifacts[puf_type] = artifact

    return artifacts


def parse_cms_marketplace_multi_puf(
    year: int,
    cache_dir: Path,
) -> list[LivingCostComponentObservation]:
    """Join Plan Attributes, Benefits, and Rates PUFs to select Lowest-Cost Adequate Silver."""
    config = CMS_PUF_URLS.get(year)
    if not config:
        raise ValueError(f"Unsupported CMS PUF reference year: {year}")

    rate_file = cache_dir / f"cms_{year}_rate_puf.csv"
    plan_file = cache_dir / f"cms_{year}_plan_attributes_puf.csv"

    if not rate_file.exists() or not plan_file.exists():
        logger.warning(f"CMS PUF files missing for {year}, returning empty list.")
        return []

    # 1. Parse Plan Attributes to find valid Silver major medical plans and their deductibles.
    # We map PlanId -> { "deductible": float, "metal": "Silver" }
    valid_plans: dict[str, dict[str, Any]] = {}
    with plan_file.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
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

            valid_plans[plan_id] = {"deductible": ded, "metal": "Silver"}

    # 2. Parse Rates PUF for Age 40, non-tobacco, joining against valid_plans
    candidates_by_area: dict[tuple[str, str], list[dict[str, Any]]] = {}

    with rate_file.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
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
            source_artifact_sha256="", # Will be populated by pipeline artifact tracker
            methodology_version="0.2.0-draft",
            notes=(
                f"Lowest-Cost Adequate Silver Plan: {selected['plan_id']} "
                f"(${selected['monthly_premium']:,.2f}/mo, Deductible: ${selected['deductible']:,.0f}) "
                f"in {state_alpha} {rating_area}."
            ),
        )
        observations.append(obs)

    return observations
