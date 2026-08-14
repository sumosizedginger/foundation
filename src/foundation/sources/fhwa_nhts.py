"""Federal Highway Administration (FHWA) / National Household Travel Survey (NHTS) Source Adapter.

Ingests and documents the empirical annual vehicle miles traveled (VMT) benchmark for single-adult
working-age drivers (Age 18-64) covering necessary commuting, medical trips, grocery shopping,
and essential local travel.

NHTS METHODOLOGICAL BASELINE:
- Survey: 2022 NHTS (National Household Travel Survey).
- Target Population: 1-driver households with 1 adult worker.
- Weighted Annual VMT: Calculated dynamically from `hhpub.csv` using `ANNMILES` and `WTHHFIN`.
"""

from __future__ import annotations

import csv
import logging
import zipfile
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

logger = logging.getLogger(__name__)

NHTS_LANDING = "https://nhts.ornl.gov/downloads"


NHTS_2022_CSV_ZIP = "https://nhts.ornl.gov/assets/2022/download/csv.zip"


def download_fhwa_nhts_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Official 2022 NextGen NHTS V2.1 public-use CSV zip."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported FHWA NHTS reference year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    from foundation.sources.acquisition import acquire_source

    return acquire_source(
        source_id=f"fhwa_nhts_{year}",
        url=NHTS_2022_CSV_ZIP,
        cache_dir=cache_dir,
        expected_filename="nhts_2022_csv.zip",
        force_download=force_download,
    )


def parse_fhwa_nhts_mileage(
    cache_dir: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse NHTS annual mileage benchmark dataset for single-adult drivers from ZIP."""
    zip_path = cache_dir / "nhts_2022_csv.zip"
    if not zip_path.exists():
        logger.warning(f"NHTS ZIP not found: {zip_path}")
        # Fail closed
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
            source_id="fhwa_nhts_2022",
            source_variable="ANNMILES",
            source_url=NHTS_2022_CSV_ZIP,
            source_release="FHWA NHTS 2022",
            source_reference_period="2022",
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: FHWA NHTS annual mileage ZIP could not be found.",
        )

    weighted_miles_sum = 0.0
    total_weights = 0.0
    sample_size = 0

    try:
        with zipfile.ZipFile(zip_path) as z:
            # Look for the household public file. Names can vary, e.g., hhpub.csv or hhpub22.csv
            hh_files = [
                f
                for f in z.namelist()
                if f.lower().endswith(".csv") and ("hhpub" in f.lower() or "hhv2pub" in f.lower())
            ]
            if not hh_files:
                raise FileNotFoundError("Could not find household public CSV inside NHTS ZIP.")

            import io

            eligible: dict[str, float] = {}
            with z.open(hh_files[0]) as fh:
                text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                reader = csv.DictReader(text_fh)
                for row in reader:
                    wrkcount = str(row.get("WRKCOUNT", "")).strip()
                    hhsize = str(row.get("HHSIZE", "")).strip()
                    if wrkcount != "1" or hhsize != "1":
                        continue
                    hid = str(row.get("HOUSEID") or "").strip()
                    weight_str = str(row.get("WTHHFIN") or "").strip()
                    if not hid or not weight_str:
                        continue
                    try:
                        weight = float(weight_str)
                    except ValueError:
                        continue
                    if weight <= 0:
                        continue
                    eligible[hid] = weight

            veh_files = [
                f
                for f in z.namelist()
                if f.lower().endswith(".csv") and ("vehv2pub" in f.lower() or "vehpub" in f.lower())
            ]
            if not veh_files:
                raise FileNotFoundError("Could not find vehicle public CSV inside NHTS ZIP.")
            miles_by_hh: dict[str, float] = {}
            with z.open(veh_files[0]) as fh:
                text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                reader = csv.DictReader(text_fh)
                for row in reader:
                    hid = str(row.get("HOUSEID") or "").strip()
                    if hid not in eligible:
                        continue
                    miles_str = str(row.get("ANNMILES") or "").strip()
                    if not miles_str:
                        continue
                    try:
                        miles = float(miles_str)
                    except ValueError:
                        continue
                    if miles < 0:
                        continue
                    miles_by_hh[hid] = miles_by_hh.get(hid, 0.0) + miles

            for hid, weight in eligible.items():
                if hid not in miles_by_hh:
                    continue
                weighted_miles_sum += miles_by_hh[hid] * weight
                total_weights += weight
                sample_size += 1

    except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile, UnicodeError) as e:
        logger.error(f"Failed to process NHTS ZIP: {e}")
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
            source_id="fhwa_nhts_2022",
            source_variable="ANNMILES",
            source_url=NHTS_2022_CSV_ZIP,
            source_release="FHWA NHTS 2022",
            source_reference_period="2022",
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=f"UNAVAILABLE: Failed to process NHTS dataset - {e}",
        )

    if sample_size == 0 or total_weights == 0:
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
            source_id="fhwa_nhts_2022",
            source_variable="ANNMILES",
            source_url=NHTS_2022_CSV_ZIP,
            source_release="FHWA NHTS 2022",
            source_reference_period="2022",
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: NHTS filtering yielded 0 valid samples.",
        )

    annual_miles = weighted_miles_sum / total_weights

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
        source_id="fhwa_nhts_2022",
        source_variable="ANNMILES_WRKCOUNT1_HHSIZE1",
        source_url=NHTS_2022_CSV_ZIP,
        source_release="FHWA NHTS 2022",
        source_reference_period="2022",
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=f"FHWA NHTS weighted annual vehicle miles traveled for single-adult driver baseline ({annual_miles:,.0f} mi/yr, Sample: {sample_size:,}).",
    )
