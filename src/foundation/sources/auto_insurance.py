"""National Association of Insurance Commissioners (NAIC) Auto Insurance Adapter.

Ingests state-level average expenditure for private passenger automobile insurance from official
NAIC Auto Insurance Database Reports.

METHODOLOGICAL DISTINCTIONS:
- Metric: Combined Average Expenditure (Liability + Comprehensive + Collision) per insured vehicle.
- Source Frequency: Biennial/triennial official NAIC releases (e.g. 2021/2022 survey data published in 2024).
- Temporal Rule: Real source vintage year is stored explicitly. If a 2026 survey is not yet published,
  the component reports the last validated observation with explicit vintage metadata.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

NAIC_BASE_URL = (
    "https://content.naic.org/research-actuarial-services/auto-insurance-database-report"
)


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
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    observations: list[LivingCostComponentObservation] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
            prem_str = (
                row.get("average_annual_premium")
                or row.get("combined_expenditure")
                or row.get("premium")
                or "0"
            )
            try:
                annual_prem = float(str(prem_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if annual_prem <= 0:
                continue

            source_vintage = str(
                row.get("source_year") or row.get("vintage") or reference_year
            ).strip()

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
                source_variable="combined_average_expenditure_liability_comp_coll",
                source_url=NAIC_BASE_URL,
                source_release=f"NAIC Auto Insurance Database Report (Source Vintage: {source_vintage})",
                source_reference_period=source_vintage,
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    f"NAIC combined average annual expenditure (Liability + Comprehensive + Collision) "
                    f"in {state_alpha} (Source Vintage: {source_vintage})."
                ),
            )
            observations.append(obs)

    return observations
