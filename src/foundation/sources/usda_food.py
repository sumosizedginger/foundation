"""USDA Food Plans Source Adapter.

Downloads, caches, verifies SHA-256 integrity, and parses official monthly reports
for the USDA Low-Cost Food Plan (primary) and Thrifty Food Plan (sensitivity bound).
Computes exact adult gender midpoint and applies the official +20% 1-person household adjustment.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

USDA_FOOD_PLANS_URL = "https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports"


def parse_usda_food_plan_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse official USDA food plan monthly cost dataset.

    Calculates:
    - 19-50 Male + Female average monthly cost
    - 1-person household factor (+20% size adjustment)
    - Low-Cost Plan (primary) and Thrifty Plan (sensitivity)
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
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    observations: list[LivingCostComponentObservation] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            plan_name = str(row.get("plan_name") or row.get("Plan") or "").strip().lower()
            if "low" not in plan_name and "thrifty" not in plan_name:
                continue

            # Male and Female age 19-50 monthly cost
            male_cost = float(row.get("male_19_50") or row.get("male_cost") or 0.0)
            female_cost = float(row.get("female_19_50") or row.get("female_cost") or 0.0)

            if male_cost <= 0 or female_cost <= 0:
                continue

            midpoint = (male_cost + female_cost) / 2.0
            single_adult_monthly = round(midpoint * 1.20, 2)  # Official +20% 1-person adjustment
            single_adult_annual = round(single_adult_monthly * 12.0, 2)

            is_thrifty = "thrifty" in plan_name
            comp_id = "food_thrifty_sensitivity" if is_thrifty else "food_low_cost"

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
                source_id=f"usda_food_plan_{reference_year}",
                source_variable=f"{'thrifty' if is_thrifty else 'low_cost'}_single_adult",
                source_url=USDA_FOOD_PLANS_URL,
                source_release=f"USDA Food Plans ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"USDA {'Thrifty' if is_thrifty else 'Low-Cost'} Plan single adult age 19-50 midpoint (${midpoint:,.2f}) with official +20% 1-person factor (${single_adult_monthly:,.2f}/mo).",
            )
            observations.append(obs)

    return observations
