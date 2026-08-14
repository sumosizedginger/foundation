"""Medical Expenditure Panel Survey (MEPS) Source Adapter.

Calculates realistic expected annual out-of-pocket (OOP) healthcare expenditures for non-elderly
adults (Age 18-64) with private health insurance coverage from official AHRQ MEPS tables/microdata.

STRICT FAIL-CLOSED RULES:
- NO hardcoded numeric fallback values ($1,420 / $1,550).
- If source observation cannot be parsed or verified, status = UNAVAILABLE with None values.
- Population Filter: Adults age 18-64, privately insured throughout the survey year.
- Metric: Population-weighted mean out-of-pocket medical expenditure (TOTSLFX).
"""

from __future__ import annotations

import csv
import dataclasses
import logging
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

MEPS_HC243_LANDING = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251"
)
MEPS_HC243_ASCII_ZIP = "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip"
MEPS_DATA_YEAR = 2023
MEPS_PUF_ID = "HC-251"
MEPS_NOTE = (
    "Newest official Full Year Consolidated PUF at execution is HC-251 (2023). "
    "2024 Full Year Consolidated is scheduled later; not used."
)


def download_meps_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official MEPS HC-243 (2022 Full Year Consolidated), or record a gap."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported MEPS project cost year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = acquire_source(
        source_id=f"meps_table1_{year}",
        url=MEPS_HC243_ASCII_ZIP,
        cache_dir=cache_dir,
        expected_filename="h251dat.zip",
        force_download=force_download,
    )
    if artifact is None:
        return record_unretrieved(
            f"meps_table1_{year}",
            status="UNAVAILABLE",
            resolved_url=MEPS_HC243_LANDING,
            notes=(
                f"Official MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year) could not be retrieved. "
                "No fabricated meps_fy_{year}.csv URL is used."
            ),
        )
    return dataclasses.replace(
        artifact,
        notes=(
            f"MEPS {MEPS_PUF_ID} data year {MEPS_DATA_YEAR} used as OOP source vintage "
            f"for project cost year {year}. This is not a {year} MEPS file."
        ),
    )


def parse_meps_oop_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse MEPS expected OOP healthcare expenditure table for privately insured adults 18-64."""
    file_path = cache_dir if cache_dir.is_file() else cache_dir / "h251dat.zip"

    if not file_path.exists():
        logger.warning(f"MEPS CSV not found: {file_path}")
        return LivingCostComponentObservation(
            component_id="healthcare_oop_meps",
            category="healthcare",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=None,
            value_monthly=None,
            unit="USD",
            status=ComponentStatus.UNAVAILABLE,
            source_id=f"meps_fyc_{reference_year}",
            source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
            source_url=MEPS_HC243_LANDING,
            source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
            source_reference_period=str(MEPS_DATA_YEAR),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: MEPS out-of-pocket medical expenditure CSV could not be found.",
        )

    expected_oop_annual: float | None = None
    sample_size: int = 0
    represented_pop: int = 0

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                age_group = str(row.get("age_group") or row.get("Age") or "").strip()
                ins_status = (
                    str(
                        row.get("insurance_status")
                        or row.get("Insurance")
                        or row.get("insurance")
                        or ""
                    )
                    .strip()
                    .lower()
                )

                # Enforce strict population filter: Adults 18-64 + Private Insurance
                is_adult = (
                    "18-64" in age_group or "adult" in age_group.lower() or age_group == "18 to 64"
                )
                is_private = (
                    "priv" in ins_status or "any private" in ins_status or ins_status == "private"
                )

                if is_adult and is_private:
                    oop_str = (
                        row.get("mean_oop_expenditure")
                        or row.get("oop_annual")
                        or row.get("TOTSLFX_mean")
                    )
                    if oop_str is not None and str(oop_str).strip() != "":
                        try:
                            val = float(str(oop_str).replace("$", "").replace(",", "").strip())
                            if val > 0:
                                expected_oop_annual = val
                                sample_size = int(
                                    float(row.get("sample_count") or row.get("n_unweighted") or 0)
                                )
                                represented_pop = int(
                                    float(
                                        row.get("represented_population")
                                        or row.get("n_weighted")
                                        or 0
                                    )
                                )
                                break
                        except ValueError:
                            continue
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse MEPS CSV: {e}")

    if expected_oop_annual is None or expected_oop_annual <= 0:
        # FAIL-CLOSED: No numeric substitution allowed
        return LivingCostComponentObservation(
            component_id="healthcare_oop_meps",
            category="healthcare",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=None,
            value_monthly=None,
            unit="USD",
            status=ComponentStatus.UNAVAILABLE,
            source_id=f"meps_fyc_{reference_year}",
            source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
            source_url=MEPS_HC243_LANDING,
            source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
            source_reference_period=str(MEPS_DATA_YEAR),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes="UNAVAILABLE: MEPS out-of-pocket medical expenditure could not be parsed from source dataset.",
        )

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
        source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
        source_url=MEPS_HC243_LANDING,
        source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
        source_reference_period=str(MEPS_DATA_YEAR),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"AHRQ MEPS weighted mean OOP medical spending for privately insured adults age 18-64 "
            f"(Sample: {sample_size:,}, Represented: {represented_pop:,})."
        ),
    )
