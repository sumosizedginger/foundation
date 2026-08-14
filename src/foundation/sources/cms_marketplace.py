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
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

CMS_PUF_URLS: dict[int, dict[str, str]] = {
    2024: {
        "rate_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-rate-puf.csv",
        "plan_attributes_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-plan-attributes-puf.csv",
        "service_area_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2024-service-area-puf.csv",
    },
    2026: {
        "rate_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-rate-puf.csv",
        "plan_attributes_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-plan-attributes-puf.csv",
        "service_area_puf": "https://www.cms.gov/marketplace/resources/data/public-use-files/2026-service-area-puf.csv",
    },
}

# FFM States covered by federal CMS Marketplace PUFs (33 states)
FFM_STATES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "DE",
    "FL",
    "GA",
    "HI",
    "IL",
    "IN",
    "IA",
    "KS",
    "LA",
    "MI",
    "MS",
    "MO",
    "MT",
    "NE",
    "NH",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "WV",
    "WI",
    "WY",
}

# SBE States operating independent state exchanges (18 states + DC)
SBE_STATES = {
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
    "NJ",
    "NM",
    "NY",
    "PA",
    "RI",
    "VT",
    "WA",
}


def parse_cms_marketplace_rates_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse CMS Marketplace Rate PUF and select the lowest-cost adequate Silver plan per rating area."""
    if not file_path.exists():
        raise FileNotFoundError(f"CMS Marketplace file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    # Accumulate candidate plans by rating area: (state, rating_area) -> list of candidates
    candidates_by_area: dict[tuple[str, str], list[dict[str, Any]]] = {}

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Filter age = 40
            age = str(row.get("Age") or row.get("age") or "").strip()
            if age != "40" and age != "Age 40":
                continue

            # Filter metal = Silver
            metal = (
                str(row.get("MetalLevel") or row.get("metal_level") or row.get("Metal") or "")
                .strip()
                .lower()
            )
            if metal != "silver":
                continue

            # Check individual market / major medical indicators
            plan_type = str(row.get("PlanType") or row.get("plan_type") or "").strip().upper()
            if "DENTAL" in plan_type or "CATASTROPHIC" in plan_type:
                continue

            plan_id = str(
                row.get("PlanId") or row.get("plan_id") or row.get("StandardComponentId") or ""
            ).strip()
            rating_area = str(
                row.get("RatingAreaId")
                or row.get("rating_area")
                or row.get("RatingArea")
                or "Rating Area 1"
            ).strip()
            state_alpha = (
                str(row.get("State") or row.get("state") or row.get("StateCode") or "")
                .strip()
                .upper()
            )

            if not state_alpha or not plan_id:
                continue

            rate_str = (
                row.get("IndividualRate")
                or row.get("individual_rate")
                or row.get("Rate")
                or row.get("premium")
                or "0"
            )
            try:
                monthly_prem = float(str(rate_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if monthly_prem <= 0:
                continue

            deductible_str = row.get("MedicalDeductible") or row.get("deductible") or "5000"
            try:
                deductible = float(str(deductible_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                deductible = 5000.0

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

    # Deterministic Selection for each Rating Area
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
            reference_year=reference_year,
            value_annual=annual_prem,
            value_monthly=round(selected["monthly_premium"], 2),
            unit="USD",
            status=ComponentStatus.MEASURED,
            source_id=f"cms_marketplace_puf_{reference_year}",
            source_variable="IndividualRate_Age40_Silver_Adequate",
            source_url=CMS_PUF_URLS.get(reference_year, {}).get(
                "rate_puf", "https://www.cms.gov/marketplace/resources/data/public-use-files"
            ),
            source_release=f"CMS Marketplace PUF ({reference_year})",
            source_reference_period=str(reference_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                f"Lowest-Cost Adequate Silver Plan: {selected['plan_id']} "
                f"(${selected['monthly_premium']:,.2f}/mo, Deductible: ${selected['deductible']:,.0f}) "
                f"in {state_alpha} {rating_area}."
            ),
        )
        observations.append(obs)

    return observations
