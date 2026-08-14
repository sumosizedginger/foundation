"""National Association of Insurance Commissioners (NAIC) Auto Insurance Adapter.

The 2022/2023 Auto Insurance Database Report is an official FREE download.
That does not grant raw-report redistribution rights.

METHODOLOGICAL DISTINCTIONS (OD-006 — not frozen):
- A. average expenditure per insured vehicle
- B. combined average premium
- C. coverage-specific / mandatory-coverage measure if tables permit

Do not treat insurance as LICENSING_REVIEW merely because a previous agent
failed to discover the free report. Use redistribution_status separately.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path

from foundation.living_cost.models import ComponentStatus, LivingCostComponentObservation
from foundation.sources.acquisition import acquire_source, record_unretrieved

logger = logging.getLogger(__name__)

NAIC_LANDING = "https://content.naic.org/publications"
NAIC_NEWS_URL = (
    "https://content.naic.org/article/naic-releases-20222023-auto-insurance-database-report"
)
NAIC_REPORT_URL = (
    "https://content.naic.org/sites/default/files/publication-aut-pb-auto-insurance-database.pdf"
)
NAIC_PUBLICATION_YEAR = 2025
NAIC_DATA_YEAR = 2023
NAIC_REDISTRIBUTION_STATUS = "FREE_DOWNLOAD_REDISTRIBUTION_UNCONFIRMED"
NAIC_EXPECTED_FILENAME = "publication-aut-pb-auto-insurance-database.pdf"


def download_naic_artifact(year: int, cache_dir: Path, force_download: bool = False):
    """Retrieve the official free 2022/2023 Auto Insurance Database Report PDF."""
    if year not in (2024, 2026):
        raise ValueError(f"Unsupported NAIC reference year: {year}")
    cache_dir.mkdir(parents=True, exist_ok=True)
    artifact = acquire_source(
        source_id=f"naic_auto_ins_{year}",
        url=NAIC_REPORT_URL,
        cache_dir=cache_dir,
        expected_filename=NAIC_EXPECTED_FILENAME,
        force_download=force_download,
        refresh_if_unprovenanced=True,
    )
    if artifact is None:
        return record_unretrieved(
            f"naic_auto_ins_{year}",
            status="SOURCE_GAP",
            resolved_url=NAIC_REPORT_URL,
            notes=(
                "Official NAIC 2022/2023 Auto Insurance Database Report PDF was not retrieved. "
                f"Landing: {NAIC_LANDING}. This is a free official download, not a licensed-only "
                "CSV. Do not fabricate a state-average CSV."
            ),
        )
    from dataclasses import replace

    notes = (
        f"Official NAIC 2022/2023 Auto Insurance Database Report retrieved. "
        f"source_url={NAIC_REPORT_URL}; publication_year={NAIC_PUBLICATION_YEAR} "
        f"(Adopted December 2025; news release 2026-02-13); data_year={NAIC_DATA_YEAR}; "
        f"byte_size={artifact.byte_size}; sha256={artifact.sha256}; "
        f"retrieved_at={artifact.retrieved_at}; "
        f"redistribution_status={NAIC_REDISTRIBUTION_STATUS}. "
        "Free download is not a redistribution license. Derived statistics with attribution "
        "are handled separately from raw-artifact redistribution. OD-006 remains unfrozen: "
        "choose average expenditure vs combined average premium vs coverage-specific measure."
    )
    return replace(
        artifact,
        validation_status="RETRIEVED_UNVALIDATED",
        notes=notes,
        resolved_url=NAIC_REPORT_URL,
    )


def parse_naic_auto_insurance_csv(
    cache_dir: Path,
    reference_year: int,
    retrieved_at: str = "",
    file_sha256: str = "",
) -> list[LivingCostComponentObservation]:
    """Parse a derived NAIC state table if an extracted CSV is present.

    The official artifact is a PDF. This parser does not invent state averages
    from the PDF. A fixture/extracted CSV is accepted only when present.
    """
    file_path = (
        cache_dir
        if cache_dir.is_file() and cache_dir.suffix.lower() == ".csv"
        else cache_dir / f"naic_auto_insurance_{reference_year}.csv"
    )

    if not file_path.exists():
        logger.warning("NAIC extracted CSV not found: %s", file_path)
        return []

    observations: list[LivingCostComponentObservation] = []

    try:
        with file_path.open("r", encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                state_alpha = str(row.get("state") or row.get("State") or "").strip().upper()
                if not state_alpha:
                    continue

                prem_str = (
                    row.get("average_annual_premium")
                    or row.get("combined_expenditure")
                    or row.get("premium")
                    or "0"
                )
                try:
                    annual_prem = float(str(prem_str).replace("$", "").replace(",", "").strip())
                except ValueError:
                    continue

                if annual_prem <= 0:
                    continue

                source_vintage = str(
                    row.get("source_year") or row.get("vintage") or NAIC_DATA_YEAR
                ).strip()
                measure = str(
                    row.get("measure") or "combined_average_expenditure_or_premium_unspecified"
                ).strip()

                obs = LivingCostComponentObservation(
                    component_id="transport_auto_insurance",
                    category="transportation",
                    geography_type="state",
                    geography_id=state_alpha,
                    geography_name=f"{state_alpha} Auto Insurance",
                    state=state_alpha,
                    reference_year=reference_year,
                    value_annual=round(annual_prem, 2),
                    value_monthly=round(annual_prem / 12.0, 2),
                    unit="USD",
                    status=ComponentStatus.MEASURED,
                    source_id=f"naic_auto_ins_{reference_year}",
                    source_variable=measure,
                    source_url=NAIC_REPORT_URL,
                    source_release=(
                        f"NAIC 2022/2023 Auto Insurance Database Report "
                        f"(Source Vintage: {source_vintage})"
                    ),
                    source_reference_period=source_vintage,
                    retrieved_at=retrieved_at,
                    source_artifact_sha256=file_sha256,
                    methodology_version="0.2.0-draft",
                    notes=(
                        f"NAIC {measure} in {state_alpha} (Source Vintage: {source_vintage}). "
                        f"redistribution_status={NAIC_REDISTRIBUTION_STATUS}. "
                        "Headline insurance measure is not frozen (OD-006)."
                    ),
                )
                observations.append(obs)
    except (OSError, ValueError, csv.Error, UnicodeError) as e:
        logger.error(f"Failed to parse NAIC CSV: {e}")

    return observations
