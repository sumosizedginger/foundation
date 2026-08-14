"""Energy Information Administration (EIA) Retail Gasoline Source Adapter.

Ingests state and PADD regional regular retail gasoline prices ($/gallon) from EIA.
Outputs measured price_per_gallon ONLY (status = MEASURED).
Economic consumption modeling (miles/MPG/gallons) is strictly separated into living_cost/transportation.py.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

EIA_GAS_URL = "https://www.eia.gov/petroleum/gasdiesel/"


def parse_eia_gas_prices_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse EIA state retail regular gasoline price dataset."""
    if not file_path.exists():
        raise FileNotFoundError(f"EIA gas file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    observations: list[LivingCostComponentObservation] = []

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
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

    return observations
