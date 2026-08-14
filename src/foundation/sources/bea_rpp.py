"""Bureau of Economic Analysis (BEA) Regional Price Parities (RPP) Adapter.

Ingests state and metropolitan area Regional Price Parities (all items) from official BEA releases.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation

BEA_RPP_URL = "https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area"


def parse_bea_rpp_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, float]:
    """Parse BEA Regional Price Parities CSV file returning mapping state_alpha -> RPP factor (US = 1.000)."""
    if not file_path.exists():
        raise FileNotFoundError(f"BEA RPP file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    rpp_map: dict[str, float] = {}

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            state_alpha = str(row.get("state") or row.get("GeoFips") or row.get("State") or "").strip().upper()
            rpp_idx_str = row.get("rpp_all_items") or row.get("RPP") or row.get("index") or "100.0"
            try:
                rpp_idx = float(str(rpp_idx_str).replace(",", "").strip())
            except ValueError:
                continue

            if rpp_idx > 0:
                # Convert 100-base index to multiplier factor (e.g. 112.5 -> 1.125)
                factor = rpp_idx / 100.0 if rpp_idx > 10.0 else rpp_idx
                rpp_map[state_alpha] = round(factor, 4)

    return rpp_map
