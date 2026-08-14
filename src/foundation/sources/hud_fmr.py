"""HUD Fair Market Rent (FMR) Source Adapter.

Production downloader, SHA-256 cache verifier, and parser for official U.S. Department of
Housing and Urban Development (HUD) Fair Market Rent datasets for FY2024 and FY2026.

MULTI-COUNTY FMR AREA ARCHITECTURE:
- HUD establishes Fair Market Rents at the FMR Area level (Metropolitan Statistical Areas,
  HUD Metro FMR Areas, and Non-Metropolitan County groups).
- A single HUD FMR area often spans multiple counties (e.g. San Francisco-Oakland MSA).
- In the official HUD county dataset, each constituent county is assigned its own row with its
  distinct 5-digit FIPS code (`fips2010`), allowing exact 1-to-1 joins with Census ACS
  county adult population weights and county-level local tax codes.
- Where an FMR area defines the rent for multiple counties, each county retains its official
  FMR 1-Bedroom value while keeping its individual county population weight.
"""

from __future__ import annotations

import csv
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.http import download_file_with_hash

HUD_FMR_SOURCES: dict[int, dict[str, Any]] = {
    2024: {
        "url": "https://www.huduser.gov/portal/datasets/fmr/fmr2024/FY24_FMRs_revised.csv",
        "release_name": "HUD FY 2024 Fair Market Rents (Revised)",
        "effective_date": "2023-10-01",
        "reference_period": "2024",
        "expected_filename": "FY24_FMRs_revised.csv",
    },
    2026: {
        "url": "https://www.huduser.gov/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.csv",
        "release_name": "HUD FY 2026 Fair Market Rents (Baseline/Revised)",
        "effective_date": "2025-10-01",
        "reference_period": "2026",
        "expected_filename": "FY26_FMRs_revised.csv",
    },
}


def download_hud_fmr_artifact(
    year: int,
    cache_dir: Path,
    force_download: bool = False,
) -> tuple[Path, str, str]:
    """Download or retrieve cached official HUD FMR dataset.

    Returns:
        tuple of (file_path, sha256_hash, retrieved_at_iso)
    """
    if year not in HUD_FMR_SOURCES:
        raise ValueError(f"Unsupported HUD FMR reference year: {year}")

    config = HUD_FMR_SOURCES[year]
    cache_dir.mkdir(parents=True, exist_ok=True)
    target_path = cache_dir / config["expected_filename"]

    if target_path.exists() and not force_download:
        hasher = hashlib.sha256()
        with target_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()
        retrieved_at = datetime.fromtimestamp(target_path.stat().st_mtime, tz=UTC).isoformat()
        return target_path, file_sha256, retrieved_at

    return download_file_with_hash(config["url"], target_path)


def parse_hud_fmr_csv(
    file_path: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse official HUD county FMR dataset into validated component observations."""
    if not file_path.exists():
        raise FileNotFoundError(f"HUD FMR dataset file not found: {file_path}")

    if not file_sha256:
        hasher = hashlib.sha256()
        with file_path.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

    if not retrieved_at:
        retrieved_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    meta = HUD_FMR_SOURCES.get(
        reference_year,
        {
            "url": "https://www.huduser.gov/portal/datasets/fmr.html",
            "release_name": f"HUD FY {reference_year} Fair Market Rents",
            "reference_period": str(reference_year),
        },
    )

    observations: list[LivingCostComponentObservation] = []
    seen_fips: set[str] = set()

    with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.DictReader(fh)
        for row_idx, row in enumerate(reader, start=2):
            fips = (
                row.get("fips2010")
                or row.get("fips")
                or row.get("fips_code")
                or row.get("FIPS")
                or row.get("county_fips")
            )
            if not fips:
                continue

            fips = fips.strip().zfill(5)
            if len(fips) != 5 or not fips.isdigit():
                continue

            # Skip duplicate FIPS records if redundant sub-county rows exist in town-level tables
            if fips in seen_fips:
                continue
            seen_fips.add(fips)

            state_alpha = (
                str(row.get("state_alpha") or row.get("state") or row.get("State") or "")
                .strip()
                .upper()
            )
            county_name = str(
                row.get("county_name") or row.get("countyname") or row.get("County Name") or ""
            ).strip()
            metro_name = str(
                row.get("metro_name") or row.get("areaname") or row.get("hud_area_name") or ""
            ).strip()
            geo_name = f"{county_name}, {state_alpha}".strip(", ") or metro_name or fips

            fmr_1_str = row.get("fmr_1") or row.get("fmr1") or row.get("FMR1") or row.get("fmr_1br")
            if not fmr_1_str:
                continue

            try:
                fmr_1_monthly = float(str(fmr_1_str).replace("$", "").replace(",", "").strip())
            except ValueError:
                continue

            if fmr_1_monthly <= 0:
                continue

            fmr_1_annual = round(fmr_1_monthly * 12.0, 2)

            obs = LivingCostComponentObservation(
                component_id="housing_1br",
                category="housing",
                geography_type="county",
                geography_id=fips,
                geography_name=geo_name,
                state=state_alpha,
                reference_year=reference_year,
                value_annual=fmr_1_annual,
                value_monthly=round(fmr_1_monthly, 2),
                unit="USD",
                status=ComponentStatus.MEASURED,
                source_id=f"hud_fmr_{reference_year}",
                source_variable="fmr_1",
                source_url=meta["url"],
                source_release=meta["release_name"],
                source_reference_period=meta["reference_period"],
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=f"HUD 40th percentile 1BR Fair Market Rent in {geo_name} (FMR Area: {metro_name or 'Non-Metro'}).",
            )
            observations.append(obs)

    return observations
