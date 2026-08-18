"""EPA reference-vehicle MPG candidates (OD-004).

Constructs candidate reference-vehicle combined real-world MPG standards from
official EPA vehicle-level data. Does not freeze 24 / 28 / 32. Does not publish
a living-cost headline.

Official sources researched:
- EPA Automotive Trends Report data page
- EPA/DOE fueleconomy.gov public vehicle file (vehicles.csv.zip)
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.percentiles import weighted_percentile
from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

EPA_TRENDS_LANDING = "https://www.epa.gov/automotive-trends/explore-automotive-trends-data"
EPA_FUELEconomy_LANDING = "https://www.fueleconomy.gov/feg/download.shtml"
EPA_VEHICLES_ZIP = "https://www.fueleconomy.gov/feg/epadata/vehicles.csv.zip"
EPA_EXPECTED_FILENAME = "epa_fueleconomy_vehicles.csv.zip"

# Exact normalized EPA/DOE VClass values for canonical OD-004.
# Substring "compact" must not pull Subcompact Cars or Minicompact Cars
# into the canonical median.
CANONICAL_VCLASS_VALUES: tuple[str, ...] = ("Compact Cars", "Midsize Cars")
_CANONICAL_VCLASS_NORMALIZED: dict[str, str] = {
    "compact cars": "compact",
    "midsize cars": "midsize",
}
SENSITIVITY_VCLASS_NORMALIZED: dict[str, str] = {
    "subcompact cars": "subcompact",
    "minicompact cars": "minicompact",
}
BEV_TOKENS = ("electricity", "electric")
PHEV_TOKENS = ("plug-in", "phev")
CANONICAL_MPG_FIELD = "comb08"


def download_epa_mpg_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official EPA/DOE fueleconomy.gov vehicle-level file."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported EPA MPG project cost year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = acquire_source(
        source_id=f"epa_mpg_{year}",
        url=EPA_VEHICLES_ZIP,
        cache_dir=cache_dir,
        expected_filename=EPA_EXPECTED_FILENAME,
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        return record_unretrieved(
            f"epa_mpg_{year}",
            status="SOURCE_GAP",
            resolved_url=EPA_FUELEconomy_LANDING,
            notes=(
                "Official EPA/DOE fueleconomy.gov vehicles.csv.zip was not retrieved. "
                f"Automotive Trends landing: {EPA_TRENDS_LANDING}. "
                "24/28/32 MPG constants are forbidden (OD-004). Cohort MPG is data-derived."
            ),
        )
    return artifact


def _row_is_gasoline_ice(row: dict[str, str]) -> bool:
    fuel = str(row.get("fuelType") or row.get("fuelType1") or "").strip().lower()
    atv = str(row.get("atvType") or "").strip().lower()
    if any(tok in fuel or tok in atv for tok in BEV_TOKENS):
        return False
    if any(tok in fuel or tok in atv for tok in PHEV_TOKENS):
        return False
    if "diesel" in fuel or "e85" in fuel or "hydrogen" in fuel or "natural" in fuel:
        return False
    return "gas" in fuel or fuel in {"regular", "premium", "midgrade"}


def _normalized_vclass(row: dict[str, str]) -> str:
    return " ".join(str(row.get("VClass") or row.get("vclass") or "").split()).strip().lower()


def _row_class(row: dict[str, str]) -> str | None:
    """Canonical class is exact Compact Cars / Midsize Cars only."""
    return _CANONICAL_VCLASS_NORMALIZED.get(_normalized_vclass(row))


def _sensitivity_class(row: dict[str, str]) -> str | None:
    return SENSITIVITY_VCLASS_NORMALIZED.get(_normalized_vclass(row))


def _combined_mpg(row: dict[str, str]) -> float | None:
    """Canonical OD-004 MPG is comb08 only. No UCity / combA08 substitution."""
    raw = str(row.get(CANONICAL_MPG_FIELD) or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def _model_year(row: dict[str, str]) -> int | None:
    raw = str(row.get("year") or row.get("Year") or "").strip()
    if not raw:
        return None
    try:
        year = int(float(raw))
    except ValueError:
        return None
    return year if 1980 <= year <= 2030 else None


def filter_funnel(rows: list[dict[str, str]], cost_year: int) -> dict[str, Any]:
    """Record official filter counts required by the evidence campaign."""
    used_lo = cost_year - 12
    used_hi = cost_year - 8
    after_fuel = 0
    after_class = 0
    after_year = 0
    missing_comb08 = 0
    final_mpgs: list[float] = []
    compact_mpgs: list[float] = []
    midsize_mpgs: list[float] = []
    for row in rows:
        if not _row_is_gasoline_ice(row):
            continue
        after_fuel += 1
        klass = _row_class(row)
        if klass not in {"compact", "midsize"}:
            continue
        after_class += 1
        year = _model_year(row)
        if year is None or year < used_lo or year > used_hi:
            continue
        after_year += 1
        mpg = _combined_mpg(row)
        if mpg is None:
            missing_comb08 += 1
            continue
        final_mpgs.append(mpg)
        if klass == "compact":
            compact_mpgs.append(mpg)
        else:
            midsize_mpgs.append(mpg)
    weights = [1.0] * len(final_mpgs)
    return {
        "project_cost_year": cost_year,
        "model_year_low": used_lo,
        "model_year_high": used_hi,
        "total_source_rows": len(rows),
        "rows_after_fuel_filter": after_fuel,
        "rows_after_body_class_filter": after_class,
        "rows_after_model_year_filter": after_year,
        "rows_missing_canonical_comb08": missing_comb08,
        "final_cohort_row_count": len(final_mpgs),
        "median_mpg": (
            round(weighted_percentile(final_mpgs, weights, 0.50), 1) if final_mpgs else None
        ),
        "mean_mpg": round(sum(final_mpgs) / len(final_mpgs), 1) if final_mpgs else None,
        "compact_only_median_mpg": (
            round(weighted_percentile(compact_mpgs, [1.0] * len(compact_mpgs), 0.50), 1)
            if compact_mpgs
            else None
        ),
        "midsize_only_median_mpg": (
            round(weighted_percentile(midsize_mpgs, [1.0] * len(midsize_mpgs), 0.50), 1)
            if midsize_mpgs
            else None
        ),
        "canonical_vclass_values": list(CANONICAL_VCLASS_VALUES),
        "canonical_mpg_field": CANONICAL_MPG_FIELD,
        "filter_columns": ["fuelType", "fuelType1", "atvType", "VClass", "year", "comb08"],
    }


def build_mpg_candidates(rows: list[dict[str, str]], cost_year: int) -> list[dict[str, Any]]:
    """Candidate reference-vehicle cohorts. OD-004 canonical = used compact+midsize median."""
    used_lo = cost_year - 12
    used_hi = cost_year - 8
    new_year = 2024
    specs = [
        {
            "id": "used_compact_midsize_gasoline",
            "label": f"Used-car gasoline compact/midsize MY{used_lo}-{used_hi}",
            "years": set(range(used_lo, used_hi + 1)),
            "classes": {"compact", "midsize"},
        },
        {
            "id": "new_compact_midsize_gasoline_my2024",
            "label": "New-car gasoline compact/midsize MY2024",
            "years": {new_year},
            "classes": {"compact", "midsize"},
        },
        {
            "id": "used_compact_gasoline",
            "label": f"Used-car gasoline compact MY{used_lo}-{used_hi}",
            "years": set(range(used_lo, used_hi + 1)),
            "classes": {"compact"},
        },
        {
            "id": "used_midsize_gasoline",
            "label": f"Used-car gasoline midsize MY{used_lo}-{used_hi}",
            "years": set(range(used_lo, used_hi + 1)),
            "classes": {"midsize"},
        },
        {
            "id": "used_subcompact_minicompact_gasoline_sensitivity",
            "label": (
                f"SENSITIVITY used-car gasoline Subcompact/Minicompact Cars "
                f"MY{used_lo}-{used_hi} (not canonical)"
            ),
            "years": set(range(used_lo, used_hi + 1)),
            "classes": {"subcompact", "minicompact"},
        },
    ]
    candidates: list[dict[str, Any]] = []
    for spec in specs:
        mpgs: list[float] = []
        for row in rows:
            year = _model_year(row)
            if year is None or year not in spec["years"]:
                continue
            if not _row_is_gasoline_ice(row):
                continue
            klass = _row_class(row) or _sensitivity_class(row)
            if klass not in spec["classes"]:
                continue
            mpg = _combined_mpg(row)
            if mpg is None:
                continue
            mpgs.append(mpg)
        if not mpgs:
            candidates.append(
                {
                    "id": spec["id"],
                    "label": spec["label"],
                    "n": 0,
                    "median_mpg": None,
                    "mean_mpg": None,
                    "p25_mpg": None,
                    "p75_mpg": None,
                }
            )
            continue
        weights = [1.0] * len(mpgs)
        candidates.append(
            {
                "id": spec["id"],
                "label": spec["label"],
                "n": len(mpgs),
                "median_mpg": round(weighted_percentile(mpgs, weights, 0.50), 1),
                "mean_mpg": round(sum(mpgs) / len(mpgs), 1),
                "p25_mpg": round(weighted_percentile(mpgs, weights, 0.25), 1),
                "p75_mpg": round(weighted_percentile(mpgs, weights, 0.75), 1),
            }
        )
    return candidates


def parse_epa_mpg_candidates(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse official EPA vehicle file into OD-004 MPG candidates."""
    zip_path = cache_dir if cache_dir.is_file() else cache_dir / EPA_EXPECTED_FILENAME
    if not zip_path.exists():
        return [
            LivingCostComponentObservation(
                component_id="transport_reference_mpg",
                category="transportation_input",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="MPG",
                status=ComponentStatus.SOURCE_GAP,
                source_id=f"epa_mpg_{reference_year}",
                source_variable="comb08_gasoline_compact_midsize",
                source_url=EPA_VEHICLES_ZIP,
                source_release="EPA/DOE fueleconomy.gov vehicles file",
                source_reference_period="MY1984-present",
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: official EPA vehicles file not present. 24/28/32 not used.",
            )
        ]

    rows: list[dict[str, str]] = []
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
            if not members:
                raise ValueError("EPA vehicles zip has no CSV member")
            with archive.open(members[0]) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace")
                )
                rows = list(reader)
    except (OSError, ValueError, zipfile.BadZipFile, csv.Error, UnicodeError) as exc:
        logger.error("Failed to parse EPA vehicles file: %s", exc)
        return []

    candidates = build_mpg_candidates(rows, reference_year)
    observations: list[LivingCostComponentObservation] = []
    for cand in candidates:
        from foundation.living_cost.owner_freeze import CANONICAL_MPG_COHORT_ID

        role = (
            "CANONICAL used-car compact+midsize gasoline median (OD-004 FROZEN)"
            if cand["id"] == CANONICAL_MPG_COHORT_ID
            else "sensitivity cohort (OD-004 FROZEN)"
        )
        notes = (
            f"EPA reference-vehicle {role}: '{cand['label']}'. "
            f"Filter: gasoline non-BEV/non-PHEV; exact VClass Compact Cars + Midsize Cars; "
            f"combined real-world MPG = comb08 only. n={cand['n']}; "
            f"median={cand['median_mpg']}; mean={cand['mean_mpg']}; "
            f"P25={cand['p25_mpg']}; P75={cand['p75_mpg']}. "
            "24/28/32 are not the empirical model."
        )
        observations.append(
            LivingCostComponentObservation(
                component_id=f"transport_reference_mpg_{cand['id']}",
                category="transportation_input",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=cand["median_mpg"],
                value_monthly=None,
                unit="MPG",
                status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS
                if cand["median_mpg"] is not None
                else ComponentStatus.SOURCE_GAP,
                source_id=f"epa_mpg_{reference_year}",
                source_variable="comb08_gasoline_ice_candidate",
                source_url=EPA_VEHICLES_ZIP,
                source_release="EPA/DOE fueleconomy.gov vehicles.csv.zip",
                source_reference_period=cand["label"],
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=notes,
            )
        )
    return observations


def write_mpg_cohort_report(cache_zip: Path, dest: Path) -> dict[str, Any]:
    """Derive official EPA cohort statistics for 2024 and 2026. No MSLC."""
    raw = cache_zip.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise ValueError("EPA vehicles zip has no CSV member")
        with archive.open(members[0]) as handle:
            rows = list(
                csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8-sig", errors="replace"))
            )
    years = {str(year): filter_funnel(rows, year) for year in (2024, 2026)}
    payload = {
        "report_type": "living_cost_epa_mpg_cohorts",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "publisher": "EPA / DOE fueleconomy.gov",
        "landing_url": EPA_FUELEconomy_LANDING,
        "artifact_url": EPA_VEHICLES_ZIP,
        "artifact_filename": cache_zip.name,
        "sha256": sha,
        "byte_size": len(raw),
        "csv_member": members[0],
        "source_row_count": len(rows),
        "combined_mpg_field": CANONICAL_MPG_FIELD,
        "canonical_vclass_values": list(CANONICAL_VCLASS_VALUES),
        "canonical_mpg_field": CANONICAL_MPG_FIELD,
        "cohorts": years,
        "canonical_cohort": "used_compact_midsize_gasoline",
        "calculates_mslc": False,
    }
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
