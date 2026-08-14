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

import logging
from pathlib import Path
from typing import Any

import openpyxl

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source

logger = logging.getLogger(__name__)

HUD_FMR_LANDING = "https://www.huduser.gov/portal/datasets/fmr.html"

HUD_FMR_SOURCES: dict[int, dict[str, Any]] = {
    2024: {
        "url": "https://www.huduser.gov/portal/datasets/fmr/fmr2024/FMR2024_final_revised.xlsx",
        "landing_page": HUD_FMR_LANDING,
        "release_name": "HUD FY 2024 Fair Market Rents (Revised)",
        "effective_date": "2024-03-11",
        "reference_period": "2024",
        "expected_filename": "FMR2024_final_revised.xlsx",
    },
    2026: {
        "url": "https://www.huduser.gov/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.xlsx",
        "landing_page": HUD_FMR_LANDING,
        "release_name": "HUD FY 2026 Fair Market Rents (Revised)",
        "effective_date": "2026-05-21",
        "reference_period": "2026",
        "expected_filename": "FY26_FMRs_revised.xlsx",
    },
}


def download_hud_fmr_artifact(
    year: int,
    cache_dir: Path,
    force_download: bool = False,
):
    """Download or retrieve cached official HUD FMR dataset."""
    if year not in HUD_FMR_SOURCES:
        raise ValueError(f"Unsupported HUD FMR reference year: {year}")

    config = HUD_FMR_SOURCES[year]
    cache_dir.mkdir(parents=True, exist_ok=True)
    return acquire_source(
        source_id=f"hud_fmr_{year}",
        url=config["url"],
        cache_dir=cache_dir,
        expected_filename=config["expected_filename"],
        force_download=force_download,
    )


def parse_hud_fmr_xlsx(
    file_path: Path,
    reference_year: int,
    retrieved_at: str,
    file_sha256: str,
) -> list[LivingCostComponentObservation]:
    """Parse official HUD county FMR XLSX dataset into validated component observations."""
    if not file_path.exists():
        raise FileNotFoundError(f"HUD FMR dataset file not found: {file_path}")

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

    try:
        wb = openpyxl.load_workbook(filename=file_path, read_only=True, data_only=True)
    except ValueError:
        # Some official HUD workbooks have invalid core.xml timestamps.
        from openpyxl.reader.excel import ExcelReader

        reader = ExcelReader(file_path, read_only=True, data_only=True)
        reader.read_manifest()
        reader.read_strings()
        reader.read_workbook()
        reader.read_worksheets()
        wb = reader.wb
    sheet = wb.active
    if not sheet:
        raise ValueError(f"No active sheet found in HUD FMR XLSX: {file_path}")

    headers = {}
    for row_idx, row in enumerate(sheet.iter_rows(values_only=True)):
        if row_idx == 0:
            for col_idx, val in enumerate(row):
                if val:
                    headers[str(val).strip().lower()] = col_idx
            continue

        def get_val(current_row: tuple[object, ...] | list[object], keys: list[str]) -> str:
            for k in keys:
                if k in headers and current_row[headers[k]] is not None:
                    return str(current_row[headers[k]]).strip()
            return ""

        fips = get_val(row, ["fips2010", "fips", "fips_code", "county_fips"])
        if not fips:
            continue

        digits = "".join(ch for ch in fips if ch.isdigit())
        if len(digits) >= 10:
            fips = digits[:5]
        else:
            fips = digits.zfill(5)
        if len(fips) != 5 or not fips.isdigit():
            continue

        if fips in seen_fips:
            continue
        seen_fips.add(fips)

        state_alpha = get_val(row, ["stusps", "state_alpha", "state"]).upper()
        if state_alpha.isdigit():
            state_alpha = get_val(row, ["stusps", "state_alpha"]).upper()
        county_name = get_val(row, ["county_name", "countyname"])
        metro_name = get_val(row, ["metro_name", "areaname", "hud_area_name"])
        geo_name = f"{county_name}, {state_alpha}".strip(", ") or metro_name or fips

        fmr_1_str = get_val(row, ["fmr_1", "fmr1", "fmr_1br"])
        if not fmr_1_str:
            continue

        try:
            fmr_1_monthly = float(fmr_1_str.replace("$", "").replace(",", ""))
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

    wb.close()
    return observations
