"""National Association of Insurance Commissioners (NAIC) Auto Insurance Adapter.

Ingests state-level average expenditure for personal automobile insurance (liability, comprehensive, collision).
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

NAIC_BASE_URL = "https://content.naic.org/research-actuarial-services/auto-insurance-database-report"


def parse_naic_auto_insurance_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse NAIC state auto insurance average expenditure dataset."""
    if not file_path.exists():
        raise FileNotFoundError(f"NAIC auto insurance file not found: {file_path}")

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
            state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
            prem_str = row.get("average_annual_premium") or row.get("combined_expenditure") or row.get("premium") or "0"
            try:
                annual_prem = float(str(prem_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if annual_prem <= 0:
                continue

            obs = LivingCostComponentObservation(
                component_id="transport_auto_insurance",
                category="transportation",
                geography_type="state",
                geography_id=state_alpha,
                geography_name=f"{state_alpha} Auto Insurance",
                state=state_alpha,
                reference_year=reference_year,
                value_annual=round(annual_prem, 2),
                value_monthly=round(annual_prem / 12.0, 2),
                unit="USD",
                status=ComponentStatus.MEASURED,
                source_id=f"naic_auto_ins_{reference_year}",
                source_variable="combined_average_expenditure",
                source_url=NAIC_BASE_URL,
                source_release=f"NAIC Auto Insurance Database Report ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"NAIC average annual private passenger automobile insurance expenditure in {state_alpha}.",
            )
            observations.append(obs)

    return observations
