"""Living Cost Canonical Source Manifest Generator.

Generates data/metadata/living_cost_source_manifest.json registering all official
government and primary source datasets with cryptographic hashes, licensing notes,
retrieval timestamps, and validation statuses.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StaticSourceDef:
    source_id: str
    publisher: str
    dataset: str
    reference_year: int
    release: str
    url: str
    licensing_notes: str


@dataclass(frozen=True)
class RetrievedSourceArtifact:
    source_id: str
    retrieved_at: str
    sha256: str
    byte_size: int
    local_cache_filename: str
    validation_status: str


STATIC_SOURCES: list[StaticSourceDef] = [
    StaticSourceDef(
        source_id="hud_fmr_2024",
        publisher="U.S. Department of Housing and Urban Development (HUD)",
        dataset="Fair Market Rents (FMR) 1-Bedroom 40th Percentile County Dataset",
        reference_year=2024,
        release="HUD FY 2024 Fair Market Rents (Revised)",
        url="https://www.huduser.gov/portal/datasets/fmr/fmr2024/FY24_FMRs_revised.csv",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="hud_fmr_2026",
        publisher="U.S. Department of Housing and Urban Development (HUD)",
        dataset="Fair Market Rents (FMR) 1-Bedroom 40th Percentile County Dataset",
        reference_year=2026,
        release="HUD FY 2026 Fair Market Rents (Baseline/Revised)",
        url="https://www.huduser.gov/portal/datasets/fmr/fmr2026/FY26_FMRs_revised.csv",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="census_acs5_2024",
        publisher="U.S. Census Bureau",
        dataset="American Community Survey 5-Year Estimates Table B01001 (Adult Population Age 18+)",
        reference_year=2024,
        release="2023 ACS 5-Year Data Release",
        url="https://api.census.gov/data/2023/acs/acs5",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="cms_marketplace_puf_2024",
        publisher="Centers for Medicare & Medicaid Services (CMS)",
        dataset="Marketplace Public Use Files (Rate PUF / Age 40 Individual Silver Rates)",
        reference_year=2024,
        release="CMS 2024 Marketplace PUF",
        url="https://www.cms.gov/marketplace/resources/data/public-use-files",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="meps_table1_2024",
        publisher="Agency for Healthcare Research and Quality (AHRQ)",
        dataset="Medical Expenditure Panel Survey (MEPS) Household Component Table 1",
        reference_year=2024,
        release="AHRQ MEPS Table 1 (Adults 18-64 Privately Insured OOP Spending)",
        url="https://meps.ahrq.gov/mepsweb/",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="usda_food_low_cost_2024",
        publisher="U.S. Department of Agriculture (USDA)",
        dataset="USDA Food Plans: Monthly Cost of Food Reports (Low-Cost Plan)",
        reference_year=2024,
        release="USDA Food Plans (2024 Annual Average)",
        url="https://www.fns.usda.gov/cnpp/usda-food-plans-cost-food-monthly-reports",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="eia_gas_price_2024",
        publisher="U.S. Energy Information Administration (EIA)",
        dataset="Weekly Retail Gasoline and Diesel Prices (Annual State/PADD Averages)",
        reference_year=2024,
        release="EIA Petroleum Marketing Annual Baseline",
        url="https://www.eia.gov/petroleum/gasdiesel/",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="naic_auto_ins_2024",
        publisher="National Association of Insurance Commissioners (NAIC)",
        dataset="Auto Insurance Database Report (Combined Average Annual Expenditure)",
        reference_year=2024,
        release="NAIC Auto Insurance Database Report (2021/2022 Data Baseline)",
        url="https://content.naic.org/",
        licensing_notes="Public Aggregate Tables / Research Fair Use",
    ),
    StaticSourceDef(
        source_id="fhwa_nhts_2024",
        publisher="Federal Highway Administration (FHWA)",
        dataset="National Household Travel Survey (NHTS) Solo-Driver Annual Mileage Baseline",
        reference_year=2024,
        release="FHWA NHTS Table VMT_WORKER_SOLO",
        url="https://nhts.ornl.gov/",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="bls_ce_essentials_2024",
        publisher="U.S. Bureau of Labor Statistics (BLS)",
        dataset="Consumer Expenditure Survey (CE) Single-Person Consumer Unit Microdata",
        reference_year=2024,
        release="BLS CE Survey Microdata (FMLI/EXPN)",
        url="https://www.bls.gov/cex/",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="bea_rpp_2024",
        publisher="U.S. Bureau of Economic Analysis (BEA)",
        dataset="Regional Price Parities by State & Metro Area (SARPP All Items, Series: SARPP-1)",
        reference_year=2024,
        release="BEA Regional Price Parities 2024 Release",
        url="https://www.bea.gov/data/prices-inflation/regional-price-parities-state-and-metro-area",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="irs_rev_proc_2023_34",
        publisher="Internal Revenue Service (IRS)",
        dataset="Internal Revenue Bulletin: Rev. Proc. 2023-34 (2024 Tax Inflation Adjustments)",
        reference_year=2024,
        release="IRS Rev. Proc. 2023-34",
        url="https://www.irs.gov/pub/irs-drop/rp-23-34.pdf",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
    StaticSourceDef(
        source_id="irs_rev_proc_2025_32",
        publisher="Internal Revenue Service (IRS)",
        dataset="Internal Revenue Bulletin: Rev. Proc. 2025-32 (2026 Tax Inflation Adjustments)",
        reference_year=2026,
        release="IRS Rev. Proc. 2025-32",
        url="https://www.irs.gov/pub/irs-drop/rp-25-32.pdf",
        licensing_notes="U.S. Government Work (Public Domain)",
    ),
]


def generate_source_manifest(
    retrieved_artifacts: list[RetrievedSourceArtifact], output_path: Path | None = None
) -> dict[str, Any]:
    """Generate and write the canonical living cost source manifest."""
    now_iso = datetime.now(UTC).replace(microsecond=0).isoformat()

    sources_out = []
    artifacts_by_id = {a.source_id: a for a in retrieved_artifacts}

    for static_def in STATIC_SOURCES:
        base_dict = {
            "source_id": static_def.source_id,
            "publisher": static_def.publisher,
            "dataset": static_def.dataset,
            "reference_year": static_def.reference_year,
            "release": static_def.release,
            "url": static_def.url,
            "licensing_notes": static_def.licensing_notes,
            "parser_version": "0.2.0-draft",
        }

        artifact = artifacts_by_id.get(static_def.source_id)
        if artifact:
            base_dict["retrieved_at"] = artifact.retrieved_at
            base_dict["sha256"] = artifact.sha256
            base_dict["byte_size"] = artifact.byte_size
            base_dict["local_cache_filename"] = artifact.local_cache_filename
            base_dict["validation_status"] = artifact.validation_status
        else:
            base_dict["retrieved_at"] = None
            base_dict["sha256"] = None
            base_dict["byte_size"] = None
            base_dict["local_cache_filename"] = None
            base_dict["validation_status"] = "UNAVAILABLE"

        sources_out.append(base_dict)

    manifest_doc = {
        "manifest_type": "living_cost_source_manifest",
        "methodology_version": "0.2.0-draft",
        "generated_at": now_iso,
        "source_count": len(sources_out),
        "sources": sources_out,
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(manifest_doc, fh, indent=2)

    return manifest_doc

