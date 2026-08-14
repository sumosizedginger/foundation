"""FCC Urban Rate Survey broadband price evidence (OD-009).

ACS internet tables measure subscription/access/type and are NOT a price source.

The Foundation selection remains one modest mobile line + one modest residential
broadband connection, but prices must come from real source evidence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved
from foundation.sources.xlsx_xml import rows_as_dicts

logger = logging.getLogger(__name__)

FCC_URS_LANDING = (
    "https://www.fcc.gov/economics-analytics/industry-analysis-division/"
    "urban-rate-survey-data-resources"
)
FCC_URS_FILES: dict[int, dict[str, str]] = {
    2024: {
        "url": "https://www.fcc.gov/sites/default/files/2024_urs_broadband_website_data%202023-12-26.xlsx",
        "filename": "2024_urs_broadband_website_data.xlsx",
    },
    2026: {
        "url": "https://www.fcc.gov/sites/default/files/2026_urs_broadband_website_data_Final.xlsx",
        "filename": "2026_urs_broadband_website_data_Final.xlsx",
    },
}


def download_fcc_urs_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve official FCC Urban Rate Survey broadband Excel results."""
    if year not in FCC_URS_FILES:
        raise ValueError(f"Unsupported FCC URS year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    spec = FCC_URS_FILES[year]
    artifact = acquire_source(
        source_id=f"fcc_urs_broadband_{year}",
        url=spec["url"],
        cache_dir=cache_dir,
        expected_filename=spec["filename"],
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        return record_unretrieved(
            f"fcc_urs_broadband_{year}",
            status="SOURCE_GAP",
            resolved_url=FCC_URS_LANDING,
            notes=(
                f"Official FCC Urban Rate Survey {year} broadband Excel was not retrieved. "
                "ACS internet tables are not used as a PRICE source."
            ),
        )
    return artifact


def _price_cells(row: dict[str, Any]) -> list[float]:
    prices: list[float] = []
    for key, value in row.items():
        key_l = str(key).lower()
        if not any(tok in key_l for tok in ("price", "rate", "monthly", "charge")):
            continue
        if any(tok in key_l for tok in ("voice", "phone")):
            continue
        text = str(value or "").replace("$", "").replace(",", "").strip()
        if not text:
            continue
        try:
            amount = float(text)
        except ValueError:
            continue
        if 5.0 <= amount <= 500.0:
            prices.append(amount)
    return prices


def parse_fcc_urs_broadband(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse official URS broadband rows into unfrozen price candidates."""
    spec = FCC_URS_FILES.get(reference_year) or FCC_URS_FILES[2026]
    path = cache_dir if cache_dir.is_file() else cache_dir / spec["filename"]
    if not path.exists():
        return []
    try:
        rows = rows_as_dicts(path)
    except (OSError, ValueError, KeyError) as exc:
        logger.error("Failed to parse FCC URS workbook %s: %s", path, exc)
        return []
    prices: list[float] = []
    for row in rows:
        prices.extend(_price_cells(row))
    if not prices:
        return [
            LivingCostComponentObservation(
                component_id="connectivity_broadband_urs",
                category="connectivity",
                geography_type="national",
                geography_id="US",
                geography_name="United States Baseline",
                state="US",
                reference_year=reference_year,
                value_annual=None,
                value_monthly=None,
                unit="USD",
                status=ComponentStatus.RETRIEVED_UNVALIDATED,
                source_id=f"fcc_urs_broadband_{reference_year}",
                source_variable="urs_broadband_monthly_rate",
                source_url=spec["url"],
                source_release=f"FCC Urban Rate Survey broadband {reference_year}",
                source_reference_period=str(reference_year),
                retrieved_at=retrieved_at,
                source_artifact_sha256=file_sha256,
                methodology_version="0.2.0-draft",
                notes=(
                    "FCC URS workbook retrieved but no monthly broadband price column "
                    "could be identified. Fail closed rather than invent a price. "
                    "ACS is not used as a price source. Mobile price remains a separate "
                    "SOURCE_GAP / owner decision."
                ),
            )
        ]
    mean_m = sum(prices) / len(prices)
    ordered = sorted(prices)
    median_m = ordered[len(ordered) // 2]
    return [
        LivingCostComponentObservation(
            component_id="connectivity_broadband_urs",
            category="connectivity",
            geography_type="national",
            geography_id="US",
            geography_name="United States Baseline",
            state="US",
            reference_year=reference_year,
            value_annual=round(median_m * 12.0, 2),
            value_monthly=round(median_m, 2),
            unit="USD",
            status=ComponentStatus.MODELED_FROM_MEASURED_INPUTS,
            source_id=f"fcc_urs_broadband_{reference_year}",
            source_variable="urs_broadband_surveyed_monthly_rate",
            source_url=spec["url"],
            source_release=f"FCC Urban Rate Survey broadband {reference_year}",
            source_reference_period=str(reference_year),
            retrieved_at=retrieved_at,
            source_artifact_sha256=file_sha256,
            methodology_version="0.2.0-draft",
            notes=(
                f"FCC Urban Rate Survey broadband candidate (OD-009, not frozen). "
                f"n={len(prices)} surveyed monthly rates in workbook; "
                f"median=${median_m:.2f}/mo; mean=${mean_m:.2f}/mo. "
                "This is urban surveyed rate evidence, not a national COLI. "
                "ACS internet tables are not used as a PRICE source. "
                "One modest mobile line remains a separate source (no official "
                "national prepaid series frozen)."
            ),
        )
    ]
