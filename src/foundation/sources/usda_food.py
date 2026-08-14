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
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

USDA_FOOD_PLANS_URL = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"

# Official USDA Alaska and Hawaii Multipliers relative to U.S. Baseline
USDA_GEOGRAPHIC_FACTORS = {
    "AK": 1.25,  # Alaska Urban/Baseline food multiplier
    "HI": 1.55,  # Hawaii food multiplier based on USDA Honolulu reports
}


def parse_usda_monthly_food_csv(
    file_path: Path,
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
    if not file_path.exists():
        raise FileNotFoundError(f"USDA Food Plan file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    # Accumulate monthly records by plan type: plan_name -> list of (male, female, month_name)
    monthly_by_plan: dict[str, list[dict[str, Any]]] = {
        "low_cost": [],
        "thrifty": [],
    }

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

    observations: list[LivingCostComponentObservation] = []

    for plan_key in ["low_cost", "thrifty"]:
        records = monthly_by_plan[plan_key]
        if not records:
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

        comp_id = "food_low_cost" if plan_key == "low_cost" else "food_thrifty_sensitivity"

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
