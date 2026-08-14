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

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

# Frozen population-weight vintage for BOTH 2024 and 2026 cost years.
ACS_WEIGHT_VINTAGE_YEAR = 2024
CENSUS_VINTAGE = "2024 ACS 5-Year Estimates"

# Required B01001 variables for Adult Population (18+)
ACS_VARS = [
    "NAME",
    "B01001_001E",  # Total Pop
    "B01001_003E",  # M Under 5
    "B01001_004E",  # M 5-9
    "B01001_005E",  # M 10-14
    "B01001_006E",  # M 15-17
    "B01001_027E",  # F Under 5
    "B01001_028E",  # F 5-9
    "B01001_029E",  # F 10-14
    "B01001_030E",  # F 15-17
]

CENSUS_ACS_5YR_BASE = f"https://api.census.gov/data/{ACS_WEIGHT_VINTAGE_YEAR}/acs/acs5"
CENSUS_ACS_5YR_URL = f"{CENSUS_ACS_5YR_BASE}?get={','.join(ACS_VARS)}&for=county:*"

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


def _census_api_url(state_fips: str | None = None) -> str:
    vars_q = ",".join(ACS_VARS)
    if state_fips:
        url = f"{CENSUS_ACS_5YR_BASE}?get={vars_q}&for=county:*&in=state:{state_fips}"
    else:
        url = CENSUS_ACS_5YR_URL
    api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if api_key:
        url = f"{url}&key={api_key}"
    return url


ACS_SUMMARY_B01001_URL = (
    "https://www2.census.gov/programs-surveys/acs/summary_file/2024/"
    "table-based-SF/data/5YRData/acsdt5y2024-b01001.dat"
)
ACS_SUMMARY_FILENAME = "acsdt5y2024-b01001.dat"


def download_acs_county_population_artifact(
    year: int,
    cache_dir: Path,
    force_download: bool = False,
):
    """Retrieve official ACS 5-Year B01001 county rows for the frozen weight vintage.

    Cost year 2024 and 2026 share ACS_WEIGHT_VINTAGE_YEAR so vintage changes
    are not confounded with cost-year changes.
    """
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported Census ACS project cost year: {year}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    # Official no-key bulk file is the production retrieve path.
    artifact = acquire_source(
        source_id=f"census_acs5_{year}",
        url=ACS_SUMMARY_B01001_URL,
        cache_dir=cache_dir,
        expected_filename=ACS_SUMMARY_FILENAME,
        force_download=force_download,
    )
    if artifact is not None:
        return artifact

    expected = f"acs_{ACS_WEIGHT_VINTAGE_YEAR}_5yr_county_b01001.json"
    destination = cache_dir / expected
    if destination.exists() and not force_download:
        return acquire_source(
            source_id=f"census_acs5_{year}",
            url=_census_api_url(),
            cache_dir=cache_dir,
            expected_filename=expected,
            force_download=False,
        )

    import hashlib
    import json as json_mod

    import requests

    from foundation.living_cost.manifest import RetrievedSourceArtifact
    from foundation.sources.acquisition import write_retrieval_sidecar
    from foundation.sources.http import download_file

    merged: list[list[Any]] = []
    header_row: list[str] | None = None
    errors: list[str] = []

    # Prefer one national call when a key is present; otherwise fetch by state.
    api_key = os.environ.get("CENSUS_API_KEY", "").strip()
    if api_key:
        try:
            download_file(url=_census_api_url(), destination=destination)
            return acquire_source(
                source_id=f"census_acs5_{year}",
                url=_census_api_url(),
                cache_dir=cache_dir,
                expected_filename=expected,
                force_download=False,
            )
        except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
            logger.warning("National ACS query failed (%s); trying per-state.", exc)

    for state_fips in VALID_STATE_FIPS:
        url = _census_api_url(state_fips)
        tmp = cache_dir / f"_acs_state_{state_fips}.json"
        try:
            download_file(url=url, destination=tmp)
            payload = json_mod.loads(tmp.read_text(encoding="utf-8"))
            if not isinstance(payload, list) or len(payload) < 2:
                raise ValueError(f"unexpected ACS payload for state {state_fips}")
            if header_row is None:
                header_row = [str(x) for x in payload[0]]
            merged.extend(payload[1:])
        except (
            OSError,
            RuntimeError,
            ValueError,
            json_mod.JSONDecodeError,
            requests.RequestException,
        ) as exc:
            errors.append(f"{state_fips}:{exc}")
        finally:
            tmp.unlink(missing_ok=True)

    if header_row is None or not merged:
        return record_unretrieved(
            f"census_acs5_{year}",
            status="SOURCE_GAP",
            resolved_url=CENSUS_ACS_5YR_URL,
            notes=(
                "Could not retrieve ACS 5-Year B01001 county rows. "
                f"Set CENSUS_API_KEY to use the national query. Errors: {errors[:5]}"
            ),
        )

    body = [header_row, *merged]
    raw = json_mod.dumps(body).encode("utf-8")
    tmp_out = destination.with_suffix(destination.suffix + ".part")
    tmp_out.write_bytes(raw)
    tmp_out.replace(destination)
    sha = hashlib.sha256(raw).hexdigest()
    retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    write_retrieval_sidecar(
        destination,
        source_id=f"census_acs5_{year}",
        url=CENSUS_ACS_5YR_URL,
        retrieved_at=retrieved_at,
        sha256=sha,
        byte_size=len(raw),
        http_status=200,
        content_type="application/json",
    )
    return RetrievedSourceArtifact(
        source_id=f"census_acs5_{year}",
        retrieved_at=retrieved_at,
        sha256=sha,
        byte_size=len(raw),
        local_cache_filename=expected,
        validation_status="RETRIEVED_UNVALIDATED",
        resolved_url=CENSUS_ACS_5YR_URL,
        notes=(
            f"Weight vintage {CENSUS_VINTAGE} assembled from per-state county queries "
            f"for cost year {year}. States failed: {len(errors)}."
        ),
    )


def compute_adult_population_from_b01001_row(row: dict[str, Any]) -> tuple[int, int]:
    """Calculate (adult_population_18_plus, total_population) from ACS B01001 variables."""
    total_str = row.get("B01001_001E") or row.get("B01001_E001")
    if total_str is None:
        raise ValueError("Missing total population variable in ACS row")

    total_pop = int(float(str(total_str).replace(",", "").strip()))
    if total_pop <= 0:
        raise ValueError(f"Total population must be positive, got {total_pop}")

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
    aliases = {
        "B01001_003E": "B01001_E003",
        "B01001_004E": "B01001_E004",
        "B01001_005E": "B01001_E005",
        "B01001_006E": "B01001_E006",
        "B01001_027E": "B01001_E027",
        "B01001_028E": "B01001_E028",
        "B01001_029E": "B01001_E029",
        "B01001_030E": "B01001_E030",
    }
    resolved: dict[str, Any] = {}
    for api_name in under18_vars:
        if api_name in row and str(row[api_name]).strip() != "":
            resolved[api_name] = row[api_name]
        elif aliases[api_name] in row and str(row[aliases[api_name]]).strip() != "":
            resolved[api_name] = row[aliases[api_name]]
    missing_cells = [v for v in under18_vars if v not in resolved]
    row = {**row, **resolved}
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


def parse_acs_summary_dat(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, dict[str, Any]]:
    """Parse official ACS 5-Year table-based summary file for B01001 (pipe-delimited)."""
    results: dict[str, dict[str, Any]] = {}
    with file_path.open("r", encoding="utf-8", errors="replace") as fh:
        header = fh.readline().rstrip("\n").split("|")
        for line in fh:
            cols = line.rstrip("\n").split("|")
            if len(cols) != len(header):
                continue
            row = dict(zip(header, cols))
            geo = str(row.get("GEO_ID") or "")
            if not geo.startswith("0500000US") or len(geo) < 14:
                continue
            fips = geo[-5:]
            state_fips = fips[:2]
            if state_fips in EXCLUDED_TERRITORIES_FIPS or state_fips not in VALID_STATE_FIPS:
                continue
            adult_pop, total_pop = compute_adult_population_from_b01001_row(row)
            results[fips] = {
                "fips": fips,
                "county_name": geo,
                "state": VALID_STATE_FIPS[state_fips],
                "state_fips": state_fips,
                "adult_population": adult_pop,
                "total_population": total_pop,
                "under18_population": total_pop - adult_pop,
                "source_id": f"census_acs5_{reference_year}",
                "census_vintage": CENSUS_VINTAGE,
                "source_url": ACS_SUMMARY_B01001_URL,
                "retrieved_at": retrieved_at,
                "sha256": file_sha256,
            }
    return results


def parse_acs_county_population_json(
    file_path: Path,
    reference_year: int = 2024,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> dict[str, dict[str, Any]]:
    """Parse Census ACS county population from official JSON API or summary-file .dat."""
    if file_path.suffix.lower() == ".dat":
        return parse_acs_summary_dat(file_path, reference_year, retrieved_at, file_sha256)
    if not file_path.exists():
        raise FileNotFoundError(f"Census ACS file not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, list) or len(data) < 2:
        raise ValueError(f"Invalid ACS JSON format in {file_path}")

    headers = data[0]
    results: dict[str, dict[str, Any]] = {}

    for row_idx, row_values in enumerate(data[1:], start=2):
        row = dict(zip(headers, row_values))

        st_code = row.get("state", "")
        co_code = row.get("county", "")
        if not st_code or not co_code:
            continue

        fips = f"{st_code.strip().zfill(2)}{co_code.strip().zfill(3)}"
        if len(fips) != 5 or not fips.isdigit():
            continue

        state_fips = fips[:2]
        if state_fips in EXCLUDED_TERRITORIES_FIPS:
            continue
        if state_fips not in VALID_STATE_FIPS:
            continue

        state_alpha = VALID_STATE_FIPS[state_fips]
        county_name = row.get("NAME") or fips

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
        "source_url": ACS_SUMMARY_B01001_URL,
        "total_county_count": total_counties,
        "total_state_count": len(state_counts),
        "total_adult_population_represented": total_adult_pop,
        "total_population_represented": total_pop,
        "states_represented": sorted(state_counts.keys()),
        "counties_per_state": {k: state_counts[k] for k in sorted(state_counts.keys())},
        "excluded_territories": EXCLUDED_TERRITORIES_FIPS,
        "weight_vintage_year": ACS_WEIGHT_VINTAGE_YEAR,
        "cost_reference_year_note": (
            "This file is the frozen adult-population weight vintage for both 2024 and 2026 cost years."
        ),
        "exact_query": ACS_SUMMARY_B01001_URL,
        "variables": list(ACS_VARS),
        "response_hash": next(iter(county_pop_map.values()), {}).get("sha256", ""),
        "retrieval_timestamp": next(iter(county_pop_map.values()), {}).get("retrieved_at", ""),
        "connecticut_note": (
            "Connecticut 2024 ACS 5-Year geographies are planning regions "
            "(FIPS 09110-09170), not legacy counties."
        ),
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)

    return report
