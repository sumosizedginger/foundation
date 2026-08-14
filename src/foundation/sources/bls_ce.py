"""BLS Consumer Expenditure (CE) Survey Source Adapter.

Calculates weighted lower-quartile (P25) annual expenditures directly from BLS Consumer Expenditure
single-person consumer unit microdata/tables for:
1. Restricted Essentials Basket (Apparel, Personal Hygiene, Cleaning Supplies, Household Linens).
2. Modest Social Participation & Recreation (Admissions, Hobbies, Reading, Modest Civic/Social Goods).

DOUBLE-COUNT PREVENTION ALLOWLIST / DENYLIST:
- ALLOWLIST (Essentials): Apparel/footwear replacement, laundry, soap/hygiene, household cleaning products.
- DENYLIST: Rent/mortgage (HUD), utilities/power (HUD), food at home (USDA), healthcare/insurance (CMS/MEPS), vehicle/gas/transit (FHWA/EIA/NAIC), luxury goods, vacations, alcohol/tobacco.
- ALLOWLIST (Recreation): Community activities, reading materials, modest entertainment admissions, hobby supplies.
- POPULATION FILTER: Single-person consumer units (FAM_SIZE = 1) with positive annual spending (> $0) in the category.
- WEIGHTING: Consumer Unit final calibration weight (FINLWT21).
"""

from __future__ import annotations

import csv
import logging
import zipfile
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.percentiles import weighted_percentile
from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

BLS_CE_LANDING = "https://www.bls.gov/cex/pumd_data.htm"
BLS_CE_DICTIONARY = "https://www.bls.gov/cex/pumd/ce-pumd-interview-diary-dictionary.xlsx"

# Explicit Interview-year pin. Do not invent a 2026 Interview file.
# 2024 cost year uses 2024 Interview. 2026 cost year uses the latest published Interview (2024).
BLS_CE_INTERVIEW_YEAR: dict[int, int] = {
    2024: 2024,
    2026: 2024,
}


def get_bls_ce_interview_year(cost_year: int) -> int:
    if cost_year not in BLS_CE_INTERVIEW_YEAR:
        raise ValueError(f"Unsupported BLS CE cost year: {cost_year}")
    return BLS_CE_INTERVIEW_YEAR[cost_year]


def get_bls_ce_url(year: int) -> str:
    """Official BLS CE Interview CSV zip for the pinned Interview year."""
    interview_year = get_bls_ce_interview_year(year)
    short_yr = str(interview_year)[-2:]
    # 2022+ Interview files live under /csv/, not the legacy /comma/ path.
    return f"https://www.bls.gov/cex/pumd/data/csv/intrvw{short_yr}.zip"


def _existing_interview_zip(cache_dir: Path, short_yr: str) -> Path | None:
    for name in (f"bls_ce_intrvw{short_yr}.zip", f"intrvw{short_yr}.zip"):
        path = cache_dir / name
        if path.is_file() and path.stat().st_size > 1_000_000:
            return path
    return None


def download_bls_ce_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Download official BLS CE Interview CSV zip, or reuse a valid cached copy."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported BLS CE reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)

    data_year = get_bls_ce_interview_year(year)
    short_yr = str(data_year)[-2:]
    expected_filename = f"bls_ce_intrvw{short_yr}.zip"

    cached = None if force_download else _existing_interview_zip(cache_dir, short_yr)
    if cached is not None:
        artifact = acquire_source(
            source_id=f"bls_ce_{year}",
            url=get_bls_ce_url(year),
            cache_dir=cache_dir,
            expected_filename=cached.name,
            force_download=False,
        )
        if artifact is not None:
            return artifact

    artifact = acquire_source(
        source_id=f"bls_ce_{year}",
        url=get_bls_ce_url(year),
        cache_dir=cache_dir,
        expected_filename=expected_filename,
        force_download=force_download,
    )

    if artifact is None:
        return record_unretrieved(
            f"bls_ce_{year}",
            status="UNAVAILABLE",
            resolved_url=get_bls_ce_url(year),
            notes=(
                f"Official BLS CE Interview {data_year} CSV zip was not retrieved "
                f"from the PUMD landing page ({BLS_CE_LANDING} → {get_bls_ce_url(year)}). "
                "A 403 from one client is not treated as source nonexistence; "
                "the official CSV path remains https://www.bls.gov/cex/pumd/data/csv/"
                f"intrvw{short_yr}.zip."
            ),
        )

    return artifact


def parse_bls_ce_microdata(
    cache_dir: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse BLS CE single-person consumer unit records and compute weighted P25 expenditures from ZIP."""
    data_year = get_bls_ce_interview_year(reference_year)
    short_yr = str(data_year)[-2:]
    if cache_dir.is_file():
        zip_path = cache_dir
    else:
        found = _existing_interview_zip(cache_dir, short_yr)
        zip_path = found if found is not None else cache_dir / f"bls_ce_intrvw{short_yr}.zip"

    if not zip_path.exists():
        logger.warning(f"BLS CE ZIP not found: {zip_path}")
        return [
            LivingCostComponentObservation(
                component_id="essentials_basket",
                category="essentials",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"bls_ce_essentials_{reference_year}",
                source_variable="single_person_weighted_p25_essentials",
                source_url=get_bls_ce_url(reference_year),
                source_release=f"BLS CE Survey Microdata ({data_year})",
                source_reference_period=str(data_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: BLS CE ZIP could not be found.",
            ),
            LivingCostComponentObservation(
                component_id="social_recreation",
                category="social_recreation",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"bls_ce_recreation_{reference_year}",
                source_variable="single_person_weighted_p25_recreation",
                source_url=get_bls_ce_url(reference_year),
                source_release=f"BLS CE Survey Microdata ({data_year})",
                source_reference_period=str(data_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: BLS CE ZIP could not be found.",
            ),
        ]

    essentials_vals: list[float] = []
    essentials_weights: list[float] = []

    rec_vals: list[float] = []
    rec_weights: list[float] = []

    try:
        with zipfile.ZipFile(zip_path) as z:
            fmli_files = [f for f in z.namelist() if "fmli" in f.lower() and f.endswith(".csv")]

            for fmli_file in fmli_files:
                with z.open(fmli_file) as fh:
                    import io

                    text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                    reader = csv.DictReader(text_fh)
                    fields = {name.upper() for name in (reader.fieldnames or [])}
                    required = {"FAM_SIZE", "FINLWT21", "APPARCQ", "PERSCACQ", "HOUSEQCQ", "READCQ"}
                    if not required.issubset(fields):
                        raise ValueError(
                            f"BLS CE FMLI file {fmli_file} missing required columns "
                            f"{sorted(required - fields)}"
                        )

                    for row in reader:
                        fam_size_str = row.get("FAM_SIZE") or row.get("fam_size") or "0"
                        try:
                            fam_size = int(float(fam_size_str))
                            if fam_size != 1:
                                continue
                        except ValueError:
                            continue

                        weight_str = row.get("FINLWT21") or row.get("finlwt21") or "0.0"
                        try:
                            weight = float(weight_str)
                            if weight <= 0:
                                continue
                        except ValueError:
                            continue

                        # Essentials: APPARCQ (Apparel) + PERSCACQ (Personal Care) + HOUSEQCQ (Housekeeping)
                        apparcq = float(row.get("APPARCQ") or row.get("apparcq") or 0.0)
                        perscacq = float(row.get("PERSCACQ") or row.get("perscacq") or 0.0)
                        houseqcq = float(row.get("HOUSEQCQ") or row.get("houseqcq") or 0.0)

                        # Note: Quarterly spending is annualized by multiplying by 4
                        ess_val = (apparcq + perscacq + houseqcq) * 4.0
                        if ess_val > 0:
                            essentials_vals.append(ess_val)
                            essentials_weights.append(weight)

                        # Recreation allowlist at FMLI summary level:
                        # READCQ (reading) + ENTERTCQ (entertainment). FEETXCQ is
                        # not present on 2024 Interview FMLI files.
                        entertcq = float(row.get("ENTERTCQ") or row.get("entertcq") or 0.0)
                        readcq = float(row.get("READCQ") or row.get("readcq") or 0.0)

                        rec_val = (entertcq + readcq) * 4.0
                        if rec_val > 0:
                            rec_vals.append(rec_val)
                            rec_weights.append(weight)

    except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile, UnicodeError) as e:
        logger.error(f"Failed to process BLS CE ZIP: {e}")
        # Will fall through to unavailability below

    observations: list[LivingCostComponentObservation] = []

    # Calculate weighted P25 for Essentials
    if essentials_vals:
        p20_essentials = weighted_percentile(essentials_vals, essentials_weights, 0.20)
        p25_essentials = weighted_percentile(essentials_vals, essentials_weights, 0.25)
        p30_essentials = weighted_percentile(essentials_vals, essentials_weights, 0.30)
        obs_ess = LivingCostComponentObservation(
            component_id="essentials_basket",
            category="essentials",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=round(p25_essentials, 2),
            value_monthly=round(p25_essentials / 12.0, 2),
            unit="USD",
            status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
            source_id=f"bls_ce_essentials_{reference_year}",
            source_variable="FMLI_APPARCQ_PERSCACQ_HOUSEQCQ_p20_p25_p30",
            source_url=get_bls_ce_url(reference_year),
            source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
            source_reference_period=str(data_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                "MODELED_FROM_MEASURED_INPUTS from FMLI summary allowlist "
                "APPARCQ+PERSCACQ+HOUSEQCQ (not a frozen UCC list). "
                f"P20=${p20_essentials:,.2f}; P25=${p25_essentials:,.2f}; "
                f"P30=${p30_essentials:,.2f}/yr among single-person positive spenders "
                f"(n={len(essentials_vals):,}). P25 stored as the candidate only; not frozen."
            ),
        )
        observations.append(obs_ess)
    else:
        observations.append(
            LivingCostComponentObservation(
                component_id="essentials_basket",
                category="essentials",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"bls_ce_essentials_{reference_year}",
                source_variable="single_person_weighted_p25_essentials",
                source_url=get_bls_ce_url(reference_year),
                source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
                source_reference_period=str(data_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: No positive-spending single-person consumer units parsed.",
            )
        )

    # Calculate weighted P25 for Social Recreation
    if rec_vals:
        p20_rec = weighted_percentile(rec_vals, rec_weights, 0.20)
        p25_rec = weighted_percentile(rec_vals, rec_weights, 0.25)
        p30_rec = weighted_percentile(rec_vals, rec_weights, 0.30)
        obs_rec = LivingCostComponentObservation(
            component_id="social_recreation",
            category="social_recreation",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=round(p25_rec, 2),
            value_monthly=round(p25_rec / 12.0, 2),
            unit="USD",
            status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
            source_id=f"bls_ce_recreation_{reference_year}",
            source_variable="FMLI_ENTERTCQ_READCQ_p20_p25_p30",
            source_url=get_bls_ce_url(reference_year),
            source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
            source_reference_period=str(data_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                "MODELED_FROM_MEASURED_INPUTS from FMLI READCQ+ENTERTCQ "
                "(no UCC allowlist freeze; FEETXCQ absent on 2024 FMLI). "
                f"P20=${p20_rec:,.2f}; P25=${p25_rec:,.2f}; P30=${p30_rec:,.2f}/yr "
                f"among single-person positive spenders (n={len(rec_vals):,}). "
                "No recreation percentile is frozen as the headline."
            ),
        )
        observations.append(obs_rec)
    else:
        observations.append(
            LivingCostComponentObservation(
                component_id="social_recreation",
                category="social_recreation",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.UNAVAILABLE,
                source_id=f"bls_ce_recreation_{reference_year}",
                source_variable="single_person_weighted_p25_recreation",
                source_url=get_bls_ce_url(reference_year),
                source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
                source_reference_period=str(data_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: No positive-spending single-person consumer units parsed.",
            )
        )

    return observations


def _weighted_mean(values: list[float], weights: list[float]) -> float | None:
    if not values or not weights or sum(weights) <= 0:
        return None
    return sum(v * w for v, w in zip(values, weights, strict=True)) / sum(weights)


def parse_bls_ce_maintenance_candidates(
    cache_dir: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, Any]:
    """Candidate maintenance/repair/tire statistics for OD-007. Not frozen.

    Population: single-person vehicle-owning consumer units.
    Includes zero-spend periods in mean/median. Also emits P25/P50 among
    positive spenders. Splits MAINRPCQ / TIRECQ when those FMLI columns exist.
    """
    data_year = get_bls_ce_interview_year(reference_year)
    short_yr = str(data_year)[-2:]
    if cache_dir.is_file():
        zip_path = cache_dir
    else:
        found = _existing_interview_zip(cache_dir, short_yr)
        zip_path = found if found is not None else cache_dir / f"bls_ce_intrvw{short_yr}.zip"
    empty = {
        "status": "UNAVAILABLE",
        "source_data_year": data_year,
        "notes": "BLS CE Interview zip not present.",
        "candidates": {},
    }
    if not zip_path.exists():
        return empty

    combined_all: list[tuple[float, float]] = []
    maint_all: list[tuple[float, float]] = []
    tire_all: list[tuple[float, float]] = []
    columns_seen: set[str] = set()
    try:
        with zipfile.ZipFile(zip_path) as z:
            fmli_files = [f for f in z.namelist() if "fmli" in f.lower() and f.endswith(".csv")]
            for fmli_file in fmli_files:
                with z.open(fmli_file) as fh:
                    import io

                    text_fh = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                    reader = csv.DictReader(text_fh)
                    fields = {name.upper(): name for name in (reader.fieldnames or [])}
                    columns_seen.update(fields)
                    if "FAM_SIZE" not in fields or "FINLWT21" not in fields:
                        continue
                    veh_col = next(
                        (fields[n] for n in ("VEHQ", "VEHQL", "NUM_AUTO") if n in fields),
                        None,
                    )
                    maint_col = next(
                        (fields[n] for n in ("MAINRPCQ", "VRNTLOCQ") if n in fields),
                        None,
                    )
                    tire_col = fields.get("TIRECQ")
                    if maint_col is None and tire_col is None:
                        continue
                    for row in reader:
                        try:
                            if int(float(row.get(fields["FAM_SIZE"]) or 0)) != 1:
                                continue
                            weight = float(row.get(fields["FINLWT21"]) or 0.0)
                        except ValueError:
                            continue
                        if weight <= 0:
                            continue
                        if veh_col is not None:
                            try:
                                veh = float(row.get(veh_col) or 0.0)
                            except ValueError:
                                continue
                            if veh <= 0:
                                continue
                        maint_q = 0.0
                        tire_q = 0.0
                        if maint_col:
                            try:
                                maint_q = float(row.get(maint_col) or 0.0)
                            except ValueError:
                                maint_q = 0.0
                        if tire_col:
                            try:
                                tire_q = float(row.get(tire_col) or 0.0)
                            except ValueError:
                                tire_q = 0.0
                        maint_a = max(maint_q, 0.0) * 4.0
                        tire_a = max(tire_q, 0.0) * 4.0
                        combined_all.append((maint_a + tire_a, weight))
                        maint_all.append((maint_a, weight))
                        tire_all.append((tire_a, weight))
    except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile, UnicodeError) as exc:
        logger.error("Failed to parse CE maintenance candidates: %s", exc)
        return {
            "status": "UNAVAILABLE",
            "source_data_year": data_year,
            "notes": f"Parse failed: {exc}",
            "candidates": {},
        }

    def _stats(pairs: list[tuple[float, float]]) -> dict[str, float | int | None]:
        if not pairs:
            return {
                "n": 0,
                "mean_incl_zero": None,
                "median_incl_zero": None,
                "p25_positive": None,
                "p50_positive": None,
                "n_positive": 0,
            }
        vals = [p[0] for p in pairs]
        wts = [p[1] for p in pairs]
        pos_vals = [p[0] for p in pairs if p[0] > 0]
        pos_wts = [p[1] for p in pairs if p[0] > 0]
        return {
            "n": len(pairs),
            "mean_incl_zero": None if not vals else round(_weighted_mean(vals, wts) or 0.0, 2),
            "median_incl_zero": None
            if not vals
            else round(weighted_percentile(vals, wts, 0.50), 2),
            "p25_positive": None
            if not pos_vals
            else round(weighted_percentile(pos_vals, pos_wts, 0.25), 2),
            "p50_positive": None
            if not pos_vals
            else round(weighted_percentile(pos_vals, pos_wts, 0.50), 2),
            "n_positive": len(pos_vals),
        }

    candidates = {
        "maintenance_repairs_tires_combined": _stats(combined_all),
        "routine_maintenance_repairs": _stats(maint_all),
        "tires": _stats(tire_all),
    }
    return {
        "status": "MODELED_FROM_MEASURED_INPUTS" if combined_all else "UNAVAILABLE",
        "source_data_year": data_year,
        "project_cost_year": reference_year,
        "translation_method": "NONE" if reference_year == data_year else "CPI_UPDATED_CANDIDATE",
        "price_index_series": None
        if reference_year == data_year
        else "CPI-U motor vehicle maintenance and repair (not applied)",
        "columns_present": sorted(
            c for c in columns_seen if c in {"MAINRPCQ", "TIRECQ", "VEHQ", "VEHQL"}
        ),
        "notes": (
            "OD-007 candidates among single-person vehicle-owning CE units. "
            "Zero-spend periods included in mean/median. P25/P50 also computed among "
            "positive spenders. Not frozen. $1,200 is not used."
        ),
        "candidates": candidates,
        "retrieved_at": retrieved_at,
        "source_artifact_sha256": file_sha256,
    }
