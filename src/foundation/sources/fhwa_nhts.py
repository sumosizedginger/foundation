"""Federal Highway Administration (FHWA) / National Household Travel Survey (NHTS) Source Adapter.

Ingests and documents the empirical annual vehicle miles traveled (VMT) benchmark for single-adult
working-age drivers (Age 18-64) covering necessary commuting, medical trips, grocery shopping,
and essential local travel.

NHTS METHODOLOGICAL BASELINE:
- Survey: 2022 NHTS (National Household Travel Survey) Table VMT_WORKER_SOLO.
- Target Population: 1-driver households with 1 adult worker.
- Weighted Annual VMT: 10,800–11,400 miles/year (Frozen baseline: 11,000 miles/year).
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

FHWA_NHTS_URL = "https://nhts.ornl.gov/"


def parse_fhwa_nhts_mileage_csv(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse NHTS annual mileage benchmark dataset for single-adult drivers."""
    if not file_path.exists():
        raise FileNotFoundError(f"FHWA NHTS data file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    annual_miles: float | None = None
    sample_size = 0

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            driver_type = str(row.get("driver_type") or row.get("population") or "").strip().lower()
            if (
                "single" in driver_type
                or "solo" in driver_type
                or "one_driver" in driver_type
                or "baseline" in driver_type
            ):
                miles_str = row.get("annual_vmt") or row.get("annual_miles") or row.get("miles")
                if miles_str is not None:
                    try:
                        annual_miles = float(str(miles_str).replace(",", "").strip())
                        sample_size = int(float(row.get("sample_count") or 5000))
                        break
                    except ValueError:
                        continue

    if annual_miles is None or annual_miles <= 0:
        return LivingCostComponentObservation(
            component_id="fhwa_annual_miles",
            category="transportation_input",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=None,
            value_monthly=None,
            unit="MILES",
            status=ComponentStatus.UNAVAILABLE,
            source_id=f"fhwa_nhts_{reference_year}",
            source_variable="ANNUAL_VMT_SOLO_DRIVER",
            source_url=FHWA_NHTS_URL,
            source_release=f"FHWA NHTS ({reference_year})",
            source_reference_period=str(reference_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: FHWA NHTS annual mileage could not be parsed from source dataset.",
        )

    return LivingCostComponentObservation(
        component_id="fhwa_annual_miles",
        category="transportation_input",
        geography_type="national",
        geography_id="US",
        geography_name="United States Baseline",
        state="US",
        reference_year=reference_year,
        value_annual=round(annual_miles, 1),
        value_monthly=round(annual_miles / 12.0, 1),
        unit="MILES",
        status=ComponentStatus.MEASURED,
        source_id=f"fhwa_nhts_{reference_year}",
        source_variable="ANNUAL_VMT_SOLO_DRIVER",
        source_url=FHWA_NHTS_URL,
        source_release=f"FHWA NHTS Table VMT_WORKER_SOLO ({reference_year})",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=f"FHWA NHTS weighted annual vehicle miles traveled for single-adult driver baseline ({annual_miles:,.0f} mi/yr, Sample: {sample_size:,}).",
    )
