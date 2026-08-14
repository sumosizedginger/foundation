"""BLS Consumer Expenditure (CE) Survey Source Adapter.

Calculates weighted lower-quartile (P25) expenditures for single-person consumer units
covering restricted necessity goods (apparel, personal care, housekeeping) and modest recreation.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

BLS_CE_BASE_URL = "https://www.bls.gov/cex/"


def parse_bls_ce_single_adult_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse BLS CE single-person consumer unit expenditure dataset."""
    if not file_path.exists():
        raise FileNotFoundError(f"BLS CE file not found: {file_path}")

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
            category = str(row.get("category") or "").strip().lower()
            p25_val = float(row.get("p25_expenditure") or row.get("expenditure_annual") or 0.0)
            if p25_val <= 0:
                continue

            comp_id = "essentials_basket" if "essential" in category or "apparel" in category else "social_recreation"

            obs = LivingCostComponentObservation(
                component_id=comp_id,
                category="essentials" if comp_id == "essentials_basket" else "social_recreation",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=round(p25_val, 2),
                value_monthly=round(p25_val / 12.0, 2),
                unit="USD",
                status=ComponentStatus.MEASURED,
                source_id=f"bls_ce_table1400_{reference_year}",
                source_variable=f"single_person_p25_{category}",
                source_url=BLS_CE_BASE_URL,
                source_release=f"BLS Consumer Expenditure Survey Table 1400 ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"BLS CE weighted P25 expenditure among single-person positive-spending consumer units for {category}.",
            )
            observations.append(obs)

    return observations
