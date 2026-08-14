"""USDA Food Plans source adapter.

Retrieves official CNPP Excel archives and computes the 1-person Low-Cost
and Thrifty adult midpoint with the statutory +20% one-person adjustment
printed in the official file notes.

Raw monthly USDA cells are MEASURED. The midpoint × 1.20 step is
MODELED_FROM_MEASURED_INPUTS.

Alaska/Hawaii official archives currently publish Thrifty family
observations only. Those rows are recorded as measured Thrifty family
references. They are not converted into a Low-Cost 1-person amount with
a hand-entered multiplier.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.xlsx_xml import rows_as_dicts

logger = logging.getLogger(__name__)

USDA_FOOD_PLANS_URL = (
    "https://www.fna.usda.gov/research/cnpp/usda-food-plans/cost-food-monthly-reports"
)
USDA_FILE_BASE = "https://www.fna.usda.gov/sites/default/files/resource-files"

# Official one-person household adjustment printed in CNPP archive notes.
ONE_PERSON_HOUSEHOLD_FACTOR = 1.20
ADULT_AGE_TOKEN = "19-50"

USDA_ARCHIVES: dict[str, dict[str, str]] = {
    "low_cost": {
        "filename": "usda-lowcostplan-sept2007-present.xlsx",
        "source_id_prefix": "usda_food_low_cost",
        "plan_label": "Low-Cost",
    },
    "thrifty": {
        "filename": "usda-thriftyplan-june2021-present.xlsx",
        "source_id_prefix": "usda_food_thrifty",
        "plan_label": "Thrifty",
    },
    "alaska": {
        "filename": "usda-alaska-june2023-present.xlsx",
        "source_id_prefix": "usda_food_alaska",
        "plan_label": "Alaska",
    },
    "hawaii": {
        "filename": "usda-hawaii-june2023-present.xlsx",
        "source_id_prefix": "usda_food_hawaii",
        "plan_label": "Hawaii",
    },
}


def _official_url(filename: str) -> str:
    return f"{USDA_FILE_BASE}/{filename}"


def download_usda_food_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official CNPP Low-Cost / Thrifty / AK / HI Excel archives."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported USDA Food Plan reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for key, spec in USDA_ARCHIVES.items():
        artifact = acquire_source(
            source_id=f"{spec['source_id_prefix']}_{year}",
            url=_official_url(spec["filename"]),
            cache_dir=cache_dir,
            expected_filename=spec["filename"],
            force_download=force_download,
        )
        if artifact is None:
            artifacts.append(
                record_unretrieved(
                    f"{spec['source_id_prefix']}_{year}",
                    status="SOURCE_GAP",
                    resolved_url=_official_url(spec["filename"]),
                    notes=(
                        f"Official USDA {spec['plan_label']} archive "
                        f"{spec['filename']} was not retrieved from {USDA_FOOD_PLANS_URL}."
                    ),
                )
            )
            continue
        parsed = parse_usda_official_xlsx(
            cache_dir / spec["filename"],
            reference_year=year,
            plan_key=key,
            retrieved_at=artifact.retrieved_at,
            file_sha256=artifact.sha256,
        )
        notes = artifact.notes or ""
        if parsed:
            status = "VALIDATED"
            notes = (
                f"{notes} Parsed {len(parsed)} official monthly rows for {year} "
                f"{spec['plan_label']}."
            ).strip()
        else:
            status = "RETRIEVED_UNVALIDATED"
            notes = (
                f"{notes} Archive retrieved but no official monthly rows matched "
                f"the adult 19-50 individual filter for {year}."
            ).strip()
        from dataclasses import replace

        artifacts.append(
            replace(
                artifact,
                validation_status=status,
                notes=notes,
            )
        )
    if not artifacts:
        return record_unretrieved(
            f"usda_food_low_cost_{year}",
            status="SOURCE_GAP",
            resolved_url=USDA_FOOD_PLANS_URL,
            notes="No USDA Food Plan archives were retrieved.",
        )
    return artifacts


def _cell_str(value: object) -> str:
    return str(value).strip() if value is not None else ""


def _cell_year(value: object) -> int | None:
    text = _cell_str(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _cell_cost(value: object) -> float | None:
    text = _cell_str(value).replace("$", "").replace(",", "")
    if not text:
        return None
    try:
        amount = float(text)
    except ValueError:
        return None
    if amount <= 0:
        return None
    return amount


def parse_usda_official_xlsx(
    file_path: Path,
    *,
    reference_year: int,
    plan_key: str,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[dict[str, Any]]:
    """Parse official CNPP archive rows for one calendar year."""
    if not file_path.exists():
        return []
    try:
        records = rows_as_dicts(file_path)
    except (OSError, ValueError, KeyError) as exc:
        logger.error("Failed to parse USDA workbook %s: %s", file_path, exc)
        return []

    matched: list[dict[str, Any]] = []
    for rec in records:
        year = _cell_year(rec.get("year"))
        if year != reference_year:
            continue
        frequency = _cell_str(rec.get("frequency")).lower()
        if frequency and frequency != "monthly":
            continue
        cost = _cell_cost(rec.get("cost"))
        if cost is None:
            continue
        matched.append(
            {
                "geographic_area": _cell_str(rec.get("geographic_area")),
                "fam_indv": _cell_str(rec.get("fam_indv")),
                "group": _cell_str(rec.get("group")),
                "age": _cell_str(rec.get("age")),
                "year": year,
                "month": _cell_str(rec.get("month")),
                "food_plan": _cell_str(rec.get("food_plan")) or plan_key,
                "frequency": _cell_str(rec.get("frequency")) or "Monthly",
                "cost": cost,
            }
        )
    return matched


def _adult_individual_rows(rows: list[dict[str, Any]], sex: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if "ind" not in row["fam_indv"].lower():
            continue
        if sex not in row["group"].lower():
            continue
        age = row["age"].replace("–", "-").replace(" ", "")
        if "19-50" not in age and ADULT_AGE_TOKEN not in row["age"]:
            continue
        out.append(row)
    return out


def _average_monthly(rows: list[dict[str, Any]]) -> tuple[float | None, int, list[str]]:
    if not rows:
        return None, 0, []
    months = sorted({row["month"] for row in rows if row["month"]})
    # One observation per month: if duplicates exist, average them.
    by_month: dict[str, list[float]] = {}
    for row in rows:
        by_month.setdefault(row["month"] or "unknown", []).append(row["cost"])
    month_means = [sum(vals) / len(vals) for vals in by_month.values()]
    return sum(month_means) / len(month_means), len(month_means), months


def build_usda_food_observations(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Build 1-person Low-Cost / Thrifty observations from official archives."""
    observations: list[LivingCostComponentObservation] = []
    for plan_key, spec in (
        ("low_cost", USDA_ARCHIVES["low_cost"]),
        ("thrifty", USDA_ARCHIVES["thrifty"]),
    ):
        path = cache_dir / spec["filename"] if cache_dir.is_dir() else cache_dir
        rows = parse_usda_official_xlsx(
            path,
            reference_year=reference_year,
            plan_key=plan_key,
            retrieved_at=retrieved_at,
            file_sha256=file_sha256,
        )
        male_rows = _adult_individual_rows(rows, "male")
        female_rows = _adult_individual_rows(rows, "female")
        avg_male, male_months, male_labels = _average_monthly(male_rows)
        avg_female, female_months, female_labels = _average_monthly(female_rows)
        months_count = min(male_months, female_months)
        if avg_male is None or avg_female is None or months_count <= 0:
            observations.append(
                LivingCostComponentObservation(
                    component_id="food_low_cost"
                    if plan_key == "low_cost"
                    else "food_thrifty_sensitivity",
                    category="food",
                    geography_type="national",
                    geography_id="US",
                    geography_name="United States Baseline",
                    state="US",
                    reference_year=reference_year,
                    value_annual=None,
                    value_monthly=None,
                    unit="USD",
                    status=ComponentStatus.SOURCE_GAP,
                    source_id=f"{spec['source_id_prefix']}_{reference_year}",
                    source_variable=f"single_adult_{plan_key}_midpoint_plus20",
                    source_url=_official_url(spec["filename"]),
                    source_release=f"USDA {spec['plan_label']} Food Plan archive",
                    source_reference_period=str(reference_year),
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes=(
                        "Official archive present but adult 19-50 individual monthly rows "
                        f"were not found for {reference_year}."
                    ),
                )
            )
            continue

        midpoint = (avg_male + avg_female) / 2.0
        single_adult_monthly = round(midpoint * ONE_PERSON_HOUSEHOLD_FACTOR, 2)
        single_adult_annual = round(single_adult_monthly * 12.0, 2)
        is_full_year = months_count >= 12
        period_label = (
            f"{reference_year} Annual Average ({months_count} mos)"
            if is_full_year
            else f"{reference_year} YTD FOOD COST ({months_count} mos)"
        )
        observations.append(
            LivingCostComponentObservation(
                component_id="food_low_cost"
                if plan_key == "low_cost"
                else "food_thrifty_sensitivity",
                category="food",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=single_adult_annual,
                value_monthly=single_adult_monthly,
                unit="USD",
                status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
                source_id=f"{spec['source_id_prefix']}_{reference_year}",
                source_variable=f"male_female_19_50_midpoint_x_{ONE_PERSON_HOUSEHOLD_FACTOR}",
                source_url=_official_url(spec["filename"]),
                source_release=f"USDA {spec['plan_label']} Food Plan ({period_label})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    f"USDA {spec['plan_label']} {period_label}. Age group: Individual "
                    f"Male/Female 19-50. Male monthly avg ${avg_male:.2f} "
                    f"({', '.join(male_labels)}); Female monthly avg ${avg_female:.2f} "
                    f"({', '.join(female_labels)}). Midpoint ${midpoint:.2f} × "
                    f"{ONE_PERSON_HOUSEHOLD_FACTOR:.2f} official 1-person adjustment = "
                    f"${single_adult_monthly:.2f}/mo. Raw monthly cells are MEASURED; "
                    "the midpoint and household-size adjustment are "
                    "MODELED_FROM_MEASURED_INPUTS."
                ),
            )
        )
    return observations


def parse_usda_monthly_food_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse USDA monthly food plan dataset.

    Official production path: CNPP Excel archives.
    Fixture/CSV path retained for unit tests.
    """
    if cache_dir.is_file() and cache_dir.suffix.lower() == ".xlsx":
        return build_usda_food_observations(
            cache_dir.parent,
            reference_year,
            retrieved_at=retrieved_at,
            file_sha256=file_sha256,
        )
    if cache_dir.is_dir():
        official = cache_dir / USDA_ARCHIVES["low_cost"]["filename"]
        if official.exists():
            return build_usda_food_observations(
                cache_dir,
                reference_year,
                retrieved_at=retrieved_at,
                file_sha256=file_sha256,
            )

    file_path = (
        cache_dir if cache_dir.is_file() else cache_dir / f"usda_food_plans_{reference_year}.csv"
    )
    if not file_path.exists():
        logger.warning("USDA Food Plan CSV not found: %s", file_path)
        return [
            LivingCostComponentObservation(
                component_id="food_low_cost",
                category="food",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"usda_food_low_cost_{reference_year}",
                source_variable="single_adult_low_cost_midpoint_plus20",
                source_url=USDA_FOOD_PLANS_URL,
                source_release="USDA Food Plans",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: USDA Food Plan CSV could not be found.",
            )
        ]

    monthly_by_plan: dict[str, list[dict[str, Any]]] = {"low_cost": [], "thrifty": []}
    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                plan_name = str(row.get("plan_name") or row.get("Plan") or "").strip().lower()
                target_key = None
                if "low" in plan_name:
                    target_key = "low_cost"
                elif "thrifty" in plan_name:
                    target_key = "thrifty"
                if not target_key:
                    continue
                male_cost = float(row.get("male_19_50") or row.get("male_cost") or 0.0)
                female_cost = float(row.get("female_19_50") or row.get("female_cost") or 0.0)
                month_str = str(row.get("month") or row.get("period") or "Month").strip()
                if male_cost > 0 and female_cost > 0:
                    monthly_by_plan[target_key].append(
                        {"month": month_str, "male": male_cost, "female": female_cost}
                    )
    except (OSError, ValueError, csv.Error, UnicodeError) as exc:
        logger.error("Failed to parse USDA Food Plan CSV: %s", exc)

    observations: list[LivingCostComponentObservation] = []
    for plan_key in ["low_cost", "thrifty"]:
        records = monthly_by_plan[plan_key]
        comp_id = "food_low_cost" if plan_key == "low_cost" else "food_thrifty_sensitivity"
        if not records:
            observations.append(
                LivingCostComponentObservation(
                    component_id=comp_id,
                    category="food",
                    geography_type="national",
                    geography_id="US",
                    geography_name="United States Baseline",
                    state="US",
                    reference_year=reference_year,
                    value_annual=None,
                    value_monthly=None,
                    unit="USD",
                    status=ComponentStatus.UNAVAILABLE,
                    source_id=f"usda_food_{plan_key}_{reference_year}",
                    source_variable=f"single_adult_{plan_key}_midpoint_plus20",
                    source_url=USDA_FOOD_PLANS_URL,
                    source_release="USDA Food Plans",
                    source_reference_period=str(reference_year),
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes="UNAVAILABLE: Valid monthly records could not be parsed.",
                )
            )
            continue
        months_count = len(records)
        avg_male = sum(r["male"] for r in records) / months_count
        avg_female = sum(r["female"] for r in records) / months_count
        midpoint = (avg_male + avg_female) / 2.0
        single_adult_monthly = round(midpoint * ONE_PERSON_HOUSEHOLD_FACTOR, 2)
        single_adult_annual = round(single_adult_monthly * 12.0, 2)
        is_full_year = months_count >= 12
        period_label = (
            f"{reference_year} Annual Average ({months_count} mos)"
            if is_full_year
            else f"{reference_year} YTD FOOD COST ({months_count} mos)"
        )
        observations.append(
            LivingCostComponentObservation(
                component_id=comp_id,
                category="food",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=single_adult_annual,
                value_monthly=single_adult_monthly,
                unit="USD",
                status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
                source_id=f"usda_food_{plan_key}_{reference_year}",
                source_variable=f"single_adult_{plan_key}_midpoint_plus20",
                source_url=USDA_FOOD_PLANS_URL,
                source_release=f"USDA Food Plans ({period_label})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    f"USDA {plan_key.replace('_', ' ').title()} Plan {period_label}: "
                    f"Male 19-50 avg ${avg_male:.2f}, Female 19-50 avg ${avg_female:.2f}, "
                    f"Midpoint ${midpoint:.2f} × 1.20 size factor = ${single_adult_monthly:.2f}/mo."
                ),
            )
        )
    return observations
