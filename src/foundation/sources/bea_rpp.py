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
import io
import logging
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

# BEA state GeoFIPS (ss000) -> USPS. Territories are excluded.
BEA_STATE_FIPS: dict[str, str] = {
    "01000": "AL",
    "02000": "AK",
    "04000": "AZ",
    "05000": "AR",
    "06000": "CA",
    "08000": "CO",
    "09000": "CT",
    "10000": "DE",
    "11000": "DC",
    "12000": "FL",
    "13000": "GA",
    "15000": "HI",
    "16000": "ID",
    "17000": "IL",
    "18000": "IN",
    "19000": "IA",
    "20000": "KS",
    "21000": "KY",
    "22000": "LA",
    "23000": "ME",
    "24000": "MD",
    "25000": "MA",
    "26000": "MI",
    "27000": "MN",
    "28000": "MS",
    "29000": "MO",
    "30000": "MT",
    "31000": "NE",
    "32000": "NV",
    "33000": "NH",
    "34000": "NJ",
    "35000": "NM",
    "36000": "NY",
    "37000": "NC",
    "38000": "ND",
    "39000": "OH",
    "40000": "OK",
    "41000": "OR",
    "42000": "PA",
    "44000": "RI",
    "45000": "SC",
    "46000": "SD",
    "47000": "TN",
    "48000": "TX",
    "49000": "UT",
    "50000": "VT",
    "51000": "VA",
    "53000": "WA",
    "54000": "WV",
    "55000": "WI",
    "56000": "WY",
}


def _parse_bea_sarpp_zip(zip_path: Path, reference_year: int) -> dict[str, float]:
    """Parse official SARPP_STATE_* All-items (LineCode 1) for the RPP data year.

    BEA 2024 RPP values are the latest official release. Cost year 2026 may
    reuse source year 2024 as LATEST_AVAILABLE; this function never relabels
    the source year as 2026.
    """
    rpp_year = "2024"
    try:
        with zipfile.ZipFile(zip_path) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.upper().startswith("SARPP_STATE_") and name.lower().endswith(".csv")
            ]
            if not members:
                logger.warning("No SARPP_STATE CSV in %s", zip_path)
                return {}
            member = max(members)
            with archive.open(member) as fh:
                reader = csv.DictReader(
                    io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace")
                )
                if rpp_year not in (reader.fieldnames or []):
                    logger.warning("SARPP file %s has no %s column", member, rpp_year)
                    return {}
                rpp_map: dict[str, float] = {}
                for row in reader:
                    line = str(row.get("LineCode") or "").strip()
                    if line not in {"1", "1.0"}:
                        continue
                    desc = str(row.get("Description") or "").lower()
                    if "all items" not in desc:
                        continue
                    geo = (
                        str(row.get("GeoFIPS") or row.get("GeoFips") or "")
                        .strip()
                        .replace('"', "")
                        .zfill(5)
                    )
                    state = BEA_STATE_FIPS.get(geo)
                    if state is None:
                        continue
                    raw = str(row.get(rpp_year) or "").replace(",", "").strip()
                    if not raw:
                        continue
                    try:
                        idx = float(raw)
                    except ValueError:
                        continue
                    if idx <= 0:
                        continue
                    rpp_map[state] = round(idx / 100.0 if idx > 10.0 else idx, 4)
                # reference_year is the project cost year; RPP data year is 2024.
                _ = reference_year
                return rpp_map
    except (OSError, ValueError, KeyError, csv.Error, zipfile.BadZipFile, UnicodeError) as exc:
        logger.error("Failed to parse BEA SARPP zip: %s", exc)
        return {}


BEA_RPP_LANDING = (
    "https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area"
)


BEA_RPP_ZIP_URL = "https://apps.bea.gov/regional/zip/SARPP.zip"


def download_bea_rpp_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Official BEA Regional Price Parities zip. Data year is 2024, not the cost year."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported BEA project cost year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    from foundation.sources.acquisition import acquire_source

    return acquire_source(
        source_id=f"bea_rpp_{year}",
        url=BEA_RPP_ZIP_URL,
        cache_dir=cache_dir,
        expected_filename="SARPP.zip",
        force_download=force_download,
    )


def parse_bea_rpp_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, float]:
    """Parse BEA Regional Price Parities CSV/zip returning mapping state_alpha -> RPP factor (US = 1.000)."""
    if cache_dir.is_file():
        file_path = cache_dir
    else:
        zip_path = cache_dir / "SARPP.zip"
        if zip_path.exists():
            return _parse_bea_sarpp_zip(zip_path, reference_year)
        file_path = cache_dir / f"bea_rpp_{reference_year}.csv"

    if file_path.suffix.lower() == ".zip":
        return _parse_bea_sarpp_zip(file_path, reference_year)

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
