"""CMS Health Insurance Marketplace Public Use Files (PUF) Adapter.

Ingests and parses lowest-cost adequate Silver plan premiums for single adults age 40 (non-smoker)
across CMS Federally-facilitated Marketplace (FFM) and State-based Exchange (SBE) rating areas.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

CMS_PUF_BASE_URL = "https://www.cms.gov/marketplace/resources/data/public-use-files"


def parse_cms_marketplace_rates_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse real CMS Individual Market Rate PUF CSV file for Age 40 Silver plans."""
    if not file_path.exists():
        raise FileNotFoundError(f"CMS Marketplace file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    observations: list[LivingCostComponentObservation] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Filter for Age 40 and Silver metal level
            age = str(row.get("Age") or row.get("age") or "").strip()
            if age != "40" and age != "Age 40":
                continue

            metal = str(row.get("MetalLevel") or row.get("metal_level") or row.get("Metal") or "").strip().lower()
            if metal != "silver":
                continue

            plan_id = row.get("PlanId") or row.get("plan_id") or row.get("StandardComponentId") or ""
            rating_area = row.get("RatingAreaId") or row.get("rating_area") or row.get("RatingArea") or ""
            state_alpha = row.get("State") or row.get("state") or row.get("StateCode") or ""

            rate_str = row.get("IndividualRate") or row.get("individual_rate") or row.get("Rate") or row.get("premium") or "0"
            try:
                monthly_prem = float(str(rate_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if monthly_prem <= 0:
                continue

            annual_prem = round(monthly_prem * 12.0, 2)
            geo_id = f"{state_alpha}_{rating_area}" if rating_area else state_alpha

            obs = LivingCostComponentObservation(
                component_id="healthcare_silver_unsubsidized",
                category="healthcare",
                geography_type="state" if not rating_area else "rating_area",
                geography_id=geo_id,
                geography_name=f"{state_alpha} {rating_area}".strip(),
                state=state_alpha,
                reference_year=reference_year,
                value_annual=annual_prem,
                value_monthly=round(monthly_prem, 2),
                unit="USD",
                status=ComponentStatus.MEASURED,
                source_id=f"cms_marketplace_puf_{reference_year}",
                source_variable="IndividualRate_Age40_Silver",
                source_url=f"{CMS_PUF_BASE_URL}/{reference_year}",
                source_release=f"CMS Marketplace PUF ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"Unsubsidized Silver plan premium for single non-smoker age 40 (Plan ID: {plan_id}).",
            )
            observations.append(obs)

    return observations
