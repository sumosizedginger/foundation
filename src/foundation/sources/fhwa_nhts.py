"""Federal Highway Administration (FHWA) / National Household Travel Survey (NHTS) Source Adapter.

Observed annual vehicle miles for one-person, one-worker, age-18-64 licensed-driver
households. This is OBSERVED TRAVEL BEHAVIOR, not MINIMUM NECESSARY MILEAGE.

The person file is joined so that age 18-64 and licensed-driver criteria are actually
executed. Household-only HHSIZE==1 / WRKCOUNT==1 is not sufficient.
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


def _nhts_age(row: dict[str, str]) -> int | None:
    for key in ("R_AGE", "R_AGE_IMP", "AGE"):
        raw = str(row.get(key) or "").strip()
        if not raw:
            continue
        try:
            age = int(float(raw))
        except ValueError:
            continue
        if age > 0:
            return age
    return None


def _nhts_is_driver(row: dict[str, str]) -> bool | None:
    """Return True/False when the official driver field is present; None if unsupported."""
    for key in ("DRIVER", "DRIVERSTAT"):
        raw = str(row.get(key) or "").strip().upper()
        if not raw:
            continue
        digits = raw.lstrip("0") or "0"
        if raw in {"1", "01", "YES", "Y", "DRIVER"} or digits == "1":
            return True
        if raw in {"2", "02", "NO", "N", "NONDRIVER", "NON-DRIVER"} or digits == "2":
            return False
    return None


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
        refresh_if_unprovenanced=True,
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
            per_files = [
                f
                for f in z.namelist()
                if f.lower().endswith(".csv")
                and ("perv2pub" in f.lower() or "perpub" in f.lower())
            ]
            if not per_files:
                raise FileNotFoundError(
                    "Could not find person public CSV inside NHTS ZIP. "
                    "Age 18-64 and licensed-driver filters cannot be executed without it."
                )

            import io

            eligible: dict[str, float] = {}
            with z.open(hh_files[0]) as fh:
                text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                reader = csv.DictReader(text_fh)
                for row in reader:
                    wrkcount = str(row.get("WRKCOUNT", "")).strip().lstrip("0") or "0"
                    hhsize = str(row.get("HHSIZE", "")).strip().lstrip("0") or "0"
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

            person_ok: set[str] = set()
            with z.open(per_files[0]) as fh:
                text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                reader = csv.DictReader(text_fh)
                for row in reader:
                    hid = str(row.get("HOUSEID") or "").strip()
                    if hid not in eligible:
                        continue
                    age = _nhts_age(row)
                    if age is None or age < 18 or age > 64:
                        continue
                    driver = _nhts_is_driver(row)
                    if driver is not True:
                        continue
                    person_ok.add(hid)
            eligible = {hid: w for hid, w in eligible.items() if hid in person_ok}

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

    from foundation.percentiles import weighted_percentile

    miles = [miles_by_hh[hid] for hid in eligible if hid in miles_by_hh]
    weights = [eligible[hid] for hid in eligible if hid in miles_by_hh]
    annual_miles = weighted_miles_sum / total_weights
    p25 = weighted_percentile(miles, weights, 0.25)
    median = weighted_percentile(miles, weights, 0.50)
    p75 = weighted_percentile(miles, weights, 0.75)

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
        source_variable="ANNMILES_HHSIZE1_WRKCOUNT1_AGE18_64_DRIVER",
        source_url=NHTS_2022_CSV_ZIP,
        source_release="FHWA NHTS 2022 V2.1",
        source_reference_period="2022",
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            "OBSERVED TRAVEL BEHAVIOR for one-person, one-worker, age-18-64 licensed-driver "
            "households with valid annual vehicle mileage. Filters actually executed: "
            "hhv2pub HHSIZE=1 and WRKCOUNT=1; perv2pub R_AGE in 18-64 and DRIVER=1; "
            "vehv2pub sum(ANNMILES); weight=WTHHFIN. Missing weights dropped (not defaulted). "
            f"Weighted mean={annual_miles:,.1f}; median={median:,.1f}; "
            f"P25={p25:,.1f}; P75={p75:,.1f}; unweighted n={sample_size:,}. "
            "This is not MINIMUM NECESSARY MILEAGE (OD-003)."
        ),
    )
