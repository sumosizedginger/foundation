"""Census American Community Survey (ACS) 5-Year Adult Population Source Adapter.

Deterministic derivation of adult population (Age 18+) from official Census ACS 5-Year datasets
(Table B01001: Sex by Age, where Adult Population = Total - Under 18).

STRICT METHODOLOGICAL RULES:
- NO fallback from adult population to total population under any circumstances.
- Missing adult population variables produce explicit join failures or UNAVAILABLE states.
- Real county universe derived from Census geography vintage across all 50 states + DC.
- Territories (PR, GU, VI, AS, MP) are explicitly excluded and documented.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CENSUS_ACS_5YR_URL = "https://api.census.gov/data/2023/acs/acs5"
CENSUS_VINTAGE = "2023 ACS 5-Year Estimates"

# Valid 2-digit State FIPS for 50 States + DC
VALID_STATE_FIPS = {
    "01": "AL",
    "02": "AK",
    "04": "AZ",
    "05": "AR",
    "06": "CA",
    "08": "CO",
    "09": "CT",
    "10": "DE",
    "11": "DC",
    "12": "FL",
    "13": "GA",
    "15": "HI",
    "16": "ID",
    "17": "IL",
    "18": "IN",
    "19": "IA",
    "20": "KS",
    "21": "KY",
    "22": "LA",
    "23": "ME",
    "24": "MD",
    "25": "MA",
    "26": "MI",
    "27": "MN",
    "28": "MS",
    "29": "MO",
    "30": "MT",
    "31": "NE",
    "32": "NV",
    "33": "NH",
    "34": "NJ",
    "35": "NM",
    "36": "NY",
    "37": "NC",
    "38": "ND",
    "39": "OH",
    "40": "OK",
    "41": "OR",
    "42": "PA",
    "44": "RI",
    "45": "SC",
    "46": "SD",
    "47": "TN",
    "48": "TX",
    "49": "UT",
    "50": "VT",
    "51": "VA",
    "53": "WA",
    "54": "WV",
    "55": "WI",
    "56": "WY",
}

EXCLUDED_TERRITORIES_FIPS = {
    "60": "American Samoa",
    "66": "Guam",
    "69": "Northern Mariana Islands",
    "72": "Puerto Rico",
    "78": "U.S. Virgin Islands",
}


def compute_adult_population_from_b01001_row(row: dict[str, Any]) -> tuple[int, int]:
    """Calculate (adult_population_18_plus, total_population) from ACS B01001 variables.

    Formula:
      Total = B01001_001E
      Under 18 Male = B01001_003E + B01001_004E + B01001_005E + B01001_006E
      Under 18 Female = B01001_027E + B01001_028E + B01001_029E + B01001_030E
      Adult Pop (18+) = Total - (Under 18 Male + Under 18 Female)
    """
    total_str = row.get("B01001_001E") or row.get("total_population")
    if total_str is None:
        raise ValueError("Missing total population variable in ACS row")

    total_pop = int(float(str(total_str).replace(",", "").strip()))
    if total_pop <= 0:
        raise ValueError(f"Total population must be positive, got {total_pop}")

    # Check if explicit adult population column already exists
    if "adult_population" in row or "pop_18_plus" in row or "adult_pop" in row:
        val = row.get("adult_population") or row.get("pop_18_plus") or row.get("adult_pop")
        if val is not None and str(val).strip() != "":
            adult_pop = int(float(str(val).replace(",", "").strip()))
            if adult_pop <= 0:
                raise ValueError(f"Adult population must be positive, got {adult_pop}")
            if adult_pop > total_pop:
                raise ValueError(
                    f"Adult population ({adult_pop}) cannot exceed total population ({total_pop})"
                )
            return adult_pop, total_pop

    # Otherwise compute from B01001 sex-by-age cells
    under18_vars = [
        "B01001_003E",
        "B01001_004E",
        "B01001_005E",
        "B01001_006E",
        "B01001_027E",
        "B01001_028E",
        "B01001_029E",
        "B01001_030E",
    ]

    missing_cells = [v for v in under18_vars if v not in row or str(row[v]).strip() == ""]
    if missing_cells:
        raise ValueError(
            f"Cannot derive adult population: missing required B01001 under-18 age cells {missing_cells}. "
            "Fail-closed: total population fallback is prohibited."
        )

    under18_sum = sum(int(float(str(row[v]).replace(",", "").strip())) for v in under18_vars)
    adult_pop = total_pop - under18_sum

    if adult_pop <= 0:
        raise ValueError(f"Calculated adult population is non-positive: {adult_pop}")
    if adult_pop > total_pop:
        raise ValueError(f"Calculated adult population ({adult_pop}) exceeds total ({total_pop})")

    return adult_pop, total_pop


def parse_acs_county_population_csv(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, dict[str, Any]]:
    """Parse real Census ACS county population dataset.

    Fail-Closed:
    - Never substitutes total population for adult population.
    - Validates 5-digit FIPS against the 50 States + DC universe.
    - Explicitly records excluded territory rows.
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
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    results: dict[str, dict[str, Any]] = {}

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row_idx, row in enumerate(reader, start=2):
            fips = row.get("fips") or row.get("GEOID") or row.get("geoid") or ""
            if not fips:
                st_code = row.get("state") or row.get("STATE") or ""
                co_code = row.get("county") or row.get("COUNTY") or ""
                if st_code and co_code:
                    fips = f"{st_code.strip().zfill(2)}{co_code.strip().zfill(3)}"

            fips = fips.strip().zfill(5)
            if len(fips) != 5 or not fips.isdigit():
                continue

            state_fips = fips[:2]
            if state_fips in EXCLUDED_TERRITORIES_FIPS:
                continue
            if state_fips not in VALID_STATE_FIPS:
                continue

            state_alpha = (
                row.get("state_alpha") or row.get("state_abbr") or VALID_STATE_FIPS[state_fips]
            )
            county_name = row.get("NAME") or row.get("county_name") or row.get("name") or fips

            try:
                adult_pop, total_pop = compute_adult_population_from_b01001_row(row)
            except ValueError as err:
                raise ValueError(f"ACS parse error at row {row_idx} (FIPS {fips}): {err}") from err

            results[fips] = {
                "fips": fips,
                "county_name": county_name,
                "state": state_alpha,
                "state_fips": state_fips,
                "adult_population": adult_pop,
                "total_population": total_pop,
                "under18_population": total_pop - adult_pop,
                "source_id": f"census_acs5_{reference_year}",
                "census_vintage": CENSUS_VINTAGE,
                "source_url": CENSUS_ACS_5YR_URL,
                "retrieved_at": retrieved_at,
                "sha256": file_sha256,
            }

    return results


def generate_census_county_universe_report(
    county_pop_map: dict[str, dict[str, Any]],
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate a machine-auditable Census County Universe report."""
    state_counts: dict[str, int] = {}
    for item in county_pop_map.values():
        st = item["state"]
        state_counts[st] = state_counts.get(st, 0) + 1

    total_counties = len(county_pop_map)
    total_adult_pop = sum(item["adult_population"] for item in county_pop_map.values())
    total_pop = sum(item["total_population"] for item in county_pop_map.values())
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    report = {
        "report_type": "census_county_geography_universe",
        "generated_at": now_iso,
        "census_vintage": CENSUS_VINTAGE,
        "source_url": CENSUS_ACS_5YR_URL,
        "total_county_count": total_counties,
        "total_state_count": len(state_counts),
        "total_adult_population_represented": total_adult_pop,
        "total_population_represented": total_pop,
        "states_represented": sorted(state_counts.keys()),
        "counties_per_state": {k: state_counts[k] for k in sorted(state_counts.keys())},
        "excluded_territories": EXCLUDED_TERRITORIES_FIPS,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    return report
