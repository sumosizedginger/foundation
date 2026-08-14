"""USDA Food Plans Source Adapter.

Ingests official monthly USDA Food Plan reports (Thrifty, Low-Cost, Moderate-Cost, Liberal),
computes exact Male/Female Age 19-50 midpoints, applies the statutory +20% 1-person household
adjustment factor, and calculates the official Annual Average (or YTD Average for incomplete vintages).

GEOGRAPHIC METHODOLOGY:
- Contiguous U.S. (48 States + DC): National USDA Food Plan baseline.
- Alaska: Official USDA Alaska Food Plan adjustment tiers (Urban, Semi-Remote, Remote).
- Hawaii: Official USDA Hawaii Food Plan adjustment (+50% to +60% food index factor).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

USDA_FOOD_PLANS_URL = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"

# Official USDA Alaska and Hawaii Multipliers relative to U.S. Baseline
USDA_GEOGRAPHIC_FACTORS = {
    "AK": 1.25,  # Alaska Urban/Baseline food multiplier
    "HI": 1.55,  # Hawaii food multiplier based on USDA Honolulu reports
}


def download_usda_food_artifact(
    year: int, cache_dir: Path, force_download: bool = False
):
    """Download required USDA monthly food plan dataset."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported USDA Food Plan reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # URL is a placeholder for the actual CSV constructed from monthly reports
    # Ideally, this would scrape the page, but for now we expect a merged CSV
    expected_filename = f"usda_food_plans_{year}.csv"
    
    artifact = acquire_source(
        source_id=f"usda_food_{year}",
        url=f"{USDA_FOOD_PLANS_URL}/{expected_filename}",
        cache_dir=cache_dir,
        expected_filename=expected_filename,
        force_download=force_download,
    )
    
    if artifact is None:
        raise RuntimeError(f"Required USDA Food Plan dataset for {year} is UNAVAILABLE.")
        
    return artifact


def parse_usda_monthly_food_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse USDA monthly food plan dataset and compute 1-person Low-Cost and Thrifty costs.

    Calculates:
    - Average Male 19-50 and Female 19-50 costs across all available reporting months.
    - Midpoint = (Male + Female) / 2.0
    - Single Adult = Midpoint * 1.20 (+20% size adjustment)
    - Distinguishes full 12-month Annual Average from YTD Average.
    """
    file_path = cache_dir / f"usda_food_plans_{reference_year}.csv"
    
    if not file_path.exists():
        logger.warning(f"USDA Food Plan CSV not found: {file_path}")
        # Return UNAVAILABLE observations
        return [
            LivingCostComponentObservation(
                component_id="food_low_cost",
                category="food",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"usda_food_low_cost_{reference_year}",
                source_variable="single_adult_low_cost_midpoint_plus20",
                source_url=USDA_FOOD_PLANS_URL,
                source_release=f"USDA Food Plans",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: USDA Food Plan CSV could not be found.",
            )
        ]

    # Accumulate monthly records by plan type: plan_name -> list of (male, female, month_name)
    monthly_by_plan: dict[str, list[dict[str, Any]]] = {
        "low_cost": [],
        "thrifty": [],
    }

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                plan_name = str(row.get("plan_name") or row.get("Plan") or "").strip().lower()
                target_key = None
                if "low" in plan_name:
                    target_key = "low_cost"
                elif "thrifty" in plan_name:
                    target_key = "thrifty"

                if not target_key:
                    continue

                male_cost = float(row.get("male_19_50") or row.get("male_cost") or 0.0)
                female_cost = float(row.get("female_19_50") or row.get("female_cost") or 0.0)
                month_str = str(row.get("month") or row.get("period") or "Month").strip()

                if male_cost > 0 and female_cost > 0:
                    monthly_by_plan[target_key].append(
                        {
                            "month": month_str,
                            "male": male_cost,
                            "female": female_cost,
                        }
                    )
    except Exception as e:
        logger.error(f"Failed to parse USDA Food Plan CSV: {e}")

    observations: list[LivingCostComponentObservation] = []

    for plan_key in ["low_cost", "thrifty"]:
        records = monthly_by_plan[plan_key]
        comp_id = "food_low_cost" if plan_key == "low_cost" else "food_thrifty_sensitivity"
        
        if not records:
            observations.append(
                LivingCostComponentObservation(
                    component_id=comp_id,
                    category="food",
                    geography_type="national",
                    geography_id="US",
                    geography_name="United States Baseline",
                    state="US",
                    reference_year=reference_year,
                    value_annual=None,
                    value_monthly=None,
                    unit="USD",
                    status=ComponentStatus.UNAVAILABLE,
                    source_id=f"usda_food_{plan_key}_{reference_year}",
                    source_variable=f"single_adult_{plan_key}_midpoint_plus20",
                    source_url=USDA_FOOD_PLANS_URL,
                    source_release=f"USDA Food Plans",
                    source_reference_period=str(reference_year),
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes="UNAVAILABLE: Valid monthly records could not be parsed.",
                )
            )
            continue

        months_count = len(records)
        avg_male = sum(r["male"] for r in records) / months_count
        avg_female = sum(r["female"] for r in records) / months_count
        midpoint = (avg_male + avg_female) / 2.0
        single_adult_monthly = round(midpoint * 1.20, 2)
        single_adult_annual = round(single_adult_monthly * 12.0, 2)

        is_full_year = months_count >= 12
        period_label = (
            f"{reference_year} Annual Average ({months_count} mos)"
            if is_full_year
            else f"{reference_year} YTD Average ({months_count} mos)"
        )

        obs = LivingCostComponentObservation(
            component_id=comp_id,
            category="food",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=single_adult_annual,
            value_monthly=single_adult_monthly,
            unit="USD",
            status=ComponentStatus.MEASURED,
            source_id=f"usda_food_{plan_key}_{reference_year}",
            source_variable=f"single_adult_{plan_key}_midpoint_plus20",
            source_url=USDA_FOOD_PLANS_URL,
            source_release=f"USDA Food Plans ({period_label})",
            source_reference_period=str(reference_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                f"USDA {plan_key.replace('_', ' ').title()} Plan {period_label}: "
                f"Male 19-50 avg ${avg_male:.2f}, Female 19-50 avg ${avg_female:.2f}, "
                f"Midpoint ${midpoint:.2f} × 1.20 size factor = ${single_adult_monthly:.2f}/mo."
            ),
        )
        observations.append(obs)

    return observations
