"""National Association of Insurance Commissioners (NAIC) Auto Insurance Adapter.

Ingests state-level average expenditure for private passenger automobile insurance from official
NAIC Auto Insurance Database Reports.

METHODOLOGICAL DISTINCTIONS:
- Metric: Combined Average Expenditure (Liability + Comprehensive + Collision) per insured vehicle.
- Source Frequency: Biennial/triennial official NAIC releases (e.g. 2021/2022 survey data published in 2024).
- Temporal Rule: Real source vintage year is stored explicitly. If a 2026 survey is not yet published,
  the component reports the last validated observation with explicit vintage metadata.
- Licensing: The NAIC Auto Insurance Database Report is a licensed publication. The acquisition layer
  expects the purchased artifact to be available or securely downloaded.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import record_unretrieved

logger = logging.getLogger(__name__)

NAIC_BASE_URL = (
    "https://content.naic.org/research-actuarial-services/auto-insurance-database-report"
)


def download_naic_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """NAIC Auto Insurance Database Report is licensed. Do not invent a download URL."""
    del cache_dir, force_download
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported NAIC reference year: {year}")
    return record_unretrieved(
        f"naic_auto_ins_{year}",
        status="LICENSING_REVIEW",
        resolved_url=NAIC_BASE_URL,
        notes=(
            "NAIC Auto Insurance Database Report is a licensed publication. "
            "No official public automated CSV exists. Do not fabricate a download URL."
        ),
    )


def parse_naic_auto_insurance_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse NAIC state auto insurance average expenditure dataset."""
    file_path = (
        cache_dir
        if cache_dir.is_file()
        else cache_dir / f"naic_auto_insurance_{reference_year}.csv"
    )

    if not file_path.exists():
        logger.warning(f"NAIC auto insurance CSV not found: {file_path}")
        return []

    observations: list[LivingCostComponentObservation] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
                if not state_alpha:
                    continue

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
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse NAIC CSV: {e}")

    return observations
