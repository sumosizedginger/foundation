"""Medical Expenditure Panel Survey (MEPS) Source Adapter.

Calculates realistic expected annual out-of-pocket (OOP) healthcare expenditures for non-elderly
adults (Age 18-64) with private health insurance coverage from official AHRQ MEPS tables/microdata.

STRICT FAIL-CLOSED RULES:
- NO hardcoded numeric fallback values ($1,420 / $1,550).
- If source observation cannot be parsed or verified, status = UNAVAILABLE with None values.
- Population Filter: Adults age 18-64, privately insured throughout the survey year.
- Metric: Population-weighted mean out-of-pocket medical expenditure (TOTSLFX).

2024 Full Year Consolidated is scheduled by AHRQ for AUGUST 2026. Do not claim it exists
until it appears in the official MEPS PUF listing. HC-251 (2023) remains the latest listed
full-year file as of 2026-08-14.
"""

from __future__ import annotations

import csv
import dataclasses
import logging
import re
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.http import download_file

logger = logging.getLogger(__name__)

MEPS_LISTING_URL = "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files.jsp"
MEPS_SCHEDULE_URL = "https://meps.ahrq.gov/mepsweb/about_meps/releaseschedule.jsp"
MEPS_HC251_LANDING = (
    "https://meps.ahrq.gov/mepsweb/data_stats/download_data_files_detail.jsp?cboPufNumber=HC-251"
)
MEPS_HC251_ASCII_ZIP = "https://meps.ahrq.gov/mepsweb/data_files/pufs/h251/h251dat.zip"
MEPS_DATA_YEAR = 2023
MEPS_PUF_ID = "HC-251"
MEPS_2024_FY_SCHEDULE = "AUGUST 2026"
MEPS_NOTE = (
    "Newest official Full Year Consolidated PUF actually listed is HC-251 (2023). "
    "AHRQ official 2026 release schedule lists the 2024 Full Year Consolidated Data File "
    f"for {MEPS_2024_FY_SCHEDULE}. Do not claim the 2024 file exists until it appears "
    "in the official MEPS PUF listing."
)

# Known 2024 event-file PUF numbers are NOT the Full Year Consolidated file.
# 2024 FY Consolidated PUF number is unknown until AHRQ lists it.
_FY_CONSOLIDATED_RE = re.compile(
    r"2024\s+Full\s+Year\s+Consolidated",
    re.IGNORECASE,
)
_PUF_NUMBER_RE = re.compile(r"cboPufNumber=(HC-\d+[A-Z]?)", re.IGNORECASE)
_H_DAT_ZIP_RE = re.compile(
    r"https://meps\.ahrq\.gov/mepsweb/data_files/pufs/h(\d+)/h\1dat\.zip",
    re.IGNORECASE,
)


def check_meps_2024_full_year_listing(
    listing_html: str | None = None,
    *,
    timeout: tuple[float, float] = (15.0, 60.0),
) -> dict[str, Any]:
    """Inspect the official MEPS PUF listing for a 2024 Full Year Consolidated file.

    Returns a structured refresh result. Does not invent a PUF number.
    """
    html = listing_html
    fetched_url = MEPS_LISTING_URL
    if html is None:
        try:
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            try:
                download_file(url=MEPS_LISTING_URL, destination=tmp_path, timeout=timeout)
                html = tmp_path.read_text(encoding="utf-8", errors="replace")
            finally:
                tmp_path.unlink(missing_ok=True)
        except (OSError, ValueError, RuntimeError, TypeError) as exc:
            logger.warning("MEPS 2024 FY listing refresh failed: %s", exc)
            return {
                "checked_at_source": MEPS_LISTING_URL,
                "schedule_url": MEPS_SCHEDULE_URL,
                "schedule_states_2024_fy": MEPS_2024_FY_SCHEDULE,
                "released": False,
                "listed_puf_id": None,
                "ascii_zip_url": None,
                "notes": (
                    "Could not retrieve official MEPS PUF listing. "
                    f"Continue using {MEPS_PUF_ID} with true source year = {MEPS_DATA_YEAR}. "
                    f"Error: {exc}"
                ),
            }

    has_fy_label = bool(_FY_CONSOLIDATED_RE.search(html))
    # Only treat as released if the 2024 FY Consolidated label is present AND a
    # PUF number other than known 2023/2022 FY files is associated nearby.
    puf_ids = {m.group(1).upper() for m in _PUF_NUMBER_RE.finditer(html)}
    zip_hits = list(_H_DAT_ZIP_RE.finditer(html))
    listed_puf_id = None
    ascii_zip_url = None
    if has_fy_label:
        # Prefer a PUF number that is not HC-251 / HC-243 (prior FY files).
        for puf_id in sorted(puf_ids):
            if puf_id not in {"HC-251", "HC-243"}:
                listed_puf_id = puf_id
                break
        if listed_puf_id:
            digits = listed_puf_id.split("-", 1)[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
            ascii_zip_url = (
                f"https://meps.ahrq.gov/mepsweb/data_files/pufs/h{digits.lower()}/"
                f"h{digits.lower()}dat.zip"
            )
        elif zip_hits:
            ascii_zip_url = zip_hits[0].group(0)

    released = bool(has_fy_label and listed_puf_id)
    if released:
        notes = (
            f"Official MEPS listing now includes 2024 Full Year Consolidated "
            f"as {listed_puf_id}. Prefer this file over HC-251."
        )
    else:
        notes = (
            "2024 Full Year Consolidated is NOT in the official MEPS PUF listing. "
            f"AHRQ schedule still lists it for {MEPS_2024_FY_SCHEDULE}. "
            f"Continue using {MEPS_PUF_ID} with true source year = {MEPS_DATA_YEAR}."
        )
    return {
        "checked_at_source": fetched_url,
        "schedule_url": MEPS_SCHEDULE_URL,
        "schedule_states_2024_fy": MEPS_2024_FY_SCHEDULE,
        "released": released,
        "listed_puf_id": listed_puf_id,
        "ascii_zip_url": ascii_zip_url,
        "notes": notes,
    }


def download_meps_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve latest listed official MEPS Full Year Consolidated, or HC-251."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported MEPS project cost year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    refresh = check_meps_2024_full_year_listing()
    if refresh["released"] and refresh["ascii_zip_url"] and refresh["listed_puf_id"]:
        puf_id = str(refresh["listed_puf_id"])
        digits = puf_id.split("-", 1)[1].rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ").lower()
        artifact = acquire_source(
            source_id=f"meps_table1_{year}",
            url=str(refresh["ascii_zip_url"]),
            cache_dir=cache_dir,
            expected_filename=f"h{digits}dat.zip",
            force_download=force_download,
            refresh_if_unprovenanced=True,
        )
        if artifact is None:
            return record_unretrieved(
                f"meps_table1_{year}",
                status="UNAVAILABLE",
                resolved_url=MEPS_LISTING_URL,
                notes=(
                    f"Official MEPS {puf_id} (2024 Full Year Consolidated) was listed "
                    "but could not be retrieved."
                ),
            )
        return dataclasses.replace(
            artifact,
            notes=(
                f"MEPS {puf_id} data year 2024 used as OOP source vintage "
                f"for project cost year {year}. Refresh check found the 2024 FY file "
                f"on the official listing. {refresh['notes']}"
            ),
        )

    artifact = acquire_source(
        source_id=f"meps_table1_{year}",
        url=MEPS_HC251_ASCII_ZIP,
        cache_dir=cache_dir,
        expected_filename="h251dat.zip",
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        return record_unretrieved(
            f"meps_table1_{year}",
            status="UNAVAILABLE",
            resolved_url=MEPS_HC251_LANDING,
            notes=(
                f"Official MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year) could not be retrieved. "
                "No fabricated meps_fy_{year}.csv URL is used. "
                f"{MEPS_NOTE}"
            ),
        )
    return dataclasses.replace(
        artifact,
        notes=(
            f"MEPS {MEPS_PUF_ID} data year {MEPS_DATA_YEAR} used as OOP source vintage "
            f"for project cost year {year}. This is not a {year} MEPS file. "
            f"{refresh['notes']}"
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
            source_url=MEPS_HC251_LANDING,
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
            source_url=MEPS_HC251_LANDING,
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
        source_url=MEPS_HC251_LANDING,
        source_release=f"AHRQ MEPS {MEPS_PUF_ID} ({MEPS_DATA_YEAR} data year)",
        source_reference_period=str(MEPS_DATA_YEAR),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"AHRQ MEPS weighted mean OOP medical spending for privately insured adults age 18-64 "
            f"(Sample: {sample_size:,}, Represented: {represented_pop:,}). {MEPS_NOTE}"
        ),
    )
