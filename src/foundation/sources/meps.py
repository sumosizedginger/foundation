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
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

MEPS_BASE_URL = "https://meps.ahrq.gov/mepsweb/data_stats/tables_compendia.jsp"


def parse_meps_oop_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> LivingCostComponentObservation:
    """Parse MEPS expected OOP healthcare expenditure table for privately insured adults 18-64."""
    if not file_path.exists():
        raise FileNotFoundError(f"MEPS data file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    expected_oop_annual: float | None = None
    sample_size: int = 0
    represented_pop: int = 0

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
                                    row.get("represented_population") or row.get("n_weighted") or 0
                                )
                            )
                            break
                    except ValueError:
                        continue

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
            source_id=f"meps_table1_{reference_year}",
            source_variable="TOTSLFX_mean_adult_18_64_priv_ins",
            source_url=MEPS_BASE_URL,
            source_release=f"AHRQ MEPS Household Component Table 1 ({reference_year})",
            source_reference_period=str(reference_year),
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
        source_url=MEPS_BASE_URL,
        source_release=f"AHRQ MEPS Household Component Table 1 ({reference_year})",
        source_reference_period=str(reference_year),
        retrieved_at=retrieved_at,
        source_artifact_sha256=file_sha256,
        methodology_version="0.2.0-draft",
        notes=(
            f"AHRQ MEPS weighted mean OOP medical spending for privately insured adults age 18-64 "
            f"(Sample: {sample_size:,}, Represented: {represented_pop:,})."
        ),
    )
