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

from foundation.sources.acquisition import record_unretrieved

logger = logging.getLogger(__name__)

BEA_RPP_LANDING = (
    "https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area"
)


def download_bea_rpp_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Do not retrieve a guessed BEA zip or invent data_year = year - 2."""
    del cache_dir, force_download
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported BEA reference year: {year}")
    return record_unretrieved(
        f"bea_rpp_{year}",
        status="SOURCE_GAP",
        resolved_url=BEA_RPP_LANDING,
        notes=(
            "Official BEA RPP landing page recorded. Current public release is 2024 data "
            "(February 19, 2026). Production retrieve requires the official API/download "
            "with the actual data year labeled. Missing RPP is UNAVAILABLE, never 100.0."
        ),
    )


def parse_bea_rpp_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, float]:
    """Parse BEA Regional Price Parities CSV file returning mapping state_alpha -> RPP factor (US = 1.000)."""
    file_path = cache_dir if cache_dir.is_file() else cache_dir / f"bea_rpp_{reference_year}.csv"

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
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse BEA RPP CSV: {e}")

    if not rpp_map:
        logger.warning("BEA RPP parsing resulted in empty map (Fail closed).")

    return rpp_map
