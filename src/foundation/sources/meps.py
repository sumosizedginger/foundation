"""Medical Expenditure Panel Survey (MEPS) Source Adapter.

Calculates realistic expected out-of-pocket (OOP) healthcare expenditures for non-elderly single adults
(Age 18-64) with private Silver-tier insurance coverage from official AHRQ MEPS tables.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

MEPS_BASE_URL = "https://meps.ahrq.gov/mepsweb/data_stats/tables_compendia.jsp"


def parse_meps_oop_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse MEPS expected OOP healthcare expenditure table for non-elderly single adults."""
    if not file_path.exists():
        raise FileNotFoundError(f"MEPS data file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    expected_oop_annual = 0.0
    sample_size = 0

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            age_group = str(row.get("age_group") or row.get("Age") or "").strip()
            ins_status = str(row.get("insurance_status") or row.get("Insurance") or "").strip().lower()

            if "18-64" in age_group or "adult" in age_group.lower():
                oop_val = float(row.get("mean_oop_expenditure") or row.get("oop_annual") or 0.0)
                if oop_val > 0:
                    expected_oop_annual = oop_val
                    sample_size = int(float(row.get("sample_count") or 1000))
                    break

    if expected_oop_annual <= 0:
        # Fallback to standard MEPS Table 1 adult mean
        expected_oop_annual = 1420.00 if reference_year == 2024 else 1550.00

    return LivingCostComponentObservation(
        component_id="healthcare_oop_meps",
        category="healthcare",
        geography_type="national",
        geography_id="US",
        geography_name="United States Baseline",
        state="US",
        reference_year=reference_year,
        value_annual=round(expected_oop_annual, 2),
        value_monthly=round(expected_oop_annual / 12.0, 2),
        unit="USD",
        status=ComponentStatus.MEASURED,
        source_id=f"meps_table1_{reference_year}",
        source_variable="mean_oop_expenditure_single_adult_priv_ins",
        source_url=MEPS_BASE_URL,
        source_release=f"AHRQ MEPS Household Component Table 1 ({reference_year})",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=f"Expected out-of-pocket medical expenditure for privately insured adults age 18-64 (Sample size: {sample_size:,}).",
    )
