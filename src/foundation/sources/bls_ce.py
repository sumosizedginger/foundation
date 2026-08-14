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
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.percentiles import weighted_percentile

BLS_CE_URL = "https://www.bls.gov/cex/"


def parse_bls_ce_microdata_csv(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse BLS CE single-person consumer unit records and compute weighted P25 expenditures.

    Calculates:
    - Weighted P25 for essentials basket among positive spenders.
    - Weighted P25 for social & recreation among positive spenders.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"BLS CE file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    essentials_vals: list[float] = []
    essentials_weights: list[float] = []

    rec_vals: list[float] = []
    rec_weights: list[float] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Check family size = 1 (single-person consumer unit)
            fam_size_str = (
                row.get("FAM_SIZE") or row.get("fam_size") or row.get("family_size") or "1"
            )
            try:
                fam_size = int(float(fam_size_str))
                if fam_size != 1:
                    continue
            except ValueError:
                continue

            weight_str = row.get("FINLWT21") or row.get("weight") or row.get("cu_weight") or "1.0"
            try:
                weight = float(str(weight_str).replace(",", "").strip())
                if weight <= 0:
                    weight = 1.0
            except ValueError:
                weight = 1.0

            # Essentials spending (apparel + hygiene + housekeeping)
            ess_str = (
                row.get("essentials_expenditure")
                or row.get("apparel_and_services")
                or row.get("essentials_annual")
            )
            if ess_str is not None:
                try:
                    ess_val = float(str(ess_str).replace("$", "").replace(",", "").strip())
                    if ess_val > 0:
                        essentials_vals.append(ess_val)
                        essentials_weights.append(weight)
                except ValueError:
                    pass

            # Recreation spending (admissions + hobbies + reading)
            rec_str = (
                row.get("recreation_expenditure")
                or row.get("entertainment_modest")
                or row.get("recreation_annual")
            )
            if rec_str is not None:
                try:
                    rec_val = float(str(rec_str).replace("$", "").replace(",", "").strip())
                    if rec_val > 0:
                        rec_vals.append(rec_val)
                        rec_weights.append(weight)
                except ValueError:
                    pass

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
            source_url=BLS_CE_URL,
            source_release=f"BLS Consumer Expenditure Survey Microdata ({reference_year})",
            source_reference_period=str(reference_year),
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
                source_url=BLS_CE_URL,
                source_release=f"BLS Consumer Expenditure Survey Microdata ({reference_year})",
                source_reference_period=str(reference_year),
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
            source_url=BLS_CE_URL,
            source_release=f"BLS Consumer Expenditure Survey Microdata ({reference_year})",
            source_reference_period=str(reference_year),
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
                source_url=BLS_CE_URL,
                source_release=f"BLS Consumer Expenditure Survey Microdata ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes="UNAVAILABLE: No positive-spending single-person consumer units parsed.",
            )
        )

    return observations
