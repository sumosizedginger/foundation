"""Energy Information Administration (EIA) Retail Gasoline Source Adapter.

Ingests state and PADD regional regular retail gasoline prices ($/gallon) from EIA.
Outputs measured price_per_gallon ONLY (status = MEASURED).
Economic consumption modeling (miles/MPG/gallons) is strictly separated into living_cost/transportation.py.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

EIA_GAS_URL = "https://www.eia.gov/petroleum/gasdiesel/"

# Placeholder for EIA historical price CSV
EIA_GAS_CSV_URL = "https://www.eia.gov/petroleum/gasdiesel/xls/psw18vwall.csv"


def download_eia_gas_artifact(
    year: int, cache_dir: Path, force_download: bool = False
):
    """Download required EIA gasoline price dataset."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported EIA reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    
    expected_filename = f"eia_gas_{year}.csv"
    
    artifact = acquire_source(
        source_id=f"eia_gas_{year}",
        url=EIA_GAS_CSV_URL,
        cache_dir=cache_dir,
        expected_filename=expected_filename,
        force_download=force_download,
    )
    
    if artifact is None:
        raise RuntimeError(f"Required EIA dataset for {year} is UNAVAILABLE.")
        
    return artifact


def parse_eia_gas_prices_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse EIA state retail regular gasoline price dataset."""
    file_path = cache_dir / f"eia_gas_{reference_year}.csv"
    
    if not file_path.exists():
        logger.warning(f"EIA gas CSV not found: {file_path}")
        return []

    observations: list[LivingCostComponentObservation] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
                if not state_alpha:
                    continue
                    
                gas_price_str = (
                    row.get("regular_gas_price") or row.get("price_per_gal") or row.get("price") or "0"
                )
                try:
                    price_per_gal = float(str(gas_price_str).replace("$", "").replace(",", "").strip())
                except ValueError:
                    continue

                if price_per_gal <= 0:
                    continue

                obs = LivingCostComponentObservation(
                    component_id="eia_gas_price_per_gal",
                    category="transportation_input",
                    geography_type="state",
                    geography_id=state_alpha,
                    geography_name=f"{state_alpha} Regular Gasoline Price",
                    state=state_alpha,
                    reference_year=reference_year,
                    value_annual=round(price_per_gal, 3),  # Price per gallon
                    value_monthly=round(price_per_gal, 3),
                    unit="USD_PER_GALLON",
                    status=ComponentStatus.MEASURED,
                    source_id=f"eia_gas_price_{reference_year}",
                    source_variable="EMM_EPM0_PTE_R_DPG",
                    source_url=EIA_GAS_URL,
                    source_release=f"EIA Retail Gasoline Annual Average ({reference_year})",
                    source_reference_period=str(reference_year),
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes=f"EIA official measured average price for regular retail gasoline in {state_alpha}: ${price_per_gal:.3f}/gal.",
                )
                observations.append(obs)
    except Exception as e:
        logger.error(f"Failed to parse EIA Gas CSV: {e}")

    return observations
