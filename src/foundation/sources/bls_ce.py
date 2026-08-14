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
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.percentiles import weighted_percentile
from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

def get_bls_ce_url(year: int) -> str:
    """Get the official BLS CE PUM Intrvw ZIP URL."""
    # Assuming standard BLS PUM URL format
    # E.g. for 2022, it's intrvw22.zip
    # Use reference_year - 2 for typical lag, or reference_year - 1 if available
    # For now, we'll map 2024 to 2022 data (intrvw22.zip) and 2026 to 2024 data (intrvw24.zip)
    data_year = year - 2
    short_yr = str(data_year)[-2:]
    return f"https://www.bls.gov/cex/pumd/data/comma/intrvw{short_yr}.zip"


def download_bls_ce_artifact(
    year: int, cache_dir: Path, force_download: bool = False
):
    """Download required BLS CE microdata ZIP."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported BLS CE reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    
    data_year = year - 2
    short_yr = str(data_year)[-2:]
    expected_filename = f"bls_ce_intrvw{short_yr}.zip"
    
    artifact = acquire_source(
        source_id=f"bls_ce_{year}",
        url=get_bls_ce_url(year),
        cache_dir=cache_dir,
        expected_filename=expected_filename,
        force_download=force_download,
    )
    
    if artifact is None:
        raise RuntimeError(f"Required BLS CE dataset for {year} is UNAVAILABLE.")
        
    return artifact


def parse_bls_ce_microdata(
    cache_dir: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse BLS CE single-person consumer unit records and compute weighted P25 expenditures from ZIP."""
    data_year = reference_year - 2
    short_yr = str(data_year)[-2:]
    zip_path = cache_dir / f"bls_ce_intrvw{short_yr}.zip"
    
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
            )
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

                        # Recreation: FEETXCQ (Admissions/Fees) + READCQ (Reading)
                        feetxcq = float(row.get("FEETXCQ") or row.get("feetxcq") or 0.0)
                        readcq = float(row.get("READCQ") or row.get("readcq") or 0.0)
                        
                        rec_val = (feetxcq + readcq) * 4.0
                        if rec_val > 0:
                            rec_vals.append(rec_val)
                            rec_weights.append(weight)

    except Exception as e:
        logger.error(f"Failed to process BLS CE ZIP: {e}")
        # Will fall through to unavailability below

    observations: list[LivingCostComponentObservation] = []

    # Calculate weighted P25 for Essentials
    if essentials_vals:
        p25_essentials = weighted_percentile(essentials_vals, essentials_weights, 0.25)
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
            status=ComponentStatus.MEASURED,
            source_id=f"bls_ce_essentials_{reference_year}",
            source_variable="single_person_weighted_p25_essentials",
            source_url=get_bls_ce_url(reference_year),
            source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
            source_reference_period=str(data_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                f"BLS CE weighted P25 expenditure for restricted necessities among single-person positive spenders "
                f"(${p25_essentials:,.2f}/yr, Sample: {len(essentials_vals):,})."
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
        p25_rec = weighted_percentile(rec_vals, rec_weights, 0.25)
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
            status=ComponentStatus.MEASURED,
            source_id=f"bls_ce_recreation_{reference_year}",
            source_variable="single_person_weighted_p25_recreation",
            source_url=get_bls_ce_url(reference_year),
            source_release=f"BLS Consumer Expenditure Survey Microdata ({data_year})",
            source_reference_period=str(data_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                f"BLS CE weighted P25 expenditure for modest social/recreation goods among single-person positive spenders "
                f"(${p25_rec:,.2f}/yr, Sample: {len(rec_vals):,})."
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
