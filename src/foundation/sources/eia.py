"""Energy Information Administration (EIA) Retail Gasoline Source Adapter.

Ingests state and PADD regional regular retail gasoline prices ($/gallon) from EIA.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

EIA_GAS_URL = "https://www.eia.gov/petroleum/gasdiesel/"


def parse_eia_gas_prices_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse EIA state retail gasoline price dataset."""
    if not file_path.exists():
        raise FileNotFoundError(f"EIA gas file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    observations: list[LivingCostComponentObservation] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
            gas_price_str = row.get("regular_gas_price") or row.get("price_per_gal") or row.get("price") or "0"
            try:
                price_per_gal = float(str(gas_price_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if price_per_gal <= 0:
                continue

            # Compute annual fuel cost based on FHWA baseline 11,000 miles at 28 MPG
            annual_gallons = 11000.0 / 28.0
            annual_fuel_cost = round(annual_gallons * price_per_gal, 2)

            obs = LivingCostComponentObservation(
                component_id="transport_fuel",
                category="transportation",
                geography_type="state",
                geography_id=state_alpha,
                geography_name=f"{state_alpha} Retail Gasoline",
                state=state_alpha,
                reference_year=reference_year,
                value_annual=annual_fuel_cost,
                value_monthly=round(annual_fuel_cost / 12.0, 2),
                unit="USD",
                status=ComponentStatus.MEASURED,
                source_id=f"eia_gas_{reference_year}",
                source_variable="EMM_EPM0_PTE_R_DPG",
                source_url=EIA_GAS_URL,
                source_release=f"EIA Retail Gasoline Annual Average ({reference_year})",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"EIA regular retail gasoline price: ${price_per_gal:.2f}/gal (FHWA 11,000 mi @ 28 mpg = {annual_gallons:.1f} gal/yr).",
            )
            observations.append(obs)

    return observations
