"""Census American Community Survey (ACS) 5-Year Adult Population Adapter.

Retrieves, caches, and parses adult population counts (Age 18+) across all 3,143+ U.S.
counties and county-equivalents to provide empirical person weights for local aggregation.
"""

from __future__ import annotations
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CENSUS_ACS_BASE_URL = "https://api.census.gov/data/2023/acs/acs5"


def parse_acs_county_population_csv(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, dict[str, Any]]:
    """Parse real Census ACS county population CSV file.

    Returns dict mapping 5-digit county FIPS -> {
        "adult_population": int,
        "total_population": int,
        "county_name": str,
        "state": str,
        "fips": str
    }
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Census ACS file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    results: dict[str, dict[str, Any]] = {}

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Handle standard FIPS or state+county FIPS columns
            fips = row.get("fips") or row.get("GEOID") or row.get("geoid") or ""
            if not fips:
                st_code = row.get("state") or row.get("STATE") or ""
                co_code = row.get("county") or row.get("COUNTY") or ""
                if st_code and co_code:
                    fips = f"{st_code.strip().zfill(2)}{co_code.strip().zfill(3)}"

            fips = fips.strip().zfill(5)
            if len(fips) != 5 or not fips.isdigit():
                continue

            county_name = row.get("NAME") or row.get("county_name") or row.get("name") or ""
            state_alpha = row.get("state_alpha") or row.get("state_abbr") or ""

            # Extract adult population (age 18+)
            # Table B01001 or explicit adult_pop column
            adult_pop_str = (
                row.get("adult_population")
                or row.get("adult_pop")
                or row.get("pop_18_plus")
                or row.get("B01001_adult")
                or row.get("population_18_over")
            )
            if not adult_pop_str:
                # Fallback to total pop if adult pop not separated
                adult_pop_str = row.get("total_population") or row.get("B01001_001E") or row.get("population") or "0"

            try:
                adult_pop = int(float(str(adult_pop_str).replace(",", "").strip()))
            except ValueError:
                adult_pop = 0

            if adult_pop <= 0:
                continue

            results[fips] = {
                "fips": fips,
                "county_name": county_name,
                "state": state_alpha,
                "adult_population": adult_pop,
                "source_id": f"census_acs5_{reference_year}",
                "retrieved_at": retrieved_at,
                "sha256": file_sha256,
            }

    return results
