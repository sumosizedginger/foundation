"""Connecticut HUD-legacy-county reconstruction from official Census sources (OD-013).

KEEP HUD COST GEOGRAPHY = legacy HUD county.

Reconstruct adult population weights for the eight legacy Connecticut counties
from ACS B01001 county-subdivision rows plus the official Census Connecticut
County to County Subdivision Crosswalk.

Do not invent planning-region rents. If official sources cannot reproduce the
reconstruction, leave CT unmatched.
"""

from __future__ import annotations

import csv
import io
import logging
from pathlib import Path
from typing import Any

from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.census_acs import compute_adult_population_from_b01001_row
from foundation.sources.xlsx_xml import rows_as_dicts

logger = logging.getLogger(__name__)

CT_CROSSWALK_LANDING = "https://www2.census.gov/geo/docs/reference/ct_change/"
CT_CROSSWALK_XLSX = (
    "https://www2.census.gov/geo/docs/reference/ct_change/ct_cou_to_cousub_crosswalk.xlsx"
)
CT_CROSSWALK_TXT = (
    "https://www2.census.gov/geo/docs/reference/ct_change/ct_cou_to_cousub_crosswalk.txt"
)
CT_PLANNING_REGION_FIPS = (
    "09110",
    "09120",
    "09130",
    "09140",
    "09150",
    "09160",
    "09170",
    "09180",
    "09190",
)
# Eight legacy Connecticut counties (HUD FMR geography).
CT_LEGACY_COUNTY_FIPS = (
    "09001",  # Fairfield
    "09003",  # Hartford
    "09005",  # Litchfield
    "09007",  # Middlesex
    "09009",  # New Haven
    "09011",  # New London
    "09013",  # Tolland
    "09015",  # Windham
)


def download_ct_crosswalk_artifact(cache_dir: Path, force_download: bool = False):
    """Retrieve official Census CT county-to-county-subdivision crosswalk."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = acquire_source(
        source_id="census_ct_cousub_crosswalk",
        url=CT_CROSSWALK_XLSX,
        cache_dir=cache_dir,
        expected_filename="ct_cou_to_cousub_crosswalk.xlsx",
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        artifact = acquire_source(
            source_id="census_ct_cousub_crosswalk",
            url=CT_CROSSWALK_TXT,
            cache_dir=cache_dir,
            expected_filename="ct_cou_to_cousub_crosswalk.txt",
            force_download=force_download,
            refresh_if_unprovenanced=True,
        )
    if artifact is None:
        return record_unretrieved(
            "census_ct_cousub_crosswalk",
            status="SOURCE_GAP",
            resolved_url=CT_CROSSWALK_LANDING,
            notes=(
                "Official Census Connecticut County to County Subdivision Crosswalk "
                "was not retrieved. CT remains unmatched rather than fabricating allocation."
            ),
        )
    return artifact


def parse_ct_crosswalk(path: Path) -> list[dict[str, str]]:
    """Parse official Census CT crosswalk rows. Fail closed on unknown layout."""
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    suffix = path.suffix.lower()
    try:
        if suffix in {".xlsx", ".xlsm"}:
            for rec in rows_as_dicts(path):
                rows.append({str(k): str(v) if v is not None else "" for k, v in rec.items()})
        else:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",\t|")
            reader = csv.DictReader(io.StringIO(text), dialect=dialect)
            rows = [{str(k): str(v or "") for k, v in rec.items()} for rec in reader]
    except (OSError, ValueError, csv.Error, KeyError) as exc:
        logger.error("Failed to parse CT crosswalk %s: %s", path, exc)
        return []
    return rows


def _pick(row: dict[str, str], *names: str) -> str:
    lower = {k.lower().strip(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower:
            return str(lower[name.lower()]).strip()
    return ""


def _normalize_header(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _lookup_norm(by_norm: dict[str, str], *needles: str) -> str:
    for needle in needles:
        n = _normalize_header(needle)
        for key, val in by_norm.items():
            if n in key:
                return str(val).strip()
    return ""


def assign_towns_to_legacy_counties(rows: list[dict[str, str]]) -> dict[str, str]:
    """Map current ACS county-subdivision GEOID -> 5-digit legacy county FIPS.

    Official Census workbook columns (2022 CT change file):
    STATEFP, OLD_COUNTYFP, NEW_COUSUB_GEOID / OLD_COUSUB_GEOID, COUSUBFP.
    ACS 2024 uses NEW planning-region county-subdivision GEOIDs.
    """
    mapping: dict[str, str] = {}
    for row in rows:
        by_norm = {_normalize_header(k): v for k, v in row.items()}
        state = _lookup_norm(by_norm, "STATEFP", "state") or "09"
        old_county = _lookup_norm(by_norm, "OLD_COUNTYFP", "legacy_county", "countyfp")
        new_geoid = _lookup_norm(by_norm, "NEW_COUSUB_GEOID", "newcousubgeoid")
        old_geoid = _lookup_norm(by_norm, "OLD_COUSUB_GEOID", "oldcousubgeoid")
        cousubfp = _lookup_norm(by_norm, "COUSUBFP", "cousub")

        digits_state = "".join(ch for ch in state if ch.isdigit()).zfill(2)
        digits_old_county = "".join(ch for ch in old_county if ch.isdigit()).zfill(3)
        if digits_state != "09" or len(digits_old_county) < 3:
            continue
        legacy = f"09{digits_old_county[-3:]}"
        if legacy not in CT_LEGACY_COUNTY_FIPS:
            continue

        # Prefer the NEW (planning-region) cousub GEOID used by 2024 ACS.
        geoid_raw = "".join(ch for ch in str(new_geoid) if ch.isdigit())
        if not geoid_raw:
            geoid_raw = "".join(ch for ch in str(old_geoid) if ch.isdigit())
        if len(geoid_raw) == 9:
            geoid_raw = geoid_raw.zfill(10)
        if len(geoid_raw) >= 10:
            geoid = geoid_raw[:10]
        elif cousubfp:
            digits_cousub = "".join(ch for ch in cousubfp if ch.isdigit()).zfill(5)
            # Fall back to constructing from NEW county if present.
            new_county = "".join(
                ch for ch in _lookup_norm(by_norm, "NEW_COUNTYFP") if ch.isdigit()
            ).zfill(3)
            geoid = f"09{new_county[-3:]}{digits_cousub[-5:]}"
        else:
            continue
        if not geoid.startswith("09"):
            continue
        mapping[geoid] = legacy
    return mapping


def parse_acs_ct_cousub_adults(dat_path: Path) -> dict[str, int]:
    """Adult 18+ population at county-subdivision geography for Connecticut."""
    adults: dict[str, int] = {}
    if not dat_path.exists():
        return adults
    with dat_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        header = fh.readline()
        if not header:
            return adults
        cols = header.rstrip("\n").split("|")
        index = {name: i for i, name in enumerate(cols)}
        geo_idx = index.get("GEO_ID")
        if geo_idx is None:
            return adults
        for line in fh:
            parts = line.rstrip("\n").split("|")
            if geo_idx >= len(parts):
                continue
            geo = parts[geo_idx]
            # County subdivision summary level.
            if not geo.startswith("0600000US09") or len(geo) < 19:
                continue
            geoid = geo[9:19]  # sscccddddd
            row = {name: parts[i] if i < len(parts) else "" for name, i in index.items()}
            try:
                adult_pop, _total = compute_adult_population_from_b01001_row(row)
            except (ValueError, KeyError, TypeError):
                continue
            adults[geoid] = int(adult_pop)
    return adults


def reconstruct_legacy_county_adult_pop(
    crosswalk_rows: list[dict[str, str]],
    cousub_adults: dict[str, int],
) -> dict[str, Any]:
    """Sum town adult population into eight legacy counties. Fail closed if invalid."""
    mapping = assign_towns_to_legacy_counties(crosswalk_rows)
    report: dict[str, Any] = {
        "architecture": "keep_hud_geography_legacy_county",
        "planning_region_fips": list(CT_PLANNING_REGION_FIPS),
        "legacy_county_fips": list(CT_LEGACY_COUNTY_FIPS),
        "crosswalk_rows": len(crosswalk_rows),
        "mapped_towns": len(mapping),
        "cousub_adult_rows": len(cousub_adults),
        "legacy_county_adult_population": {},
        "unmapped_towns": [],
        "duplicate_towns": [],
        "missing_legacy_counties": [],
        "reproduced": False,
        "notes": "",
    }
    if not mapping or not cousub_adults:
        report["notes"] = (
            "Official CT reconstruction cannot be reproduced (empty crosswalk or "
            "empty ACS county-subdivision B01001). Leave CT unmatched."
        )
        return report

    assigned: dict[str, str] = {}
    duplicates: list[str] = []
    for geoid, legacy in mapping.items():
        if geoid in assigned and assigned[geoid] != legacy:
            duplicates.append(geoid)
        assigned[geoid] = legacy
    report["duplicate_towns"] = sorted(set(duplicates))

    unmapped = sorted(set(cousub_adults) - set(assigned))
    report["unmapped_towns"] = unmapped

    totals = {fips: 0 for fips in CT_LEGACY_COUNTY_FIPS}
    for geoid, adult in cousub_adults.items():
        legacy = assigned.get(geoid)
        if legacy is None:
            continue
        totals[legacy] += adult
    report["legacy_county_adult_population"] = totals
    missing = [fips for fips, pop in totals.items() if pop <= 0]
    report["missing_legacy_counties"] = missing
    reproduced = (
        not duplicates
        and not missing
        and len(unmapped) == 0
        and all(pop > 0 for pop in totals.values())
    )
    report["reproduced"] = reproduced
    if reproduced:
        report["notes"] = (
            "Reconstructed eight legacy-county adult populations from official "
            "Census CT crosswalk + ACS B01001 county-subdivision rows. "
            "HUD FMR geography stays on legacy counties."
        )
    else:
        report["notes"] = (
            "CT reconstruction failed validation (duplicate municipality, missing town, "
            "or empty legacy county). Leave CT unmatched rather than fabricate allocation."
        )
    return report
