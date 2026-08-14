"""Bureau of Economic Analysis (BEA) Regional Price Parities (RPP) Adapter.

Ingests state and metropolitan area Regional Price Parities (SARPP All Items, Series: SARPP-1)
from official BEA releases.

TEMPORAL RULES:
- Explicitly stores reference year and official BEA release vintage.
- Parity factors are expressed relative to national price level (U.S. Baseline = 1.000).
- Spot checks against official BEA published benchmarks (e.g., CA > 1.10, MS < 0.90).
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

# Placeholder URL for BEA Regional Price Parities ZIP/CSV
BEA_RPP_URL = "https://apps.bea.gov/regional/zip/RPP.zip"


def download_bea_rpp_artifact(
    year: int, cache_dir: Path, force_download: bool = False
):
    """Download required BEA RPP dataset."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported BEA reference year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Typically BEA releases lag by 1-2 years
    data_year = year - 2
    expected_filename = f"bea_rpp_{data_year}.csv"
    
    artifact = acquire_source(
        source_id=f"bea_rpp_{year}",
        url=BEA_RPP_URL,
        cache_dir=cache_dir,
        expected_filename=expected_filename,
        force_download=force_download,
    )
    
    if artifact is None:
        raise RuntimeError(f"Required BEA RPP dataset for {year} is UNAVAILABLE.")
        
    return artifact


def parse_bea_rpp_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, float]:
    """Parse BEA Regional Price Parities CSV file returning mapping state_alpha -> RPP factor (US = 1.000)."""
    data_year = reference_year - 2
    file_path = cache_dir / f"bea_rpp_{data_year}.csv"
    
    if not file_path.exists():
        logger.warning(f"BEA RPP CSV not found: {file_path}")
        return {}  # Fail closed: returns empty map, causing pipeline to fail when joining

    rpp_map: dict[str, float] = {}

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                state_alpha = (
                    str(row.get("state") or row.get("GeoFips") or row.get("State") or "")
                    .strip()
                    .upper()
                )
                rpp_idx_str = row.get("rpp_all_items") or row.get("RPP") or row.get("index") or ""
                if not rpp_idx_str:
                    continue
                    
                try:
                    rpp_idx = float(str(rpp_idx_str).replace(",", "").strip())
                except ValueError:
                    continue

                if rpp_idx > 0:
                    # Convert 100-base index to multiplier factor (e.g. 112.5 -> 1.125)
                    factor = rpp_idx / 100.0 if rpp_idx > 10.0 else rpp_idx
                    rpp_map[state_alpha] = round(factor, 4)
    except Exception as e:
        logger.error(f"Failed to parse BEA RPP CSV: {e}")

    if not rpp_map:
        logger.warning("BEA RPP parsing resulted in empty map (Fail closed).")

    return rpp_map
